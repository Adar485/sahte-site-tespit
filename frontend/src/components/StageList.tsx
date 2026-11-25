import { Check, Circle, Loader2, Minus, X } from 'lucide-react';
import { STAGE_DESCRIPTIONS, STAGE_LABELS, STAGE_ORDER } from '../lib/labels';
import type { AnalysisStage } from '../types/analysis';

export type StageState = 'pending' | 'active' | 'done' | 'failed' | 'skipped';

const STATE_TEXT: Record<StageState, string> = {
  pending: 'Sırada',
  active: 'Sürüyor',
  done: 'Tamamlandı',
  failed: 'Tamamlanamadı',
  skipped: 'Atlandı',
};

/** Mevcut aşamaya ve (varsa) hataya göre her aşamanın durumunu hesaplar. */
export function stageStates(options: { current?: AnalysisStage; failedAt?: AnalysisStage; allDone?: boolean }): Record<AnalysisStage, StageState> {
  const states = {} as Record<AnalysisStage, StageState>;
  const pivot = options.failedAt ?? options.current;
  const pivotIndex = pivot ? STAGE_ORDER.indexOf(pivot) : -1;

  STAGE_ORDER.forEach((stage, index) => {
    if (options.allDone) states[stage] = 'done';
    else if (index < pivotIndex) states[stage] = 'done';
    else if (index === pivotIndex) states[stage] = options.failedAt ? 'failed' : 'active';
    else states[stage] = options.failedAt ? 'skipped' : 'pending';
  });
  return states;
}

function StageIcon({ state }: { state: StageState }) {
  const base = 'relative z-10 inline-flex size-8 shrink-0 items-center justify-center rounded-full border-2';
  switch (state) {
    case 'done':
      return (
        <span className={`${base} border-teal bg-teal text-white`}>
          <Check aria-hidden className="size-4" strokeWidth={3} />
        </span>
      );
    case 'active':
      return (
        <span className={`${base} border-teal bg-card text-teal`}>
          <Loader2 aria-hidden className="size-4 motion-safe:animate-spin" strokeWidth={2.75} />
        </span>
      );
    case 'failed':
      return (
        <span className={`${base} border-coral bg-coral text-white`}>
          <X aria-hidden className="size-4" strokeWidth={3} />
        </span>
      );
    case 'skipped':
      return (
        <span className={`${base} border-line-strong bg-paper-deep text-ink-muted`}>
          <Minus aria-hidden className="size-4" strokeWidth={2.75} />
        </span>
      );
    default:
      return (
        <span className={`${base} border-line-strong bg-card text-line-strong`}>
          <Circle aria-hidden className="size-2.5 fill-current" />
        </span>
      );
  }
}

export function StageList({ states, compact = false }: { states: Record<AnalysisStage, StageState>; compact?: boolean }) {
  return (
    <ol className="relative">
      {STAGE_ORDER.map((stage, index) => {
        const state = states[stage];
        const isLast = index === STAGE_ORDER.length - 1;
        return (
          <li key={stage} className={`relative flex gap-4 ${isLast ? '' : compact ? 'pb-4' : 'pb-6'}`}>
            {!isLast && (
              <span
                aria-hidden
                className={`absolute left-[15px] top-8 bottom-0 w-0.5 ${state === 'done' ? 'bg-teal' : 'bg-line'}`}
              />
            )}
            <StageIcon state={state} />
            <div className="min-w-0 pt-1">
              <p className="flex flex-wrap items-baseline gap-x-2 text-[15px] font-bold text-ink">
                <span className={state === 'pending' || state === 'skipped' ? 'text-ink-muted' : ''}>{STAGE_LABELS[stage]}</span>
                <span
                  className={[
                    'text-[13px] font-semibold',
                    state === 'active' ? 'text-teal-strong' : state === 'failed' ? 'text-coral' : 'text-ink-muted',
                  ].join(' ')}
                >
                  {STATE_TEXT[state]}
                </span>
              </p>
              {!compact && (state === 'active' || state === 'failed') && (
                <p className="mt-0.5 text-[14px] leading-6 text-ink-muted">{STAGE_DESCRIPTIONS[stage]}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
