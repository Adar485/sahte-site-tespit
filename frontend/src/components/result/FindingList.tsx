import { AlertOctagon, AlertTriangle, Info, CircleAlert } from 'lucide-react';
import { SEVERITY_LABELS } from '../../lib/labels';
import type { Finding, FindingSeverity } from '../../types/analysis';

const SEVERITY_STYLES: Record<FindingSeverity, { icon: typeof Info; className: string }> = {
  high: { icon: AlertOctagon, className: 'bg-coral-soft text-coral' },
  medium: { icon: AlertTriangle, className: 'bg-amber-soft text-amber' },
  low: { icon: CircleAlert, className: 'bg-paper-deep text-ink-soft' },
  info: { icon: Info, className: 'bg-blue-soft text-blue-strong' },
};

export const SEVERITY_RANK: Record<FindingSeverity, number> = { high: 3, medium: 2, low: 1, info: 0 };

export function FindingItem({ finding, context }: { finding: Finding; context?: string }) {
  const style = SEVERITY_STYLES[finding.severity];
  const Icon = style.icon;
  return (
    <li className="flex gap-3.5 py-4 first:pt-0 last:pb-0">
      <span className={`inline-flex size-8 shrink-0 items-center justify-center rounded-lg ${style.className}`}>
        <Icon aria-hidden className="size-[17px]" strokeWidth={2.25} />
      </span>
      <div className="min-w-0">
        <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-ink-muted">
          {SEVERITY_LABELS[finding.severity]}
          {context && <span className="font-semibold normal-case tracking-normal"> · {context}</span>}
        </p>
        <h4 className="mt-0.5 text-[15px] font-bold text-ink">{finding.title}</h4>
        {/* Bitişik harfler kapalı: "xn--" tek bir tire gibi görünmemeli. */}
        <p className="mt-1 text-[15px] leading-6 text-ink-soft break-words [font-variant-ligatures:none]">{finding.description}</p>
      </div>
    </li>
  );
}

export function FindingList({ findings, emptyText }: { findings: Finding[]; emptyText?: string }) {
  if (findings.length === 0) {
    return <p className="text-[15px] text-ink-muted">{emptyText ?? 'Bu bölümde dikkat çeken bir bulgu yok.'}</p>;
  }
  const sorted = [...findings].sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity]);
  return (
    <ul className="divide-y divide-line">
      {sorted.map((finding) => (
        <FindingItem key={finding.id} finding={finding} />
      ))}
    </ul>
  );
}
