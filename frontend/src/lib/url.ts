export type UrlValidationError = 'empty' | 'too_long' | 'whitespace' | 'unsupported_scheme' | 'malformed' | 'invalid_host';

export type UrlValidationResult =
  | { ok: true; url: string; wasNormalized: boolean }
  | { ok: false; error: UrlValidationError; scheme?: string };

const MAX_URL_LENGTH = 2048;

/** Tarayıcıda çalıştırılabilen ya da web sayfası olmayan şemalar. */
const NON_WEB_SCHEMES = /^(javascript|data|file|mailto|tel|sms|ftp|ftps|about|blob|vbscript|chrome|ws|wss|ssh|smb):/i;
const EXPLICIT_SCHEME = /^([a-z][a-z0-9+.-]*):\/\//i;
const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;
/** En az bir nokta ve harflerden (ya da punycode) oluşan bir üst düzey alan adı. */
const DOMAIN = /^(?!-)[\p{L}\p{N}-]+(\.[\p{L}\p{N}-]+)*\.(\p{L}{2,}|xn--[a-z0-9-]+)\.?$/u;

/**
 * Kullanıcının girdiği metni doğrular ve http(s) adresine dönüştürür.
 * Şemasız girişler ("ornek.com/giris") https:// ile tamamlanır.
 */
export function normalizeUrl(input: string): UrlValidationResult {
  const value = input.trim();

  if (value.length === 0) return { ok: false, error: 'empty' };
  if (value.length > MAX_URL_LENGTH) return { ok: false, error: 'too_long' };
  if (/\s/.test(value)) return { ok: false, error: 'whitespace' };

  const nonWeb = value.match(NON_WEB_SCHEMES);
  if (nonWeb) return { ok: false, error: 'unsupported_scheme', scheme: nonWeb[1].toLowerCase() };

  const explicit = value.match(EXPLICIT_SCHEME);
  if (explicit && !/^https?$/i.test(explicit[1])) {
    return { ok: false, error: 'unsupported_scheme', scheme: explicit[1].toLowerCase() };
  }

  let candidate = value;
  let wasNormalized = false;
  if (!explicit) {
    candidate = `https://${value.replace(/^\/\//, '')}`;
    wasNormalized = true;
  }

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    return { ok: false, error: 'malformed' };
  }

  const host = parsed.hostname;
  if (!host) return { ok: false, error: 'malformed' };

  const isIp = IPV4.test(host) || host.startsWith('[');
  // URL ayrıştırıcısı Unicode alan adlarını punycode'a çevirir; bu yüzden ikisi de kabul edilir.
  if (!isIp && !DOMAIN.test(host)) return { ok: false, error: 'invalid_host' };

  return { ok: true, url: parsed.href, wasNormalized };
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
    case 'malformed':
      return 'Bu bir web adresine benzemiyor. Örneğin “ornek.com” ya da “https://ornek.com/giris” biçiminde yazın.';
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
    return new URL(url).hostname;
  } catch {
    return url;
  }
}
