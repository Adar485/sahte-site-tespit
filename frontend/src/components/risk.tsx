import { CircleSlash, Shield, ShieldAlert, ShieldX, type LucideIcon } from 'lucide-react';
import { FAILED_LABEL, RISK_LABELS, RISK_SHORT_LABELS } from '../lib/labels';
import type { RiskLevel } from '../types/analysis';

export type Tone = RiskLevel | 'failed';

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
};

export function toneOf(level: RiskLevel | null): Tone {
  return level ?? 'failed';
}

export function toneLabel(tone: Tone, short = false): string {
  if (tone === 'failed') return short ? 'Tamamlanamadı' : FAILED_LABEL;
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
