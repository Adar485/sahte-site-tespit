"""Egress control for the capture browser.

The browser is given a local forward proxy as its only route out and is told not
to resolve names itself. For every connection (navigation, redirect hop, frame,
subresource, popup, WebSocket tunnel) the proxy:

1. resolves the host name,
2. refuses it unless EVERY resolved address is a public unicast address,
3. connects to one of exactly those addresses.

Because the address that was checked is the address that is connected to, a name
that changes its answer between check and use (DNS rebinding) cannot redirect the
connection. Browser-side request filtering alone could not guarantee this.
"""

import asyncio
import ipaddress
import logging
import socket
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# Explicit lists, so the result does not depend on the Python version's is_global.
_BLOCKED_IPV4 = tuple(
    ipaddress.ip_network(network)
    for network in (
        "0.0.0.0/8",  # unspecified / "this network"
        "10.0.0.0/8",  # private
        "100.64.0.0/10",  # carrier-grade NAT
        "127.0.0.0/8",  # loopback
        "169.254.0.0/16",  # link-local, cloud metadata
        "172.16.0.0/12",  # private
        "192.0.0.0/24",
        "192.0.2.0/24",  # documentation
        "192.88.99.0/24",  # 6to4 relay
        "192.168.0.0/16",  # private
        "198.18.0.0/15",  # benchmarking
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved, broadcast
        "168.63.129.16/32",  # Azure platform address
    )
)
# IPv6: only global unicast, minus ranges that embed or tunnel other addresses.
_GLOBAL_IPV6 = ipaddress.ip_network("2000::/3")
_BLOCKED_IPV6 = tuple(
    ipaddress.ip_network(network)
    for network in ("2001::/23", "2001:db8::/32", "2002::/16", "3fff::/20")  # IETF/Teredo, docs, 6to4, docs
)

MAX_HEAD_BYTES = 64 * 1024
CONNECT_TIMEOUT_S = 8


def is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if address.version == 4:
        return not any(address in network for network in _BLOCKED_IPV4)
    # IPv4-mapped, NAT64, loopback, link-local, unique-local and multicast are all outside 2000::/3.
    return address in _GLOBAL_IPV6 and not any(address in network for network in _BLOCKED_IPV6)


class DestinationRefused(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason  # "destination_blocked" | "dns_error"


async def _system_resolver(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0] for info in infos))


@dataclass(frozen=True)
class NetworkPolicy:
    """Which destinations the browser may reach.

    test_destinations exists for tests with local fixture servers: it maps an exact
    (host, port) to an address that is then reachable. It can only be set from code;
    no setting or environment variable fills it.
    """

    allowed_ports: frozenset[int] = frozenset({80, 443, 8080, 8443})
    test_destinations: Mapping[tuple[str, int], str] = field(default_factory=dict)
    resolver: Callable[[str, int], Awaitable[list[str]]] = _system_resolver

    async def addresses_for(self, host: str, port: int) -> list[str]:
        """The only addresses a connection to host:port may use."""
        host = host.lower().rstrip(".")
        if (host, port) in self.test_destinations:
            return [self.test_destinations[host, port]]
        if port not in self.allowed_ports:
            raise DestinationRefused("destination_blocked")
        try:
            ipaddress.ip_address(host)
            addresses = [host]
        except ValueError:
            try:
                addresses = await asyncio.wait_for(self.resolver(host, port), CONNECT_TIMEOUT_S)
            except (OSError, UnicodeError, asyncio.TimeoutError) as error:
                raise DestinationRefused("dns_error") from error
        if not addresses:
            raise DestinationRefused("dns_error")
        # One private answer is enough to refuse: the name is not purely public.
        if not all(is_public_address(address) for address in addresses):
            raise DestinationRefused("destination_blocked")
        return addresses


