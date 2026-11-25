import { formatPercent } from '../../lib/format';
import type { SimilarityMatch } from '../../types/analysis';

/**
 * Benzerlik puanı göstergesi. Risk renklerinden bilinçli olarak ayrı (mavi)
 * tutulur; çünkü benzerlik, sayfanın zararlı olma olasılığı değildir.
 */
export function SimilarityMeter({ match, label }: { match: SimilarityMatch; label?: string }) {
  const percent = Math.round(match.score * 100);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 text-[14px] text-ink-soft">
          {label && <span className="block text-[12px] font-bold uppercase tracking-[0.08em] text-ink-muted">{label}</span>}
          <span className="font-semibold text-ink break-words">{match.reference}</span>
        </p>
        <p className="shrink-0 text-[15px] font-bold tabular-nums text-blue-strong">{formatPercent(match.score)} benzerlik</p>
      </div>
      <div
        role="img"
        aria-label={`${match.reference} ile ${formatPercent(match.score)} benzerlik`}
        className="mt-2 h-2 overflow-hidden rounded-full bg-blue-soft"
      >
        <div className="h-full rounded-full bg-blue" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export function SimilarityNote() {
  return (
    <p className="text-[13px] leading-5 text-ink-muted">
      Benzerlik puanı, sayfanın bir referansa ne kadar benzediğini gösterir. Zararlı olma olasılığı değildir; tek başına risk
      anlamına gelmez.
    </p>
  );
}
