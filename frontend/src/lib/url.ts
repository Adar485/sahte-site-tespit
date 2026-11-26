export type UrlValidationError =
  | 'empty'
  | 'too_long'
  | 'whitespace'
  | 'unsupported_scheme'
  | 'backslash'
  | 'credentials_not_allowed'
  | 'malformed'
  | 'invalid_port'
  | 'invalid_host';

export type UrlValidationResult =
  | { ok: true; url: string; wasNormalized: boolean }
  | { ok: false; error: UrlValidationError; scheme?: string };

/*
 * Arka uçtaki parse_url kurallarının tarayıcıdaki karşılığı
 * (backend/app/services/url_inspection/parsing.py). Belirleyici olan arka uçtur.
 * İki tarafın ortak durumları: tests/url_validation_cases.json
 */

const MAX_URL_LENGTH = 2048;
const DEFAULT_PORTS: Record<string, number> = { http: 80, https: 443 };

/** Python'daki boşluk tanımıyla aynı küme (JavaScript'in \s kümesinden biraz farklıdır). */
const SPACE = '[\\t-\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000]';
const OUTER_SPACE = new RegExp(`^${SPACE}+|${SPACE}+$`, 'g');
const ANY_SPACE = new RegExp(SPACE);

/** Tarayıcıda çalıştırılabilen ya da web sayfası olmayan şemalar. */
const NON_WEB_SCHEMES = /^(javascript|data|file|mailto|tel|sms|ftp|ftps|about|blob|vbscript|chrome|ws|wss|ssh|smb):/i;
const EXPLICIT_SCHEME = /^([a-z][a-z0-9+.-]*):\/\//i;
const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;
const FORBIDDEN_IN_HOST = /[\x00-\x20\x7f#/:<>?@[\\\]^|%]/;
const ASCII_LABEL = /^[a-z0-9_-]+$/;
/** IDNA 2008: harf, işaret, rakam, tire ve birkaç istisna. Simge ve noktalama kabul edilmez. */
const IDN_CHARS = /^[\p{L}\p{M}\p{Nd}\-\u00b7\u0375\u05f3\u05f4\u06fd\u06fe\u0f0b\u3007\u30fb\u200c\u200d]+$/u;

/** RFC 3492 punycode çözücü. Geçersiz girdide null döner. */
function decodePunycode(input: string): string | null {
  const output: number[] = [];
  const delimiter = input.lastIndexOf('-');
  for (let index = 0; index < delimiter; index += 1) output.push(input.charCodeAt(index));

  let code = 128;
  let bias = 72;
  let position = 0;
  let index = delimiter > 0 ? delimiter + 1 : 0;
  while (index < input.length) {
    const previous = position;
    let weight = 1;
    for (let k = 36; ; k += 36) {
      if (index >= input.length) return null;
      const char = input.charCodeAt(index++);
      const digit = char >= 48 && char <= 57 ? char - 22 : char >= 97 && char <= 122 ? char - 97 : -1;
      if (digit < 0) return null;
      position += digit * weight;
      if (position > 0x7fffffff) return null;
      const threshold = k <= bias ? 1 : k >= bias + 26 ? 26 : k - bias;
      if (digit < threshold) break;
      weight *= 36 - threshold;
    }
    const length = output.length + 1;
    let delta = Math.floor((position - previous) / (previous === 0 ? 700 : 2));
    delta += Math.floor(delta / length);
    let k = 0;
    while (delta > 455) {
      delta = Math.floor(delta / 35);
      k += 36;
    }
    bias = k + Math.floor((36 * delta) / (delta + 38));
    code += Math.floor(position / length);
    if (code > 0x10ffff) return null;
    position %= length;
    output.splice(position++, 0, code);
  }
  return String.fromCodePoint(...output);
}

/** IDNA 2008 bağlam kuralları (RFC 5892, CONTEXTO). Birleştirici karakterleri URL ayrıştırıcısı denetler. */
function hasValidContext(label: string): boolean {
  const chars = [...label];
  if (/[\u0660-\u0669]/.test(label) && /[\u06f0-\u06f9]/.test(label)) return false;
  return chars.every((char, index) => {
    if (char === '\u00b7') return chars[index - 1] === 'l' && chars[index + 1] === 'l';
    if (char === '\u0375') return /\p{Script=Greek}/u.test(chars[index + 1] ?? '');
    if (char === '\u05f3' || char === '\u05f4') return /\p{Script=Hebrew}/u.test(chars[index - 1] ?? '');
    if (char === '\u30fb') {
      return chars.some((other) => other !== '\u30fb' && /[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}]/u.test(other));
    }
    return true;
  });
}