class EgressProxy:
    """Minimal HTTP forward proxy (CONNECT and absolute-form http) bound to loopback."""

    def __init__(self, policy: NetworkPolicy, max_download_bytes: int, max_connections: int = 300) -> None:
        self.policy = policy
        self.max_download_bytes = max_download_bytes
        self.max_connections = max_connections
        self.failures: dict[tuple[str, int], str] = {}  # destination -> why it failed
        self.blocked_count = 0
        self.connection_count = 0
        self.downloaded_bytes = 0
        self.limit_exceeded = False
        self._server: asyncio.AbstractServer | None = None
        self._tasks: set[asyncio.Task] = set()
        self._writers: set[asyncio.StreamWriter] = set()

    @property
    def url(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.sockets[0].getsockname()[1]}"

    async def __aenter__(self) -> "EgressProxy":
        self._server = await asyncio.start_server(self._accept, "127.0.0.1", 0, limit=MAX_HEAD_BYTES)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._server is not None:
            self._server.close()
        for writer in list(self._writers):
            writer.close()
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        self._tasks.add(task)
        self._writers.add(writer)
        try:
            await self._serve(reader, writer)
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError):
            pass  # a broken or refused connection is simply closed
        except asyncio.CancelledError:
            pass
        finally:
            writer.close()
            self._writers.discard(writer)
            self._tasks.discard(task)

    async def _open(self, host: str, port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
        key = (host.lower().rstrip("."), port)
        self.connection_count += 1
        if self.connection_count > self.max_connections or self.limit_exceeded:
            self.failures[key] = "limit_exceeded"
            return None
        try:
            addresses = await self.policy.addresses_for(host, port)
        except DestinationRefused as refused:
            self.failures[key] = refused.reason
            if refused.reason == "destination_blocked":
                self.blocked_count += 1
            return None
        for address in addresses:
            try:
                connection = await asyncio.wait_for(asyncio.open_connection(address, port), CONNECT_TIMEOUT_S)
            except (OSError, asyncio.TimeoutError):
                continue
            self.failures.pop(key, None)
            return connection
        self.failures[key] = "connection_failed"
        return None

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 30)
        request_line, *header_lines = head[:-4].decode("latin-1").split("\r\n")
        method, target, _ = request_line.split(" ", 2)

        if method == "CONNECT":
            parts = urlsplit(f"//{target}")
            if not parts.hostname or not parts.port:
                return
            upstream = await self._open(parts.hostname, parts.port)
            if upstream is None:
                return  # closed without a response, so it cannot be mistaken for a page
            up_reader, up_writer = upstream
            try:
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                # The browser uses tunnels for TLS and for WebSockets only. A tunnel that does not
                # start with a TLS handshake is a plain ws:// connection (a worker can open one
                # past the page-level WebSocket block) and is refused.
                first = await asyncio.wait_for(reader.read(64 * 1024), 30)
                if not first.startswith(b"\x16"):
                    return
                up_writer.write(first)
                await self._relay(reader, writer, up_reader, up_writer)
            finally:
                up_writer.close()
            return

        parts = urlsplit(target)
        if parts.scheme != "http" or not parts.hostname or "@" in parts.netloc:
            return
        headers = [line.split(":", 1) for line in header_lines if ":" in line]
        values = {name.strip().lower(): value.strip() for name, value in headers}
        if "transfer-encoding" in values:
            return
        body_length = int(values.get("content-length", "0"))
        if not 0 <= body_length <= 1024 * 1024:
            return
        upstream = await self._open(parts.hostname, parts.port or 80)
        if upstream is None:
            return
        up_reader, up_writer = upstream
        try:
            # One request per connection: a second request could name another host.
            path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
            hop_by_hop = {"connection", "proxy-connection", "keep-alive", "proxy-authorization", "upgrade"}
            lines = [f"{method} {path} HTTP/1.1"]
            lines += [f"{name}:{value}" for name, value in headers if name.strip().lower() not in hop_by_hop]
            lines += ["Connection: close", "", ""]
            up_writer.write("\r\n".join(lines).encode("latin-1"))
            if body_length:
                up_writer.write(await reader.readexactly(body_length))
            await up_writer.drain()

            response_head = await asyncio.wait_for(up_reader.readuntil(b"\r\n\r\n"), 30)
            status_line, *response_headers = response_head[:-4].split(b"\r\n")
            kept = [
                line for line in response_headers
                if line.split(b":", 1)[0].strip().lower() not in (b"connection", b"keep-alive", b"proxy-connection")
            ]
            writer.write(b"\r\n".join([status_line, *kept, b"Connection: close", b"", b""]))
            # Stop when the server finishes or the browser closes; further client bytes are not forwarded.
            await _first_completed(self._pipe(up_reader, writer, counted=True), reader.read(1))
        finally:
            up_writer.close()

    async def _relay(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        up_reader: asyncio.StreamReader,
        up_writer: asyncio.StreamWriter,
    ) -> None:
        await _first_completed(
            self._pipe(reader, up_writer, counted=False), self._pipe(up_reader, writer, counted=True)
        )

    async def _pipe(self, source: asyncio.StreamReader, sink: asyncio.StreamWriter, counted: bool) -> None:
        while data := await source.read(64 * 1024):
            if counted:
                self.downloaded_bytes += len(data)
                if self.downloaded_bytes > self.max_download_bytes:
                    self.limit_exceeded = True
                    return
            sink.write(data)
            await sink.drain()


async def _first_completed(*coroutines) -> None:  # type: ignore[no-untyped-def]
    tasks = [asyncio.ensure_future(coroutine) for coroutine in coroutines]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
