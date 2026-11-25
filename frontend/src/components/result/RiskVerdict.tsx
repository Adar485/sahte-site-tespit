import { CircleDashed, Lightbulb } from 'lucide-react';
import { DEFAULT_RECOMMENDATIONS, MODULE_ORDER, RISK_LABELS } from '../../lib/labels';
import type { AnalysisResult, RiskAssessment, RiskLevel } from '../../types/analysis';
import { TONE_STYLES } from '../risk';
import { Eyebrow } from '../ui';

const BANDS: Array<{ level: RiskLevel; label: string; from: number; to: number }> = [
  { level: 'low', label: 'Düşük', from: 0, to: 39 },
  { level: 'suspicious', label: 'Şüpheli', from: 40, to: 69 },
  { level: 'high', label: 'Yüksek', from: 70, to: 100 },
];

function RiskScale({ risk }: { risk: RiskAssessment }) {
  const score = risk.score;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[13px] font-bold text-ink-soft">Risk puanı</p>
        <p className="tabular-nums text-ink">
          {score === null ? (
            <span className="text-[15px] font-semibold text-ink-muted">Puan yok</span>
          ) : (
            <>
              <span className="text-3xl font-extrabold tracking-tight">{score}</span>
              <span className="text-[15px] font-semibold text-ink-muted"> / 100</span>
            </>
          )}
        </p>
      </div>
      <div className="relative mt-3" role="img" aria-label={
          score === null
            ? `Risk düzeyi: ${RISK_LABELS[risk.level]}. Sayısal puan yok.`
            : `Risk puanı 100 üzerinden ${score}; ${RISK_LABELS[risk.level]} aralığında.`
        }>
        <div className="flex gap-1">
          {BANDS.map((band) => {
            const active = band.level === risk.level;
            return (
              <div key={band.level} className="flex-1" style={{ flexGrow: band.to - band.from + 1 }}>
                <div className={`h-2.5 rounded-full ${active ? TONE_STYLES[band.level].bright : 'bg-line'}`} />
                <p className={`mt-1.5 text-[12px] font-semibold ${active ? TONE_STYLES[band.level].text : 'text-ink-muted'}`}>{band.label}</p>
              </div>
            );
          })}
        </div>
        {score !== null && (
          <span
            aria-hidden
            className="absolute -top-1 h-[18px] w-1.5 -translate-x-1/2 rounded-full border-2 border-card bg-ink"
            style={{ left: `${score}%` }}
          />
        )}
      </div>
      <p className="mt-3 text-[13px] leading-5 text-ink-muted">
        Risk puanı tüm bölümlerin bulgularını birleştirir. Aşağıdaki benzerlik puanlarından ayrıdır ve bir olasılık değildir.
      </p>
    </div>
  );
}

export function partialNote(result: AnalysisResult): string | null {
  if (result.status !== 'partial') return null;
  const completed = MODULE_ORDER.filter((key) => result.modules[key].status === 'completed');
  if (completed.length === 1 && completed[0] === 'url') return 'Yalnızca URL incelenebildi';
  return `${MODULE_ORDER.length} bölümden ${completed.length} tanesi incelenebildi`;
}

export function RiskVerdict({ result, risk }: { result: AnalysisResult; risk: RiskAssessment }) {
  const style = TONE_STYLES[risk.level];
  const Icon = style.icon;
  const partial = partialNote(result);

  return (
    <section aria-labelledby="genel-sonuc" className={`overflow-hidden rounded-2xl border bg-card ${style.border}`}>
      <div className={`h-1.5 ${style.bright}`} aria-hidden />
      <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[1fr_320px] lg:gap-12">
        <div>
          <Eyebrow>Genel değerlendirme</Eyebrow>
          <div className="mt-3 flex items-start gap-4">
            <span className={`inline-flex size-14 shrink-0 items-center justify-center rounded-2xl ${style.soft} ${style.text}`}>
              <Icon aria-hidden className="size-8" strokeWidth={2} />
            </span>
            <div className="min-w-0">
              <h1 id="genel-sonuc" className={`text-[28px] font-extrabold leading-tight tracking-[-0.02em] sm:text-4xl ${style.text}`}>
                {RISK_LABELS[risk.level]}
              </h1>
              {partial && (
                <p className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-paper px-2 py-1 text-[13px] font-semibold text-ink-soft">
                  <CircleDashed aria-hidden className="size-4" />
                  Kısmi analiz: {partial}
                </p>
              )}
            </div>
          </div>
          {risk.summary && <p className="mt-5 max-w-2xl text-[17px] leading-7 text-ink">{risk.summary}</p>}

          <div className="mt-5 flex max-w-2xl gap-3 rounded-xl bg-paper p-4">
            <Lightbulb aria-hidden className="mt-0.5 size-5 shrink-0 text-ink-soft" />
            <div>
              <p className="text-[14px] font-bold text-ink">Ne yapmalısınız?</p>
              <p className="mt-0.5 text-[15px] leading-6 text-ink-soft">
                {risk.recommendation ?? DEFAULT_RECOMMENDATIONS[risk.level]}
              </p>
            </div>
          </div>
        </div>

        <div className="border-t border-line pt-6 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-1">
          <RiskScale risk={risk} />
        </div>
      </div>
    </section>
  );
}
