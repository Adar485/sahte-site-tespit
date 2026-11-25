const dateTime = new Intl.DateTimeFormat('tr-TR', { dateStyle: 'long', timeStyle: 'short' });
const shortDate = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' });
const time = new Intl.DateTimeFormat('tr-TR', { hour: '2-digit', minute: '2-digit' });

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

export function formatShortDate(iso: string): string {
  return shortDate.format(new Date(iso));
}

export function formatTime(iso: string): string {
  return time.format(new Date(iso));
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toLocaleString('tr-TR', { maximumFractionDigits: 1 })} sn`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return rest ? `${minutes} dk ${rest} sn` : `${minutes} dk`;
}

/** 0–1 aralığındaki değeri Türkçe yüzde biçimine çevirir: 0.92 -> "%92" */
export function formatPercent(value: number): string {
  return `%${Math.round(value * 100)}`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString('tr-TR');
}
