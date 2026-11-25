import { X } from 'lucide-react';
import { STAGE_LABELS, STAGE_ORDER } from '../lib/labels';
import type { AnalysisStage } from '../types/analysis';
import { StageList, stageStates } from './StageList';
import { ButtonLink, Eyebrow, Panel, UrlText } from './ui';

interface AnalysisProgressProps {
  submittedUrl: string;
  stage?: AnalysisStage;
  /** Tüm aşamalar tamamlandı, sonuç ekranına geçiliyor. */
  completed?: boolean;
}

export function AnalysisProgress({ submittedUrl, stage, completed }: AnalysisProgressProps) {
  const states = stageStates({ current: stage ?? 'url_check', allDone: completed });
  const stepIndex = completed ? STAGE_ORDER.length : STAGE_ORDER.indexOf(stage ?? 'url_check');
  const percent = Math.round((stepIndex / STAGE_ORDER.length) * 100);

  const announcement = completed
    ? 'Analiz tamamlandı. Sonuç hazırlanıyor.'
    : `${STAGE_ORDER.length} adımdan ${stepIndex + 1}. adım: ${STAGE_LABELS[stage ?? 'url_check']}.`;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6 sm:py-16">
      <Panel className="overflow-hidden">
        <div className="relative h-1 bg-paper-deep" aria-hidden>
          <div className="absolute inset-y-0 left-0 bg-teal transition-[width] duration-500" style={{ width: `${percent}%` }} />
          {!completed && (
            <div className="absolute inset-y-0 left-0 w-1/3 bg-linear-to-r from-transparent via-teal-bright/60 to-transparent motion-safe:animate-progress motion-reduce:hidden" />
          )}
        </div>

        <div className="p-6 sm:p-8">
          <Eyebrow className={completed ? 'text-teal-strong' : ''}>{completed ? 'Analiz tamamlandı' : 'Analiz sürüyor'}</Eyebrow>
          <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-ink sm:text-[28px]">
            {completed ? 'Sonuç hazır' : 'Sayfa inceleniyor'}
          </h1>
          <p className="mt-2 text-[15px] leading-6 text-ink-soft">
            <span className="sr-only">İncelenen adres: </span>
            <UrlText url={submittedUrl} className="text-ink" />
          </p>

          <div role="status" aria-live="polite" className="sr-only">
            {announcement}
          </div>

          <div className="mt-7">
            <StageList states={states} />
          </div>

          <div className="mt-8 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[14px] text-ink-muted">Bu işlem genellikle birkaç saniye sürer.</p>
            {!completed && (
              <ButtonLink to="/" variant="ghost" icon={X}>
                Vazgeç
              </ButtonLink>
            )}
          </div>
        </div>
      </Panel>
    </div>
  );
}