/** Punycode'dan çözülen ya da Unicode yazılan bir etiketin temel IDNA 2008 denetimi. */
function isValidIdnLabel(label: string): boolean {
  return (
    /[^\x00-\x7f]/.test(label) &&
    IDN_CHARS.test(label) &&
    label === label.normalize('NFC') &&
    // Büyük harf ve uyumluluk karakterleri çözülmüş etikette bulunamaz. Çeroki harfleri
    // istisnadır: IDNA 2008 büyük biçimlerini kabul eder.
    [...label].every((char) => /[\u13a0-\u13f5]/.test(char) || char === char.normalize('NFKC').toLowerCase().normalize('NFKC')) &&
    hasValidContext(label) &&
    !label.startsWith('-') &&
    !label.endsWith('-') &&
    label.slice(2, 4) !== '--' &&
    !/^\p{M}/u.test(label)
  );
}

/** Köşeli parantezsiz ana makineyi ASCII biçimine çevirir; geçersizse null. */
function parseHost(rawHost: string): string | null {
  let host: string;
  try {
    host = new URL(`http://${rawHost}/`).hostname; // UTS #46 eşlemesi, % çözme, IPv4 biçimleri
  } catch {
    return null;
  }
  host = host.replace(/\.$/, '');
  if (!host || FORBIDDEN_IN_HOST.test(host)) return null;
  if (IPV4.test(host)) return host;

  const labels = host.split('.');
  let top = '';
  for (const label of labels) {
    if (label.length < 1 || label.length > 63 || !ASCII_LABEL.test(label)) return null;
    top = label;
    if (label.startsWith('xn--')) {
      const decoded = decodePunycode(label.slice(4));
      if (label.endsWith('-') || decoded === null || !isValidIdnLabel(decoded)) return null;
    }
  }
  if (labels.length < 2 || host.length > 253 || host.startsWith('-')) return null;
  return top.startsWith('xn--') || /^[a-z]{2,}$/.test(top) ? host : null;
}

/**
 * Kullanıcının girdiği metni doğrular ve normalleştirilmiş http(s) adresine dönüştürür.
 * Şemasız girişler ("ornek.com/giris") https:// ile tamamlanır. Yol, sorgu ve parça
 * yazıldığı gibi korunur.
 */
