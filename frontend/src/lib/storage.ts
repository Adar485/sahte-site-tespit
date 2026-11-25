/** localStorage erişimi; gizli pencere ya da dolu depolama gibi durumlarda sessizce geri çekilir. */
export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Depolama kullanılamıyorsa uygulama bellek içi verilerle çalışmaya devam eder.
  }
}

export function removeKey(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // yoksay
  }
}
