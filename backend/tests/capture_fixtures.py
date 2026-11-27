"""Local fixture servers for capture tests.

The browser reaches the fixture only as "fixture.test", through an explicit
test_destinations entry. The "private" server stands for an internal service: it
has no such entry, and every request that reaches it is recorded.
"""

import base64
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==")


def page(body: str, title: str = "Fixture") -> bytes:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body>{body}</body></html>".encode()


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):  # aborted connections are expected
        pass


class Fixtures:
    def __init__(self) -> None:
        self.private_hits: list[str] = []
        self.public_requests: list[tuple[str, str]] = []
        fixtures = self

        class Private(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                fixtures.private_hits.append(f"{self.command} {self.path}")
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(page("PRIVATE SERVICE DATA"))

            do_POST = do_OPTIONS = do_HEAD = do_GET

        class Public(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, body: bytes, status: int = 200, headers: dict | None = None, content_type="text/html; charset=utf-8"):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                fixtures.public_requests.append(("POST", self.path))
                self.reply(page("form was submitted"))

            def do_GET(self):
                fixtures.public_requests.append(("GET", self.path))
                path = self.path.split("?")[0]
                private = f"127.0.0.1:{fixtures.private_port}"
                if path == "/":
                    self.reply(page(
                        "<h1>Statik başlık — çğıöşü</h1><div id='app'></div><p style='display:none'>gizli metin</p>"
                        "<script>setTimeout(() => document.getElementById('app').textContent = 'JavaScript ile eklenen içerik', 700)</script>",
                        "Fixture sayfası",
                    ))
                elif path == "/redirect":
                    self.reply(b"", 302, {"Location": "/landing?x=1"})
                elif path == "/js-redirect":
                    self.reply(page("<script>location.replace('/landing')</script>"))
                elif path == "/landing":
                    self.reply(page("<h1>Varış sayfası</h1>"))
                elif path == "/loop":
                    self.reply(b"", 302, {"Location": "/loop"})
                elif path.startswith("/to/"):  # redirect to an arbitrary absolute URL
                    self.reply(b"", 302, {"Location": self.path[len("/to/"):]})
                elif path.startswith("/jsto/"):
                    self.reply(page(f"<p>önce</p><script>setTimeout(() => location.href = '{self.path[len('/jsto/'):]}', 50)</script>"))
                elif path == "/probe":
                    targets = [private, f"localhost:{fixtures.private_port}", f"[::1]:{fixtures.private_port}"]
                    tags = "".join(
                        f"<img src='http://{t}/img'><iframe src='http://{t}/frame'></iframe><script src='http://{t}/script'></script>"
                        f"<link rel='stylesheet' href='http://{t}/css'><link rel='preconnect' href='http://{t}/'>"
                        for t in targets
                    )
                    self.reply(page(
                        "<h1>Sondaj sayfası</h1><div id='out'></div>" + tags +
                        f"""<form id='f' method='post' action='/submit'><input name='a' value='1'></form>
<script>
fetch('http://{private}/fetch', {{mode: 'no-cors'}}).catch(() => {{}});
navigator.sendBeacon('http://{private}/beacon', 'x');
try {{ new WebSocket('ws://{private}/ws'); }} catch (e) {{}}
try {{ new WebSocket('ws://fixture.test:{fixtures.port}/ws-public'); }} catch (e) {{}}
window.open('http://{private}/popup'); window.open('/popup-public');
const a = document.createElement('a'); a.href = 'http://{private}/anchor'; a.target = '_blank'; document.body.append(a); a.click();
new Worker(URL.createObjectURL(new Blob(["fetch('http://{private}/worker',{{mode:'no-cors'}}).catch(()=>{{}})"])));
document.getElementById('out').textContent = 'rtc=' + typeof RTCPeerConnection + ' transport=' + typeof WebTransport;
setTimeout(() => document.getElementById('f').submit(), 100);
</script>"""
                    ))
                elif path == "/download":
                    self.reply(b"MZ binary", headers={"Content-Disposition": "attachment; filename=a.exe"}, content_type="application/octet-stream")
                elif path == "/auto-download":
                    self.reply(page("<p>indirme denemesi</p><a id='d' href='/download' download>x</a><script>document.getElementById('d').click()</script>"))
                elif path == "/json":
                    self.reply(b'{"a":1}', content_type="application/json")
                elif path == "/slow":
                    time.sleep(8)
                    self.reply(page("late"))
                elif path == "/never-load":
                    self.reply(page("<p>içerik hazır</p><img src='/slow'>"))
                elif path == "/freeze":
                    self.reply(page("<p>önce</p><script>addEventListener('load', () => setTimeout(() => { for (;;) {} }, 50))</script>"))
                elif path == "/changing":
                    self.reply(page("<p>adres sürekli değişiyor</p><script>let n = 0; setInterval(() => history.replaceState(null, '', '?n=' + (n++)), 20)</script>"))
                elif path == "/visual":
                    self.reply(page(
                        "<style>body{margin:0;background:#fff}.b{position:absolute;left:0;width:200px;height:100px} /* STYLE_SOURCE_MARKER */"
                        ".v{visibility:hidden}</style>"
                        "<div class='b' style='top:0;background:rgb(200,0,0)'></div>"
                        "<main style='position:absolute;left:300px;top:20px;width:900px'><h1>Bilinen başlık</h1><p>Gövde metni burada.</p>"
                        "<p>Çağrı İstanbul ışık — Ünicode: 日本語 · العربية · Ω · 🔒</p><div id='late'></div></main>"
                        "<p style='display:none'>display-none içerik</p><p class='v'>görünmez içerik</p><noscript>noscript içerik</noscript>"
                        "<script>/* SCRIPT_SOURCE_MARKER */ setTimeout(() => {"
                        "const b = document.createElement('div'); b.className = 'b'; b.style.cssText = 'top:200px;background:rgb(0,0,200)';"
                        "document.body.append(b); document.getElementById('late').textContent = 'Betikle eklenen paragraf'; }, 600)</script>"
                    ))
                elif path == "/hidden-body":
                    self.reply(page("<h1>Gizli</h1><script>var SCRIPT_SOURCE_MARKER = 1</script><style>body{display:none}</style>"))
                elif path == "/hidden-root":
                    self.reply(page("<p>x</p><script>var SCRIPT_SOURCE_MARKER = 1</script><style>html{display:none}</style>"))
                elif path == "/override-slice":
                    self.reply(page("<p>" + "a" * 3000 + "</p><script>String.prototype.slice = function () { return String(this).repeat(20) }</script>"))
                elif path.startswith("/chain/"):
                    step = int(path.rsplit("/", 1)[1])
                    self.reply(b"", 302, {"Location": f"/chain/{step - 1}" if step else "/landing"})
                elif path.startswith("/empty/"):
                    self.reply(b"", int(path.rsplit("/", 1)[1]))
                elif path == "/pdf":
                    self.reply(b"%PDF-1.4\n%%EOF", content_type="application/pdf")
                elif path == "/stall":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(page("<h1>Yarım gövde</h1>") + b" " * 4096)
                    self.wfile.flush()
                    time.sleep(8)
                elif path == "/worker-sockets":
                    base = f"ws://fixture.test:{fixtures.port}/socket-"
                    self.reply(page(
                        f"""<p>soket</p><script>
const code = (kind) => URL.createObjectURL(new Blob(["try {{ new WebSocket('{base}" + kind + "') }} catch (e) {{}}"]));
new Worker(code('worker')); new SharedWorker(code('shared'));
const frame = document.createElement('iframe'); document.documentElement.append(frame);
try {{ new frame.contentWindow.WebSocket('{base}frame') }} catch (e) {{}}
try {{ new WebSocket('{base}page') }} catch (e) {{}}
</script>"""
                    ))
                elif path == "/xss":
                    self.reply(page(
                        "<p>&lt;img src=x onerror=\"window.__pwned=1\"&gt; &lt;script&gt;window.__pwned=2&lt;/script&gt;</p>"
                        "<p>&lt;a href=\"https://attacker.example.net/\"&gt;tıkla&lt;/a&gt;</p>"
                        "<img src='/image.png'>",
                        "&lt;img src=x onerror=window.__pwned=3&gt;",
                    ))
                elif path == "/notfound":
                    self.reply(page("<h1>Yok</h1>"), 404)
                elif path == "/blank":
                    self.reply(page(""))
                elif path == "/captcha":
                    self.reply(page("<p>Doğrulama</p><div class='g-recaptcha' data-sitekey='x'></div>"))
                elif path == "/big":
                    self.reply(page("<p>" + "kelime " * 60_000 + "</p>"))
                elif path == "/echo-state":
                    cookie = self.headers.get("Cookie", "yok")
                    self.reply(page(f"<p>cookie={cookie}</p>"), headers={"Set-Cookie": "visit=1; Path=/"})
                elif path == "/image.png":
                    self.reply(PNG, content_type="image/png")
                else:
                    self.reply(page("bulunamadı"), 404)

        self._servers = [_Server(("127.0.0.1", 0), Public), _Server(("127.0.0.1", 0), Private)]
        self.port, self.private_port = (server.server_address[1] for server in self._servers)
        for server in self._servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def url(self, path: str = "/") -> str:
        return f"http://fixture.test:{self.port}{path}"

    def close(self) -> None:
        for server in self._servers:
            server.shutdown()
            server.server_close()