export function normalizeUrl(input: string): UrlValidationResult {
  const fail = (error: UrlValidationError, scheme?: string): UrlValidationResult => ({ ok: false, error, scheme });
  const value = input.replace(OUTER_SPACE, '');

  if (value.length === 0) return fail('empty');
  if ([...value].length > MAX_URL_LENGTH) return fail('too_long');
  if (ANY_SPACE.test(value)) return fail('whitespace');
  if (/[\p{Cc}\p{Cs}]/u.test(value)) return fail('malformed');

  const explicit = value.match(EXPLICIT_SCHEME);
  const named = explicit ?? value.match(NON_WEB_SCHEMES);
  if (named && !(explicit && /^https?$/i.test(named[1]))) return fail('unsupported_scheme', named[1].toLowerCase());
  if (value.split(/[?#]/)[0].includes('\\')) return fail('backslash');
  if (!explicit && /^https?:/i.test(value)) return fail('malformed'); // "https:host", "https:/host"

  const candidate = explicit ? value : `https://${value.replace(/^\/\//, '')}`;
  const scheme = candidate.slice(0, candidate.indexOf(':')).toLowerCase();
  const rest = candidate.slice(candidate.indexOf('://') + 3);
  const authority = rest.split(/[/?#]/)[0];

  if (authority.includes('@')) return fail('credentials_not_allowed');
  if (!authority || authority.includes('[') !== authority.includes(']')) return fail('malformed');
  // Uyumluluk karakterleri ayraca dönüşüyorsa (ör. tam genişlikte "/") adres belirsizdir.
  const plain = authority.replace(/[:#?@]/g, '');
  if (/[/?#@:]/.test(plain.normalize('NFKC')) && plain !== plain.normalize('NFKC')) return fail('malformed');

  let rawHost: string;
  let portText = '';
  const bracketed = authority.startsWith('[');
  if (bracketed) {
    const closing = authority.indexOf(']');
    const after = authority.slice(closing + 1);
    if (after && !after.startsWith(':')) return fail('malformed');
    rawHost = authority.slice(1, closing);
    portText = after.slice(1);
  } else {
    const parts = authority.split(':');
    if (parts.length > 2) return fail('invalid_host'); // IPv6 köşeli parantez ister
    rawHost = parts[0];
    portText = parts[1] ?? '';
  }

  let port: number | null = null;
  if (portText) {
    port = Number(portText);
    if (!/^[0-9]{1,5}$/.test(portText) || port < 1 || port > 65535) return fail('invalid_port');
  }

  let host: string | null;
  if (bracketed) {
    try {
      host = rawHost.includes('%') ? null : new URL(`http://[${rawHost}]/`).hostname;
    } catch {
      host = null;
    }
  } else {
    host = parseHost(rawHost);
  }
  if (!host) return fail('invalid_host');

  const tail = rest.slice(authority.length);
  const hashAt = tail.indexOf('#');
  const beforeHash = hashAt < 0 ? tail : tail.slice(0, hashAt);
  const fragment = hashAt < 0 ? '' : tail.slice(hashAt + 1);
  const queryAt = beforeHash.indexOf('?');
  const path = queryAt < 0 ? beforeHash : beforeHash.slice(0, queryAt);
  const query = queryAt < 0 ? '' : beforeHash.slice(queryAt + 1);

  const portPart = port !== null && port !== DEFAULT_PORTS[scheme] ? `:${port}` : '';
  const url = `${scheme}://${host}${portPart}${path || '/'}${query ? `?${query}` : ''}${fragment ? `#${fragment}` : ''}`;
  return { ok: true, url, wasNormalized: !explicit };
}

export function validationMessage(result: Extract<UrlValidationResult, { ok: false }>): string {
  switch (result.error) {
    case 'empty':
      return 'İncelemek istediğiniz web adresini yazın.';
    case 'too_long':
      return 'Bu adres çok uzun. En fazla 2048 karakterlik adresler incelenebilir.';
    case 'whitespace':
      return 'Adres boşluk içeremez. Bağlantıyı kopyalayıp olduğu gibi yapıştırmayı deneyin.';
    case 'unsupported_scheme':
      return `“${result.scheme}:” adresleri desteklenmiyor. Yalnızca http:// veya https:// ile başlayan web adresleri incelenebilir.`;
    case 'backslash':
      return 'Adreste ters eğik çizgi (\\) kullanılamaz; “/” kullanın.';
    case 'credentials_not_allowed':
      return 'Kullanıcı adı veya parola içeren adresler kabul edilmiyor. “@” öncesindeki giriş bilgilerini kaldırın.';
    case 'malformed':
      return 'Bu bir web adresine benzemiyor. Örneğin “ornek.com” ya da “https://ornek.com/giris” biçiminde yazın.';
    case 'invalid_port':
      return 'Port numarası geçersiz. 1 ile 65535 arasında bir sayı olmalıdır.';
    case 'invalid_host':
      return 'Alan adı eksik ya da hatalı görünüyor. “ornek.com” gibi uzantısıyla birlikte yazın.';
  }
}

/** Ekranda gösterim için kısa adres: şema ve sondaki eğik çizgi atılır. */
export function displayUrl(url: string): string {
  return url.replace(/^https?:\/\//i, '').replace(/\/$/, '');
}

export function hostnameOf(url: string): string {
  try {
    return new URL(/^https?:/i.test(url) ? url : `https://${url.replace(/^\/\//, '')}`).hostname;
  } catch {
    return url;
  }
}
