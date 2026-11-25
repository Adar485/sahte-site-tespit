import { CircleSlash, Clock, Shield, ShieldAlert, ShieldX, type LucideIcon } from 'lucide-react';
import { FAILED_LABEL, RISK_LABELS, RISK_SHORT_LABELS } from '../lib/labels';
import type { HistoryEntry, RiskLevel } from '../types/analysis';

export type Tone = RiskLevel | 'failed' | 'pending';

interface ToneStyle {
  icon: LucideIcon;
  text: string;
  soft: string;
  bright: string;
  border: string;
}

export const TONE_STYLES: Record<Tone, ToneStyle> = {
  low: { icon: Shield, text: 'text-emerald', soft: 'bg-emerald-soft', bright: 'bg-emerald-bright', border: 'border-emerald/30' },
  suspicious: { icon: ShieldAlert, text: 'text-amber', soft: 'bg-amber-soft', bright: 'bg-amber-bright', border: 'border-amber/30' },
  high: { icon: ShieldX, text: 'text-coral', soft: 'bg-coral-soft', bright: 'bg-coral-bright', border: 'border-coral/30' },
  failed: { icon: CircleSlash, text: 'text-ink-soft', soft: 'bg-paper-deep', bright: 'bg-ink-muted', border: 'border-line-strong' },
  pending: { icon: Clock, text: 'text-blue-strong', soft: 'bg-blue-soft', bright: 'bg-blue', border: 'border-blue/30' },
};

/**
 * Geçmiş kaydının görsel tonu. Risk düzeyi yalnızca gerçekten varsa kullanılır;
 * eksik risk asla "düşük risk" olarak gösterilmez.
 */
export function toneOf(level: RiskLevel | null, status?: HistoryEntry['status']): Tone {
  if (status === 'pending' || status === 'running') return 'pending';
  return level ?? 'failed';
}

export function toneLabel(tone: Tone, short = false): string {
  if (tone === 'failed') return short ? 'Tamamlanamadı' : FAILED_LABEL;
  if (tone === 'pending') return 'Sürüyor';
  return short ? RISK_SHORT_LABELS[tone] : RISK_LABELS[tone];
}

/** Risk düzeyini simge + metin + renk ile birlikte gösteren küçük etiket. */
export function RiskTag({ tone, className = '' }: { tone: Tone; className?: string }) {
  const style = TONE_STYLES[tone];
  const Icon = style.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[13px] font-semibold whitespace-nowrap ${style.soft} ${style.text} ${className}`}
    >
      <Icon aria-hidden className="size-4" strokeWidth={2.25} />
      {toneLabel(tone, true)}
    </span>
  );
}
