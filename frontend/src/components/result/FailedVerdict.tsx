import { CircleSlash, Timer, Unplug, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import type { AnalysisFailure } from '../../types/analysis';
import { StageList, stageStates } from '../StageList';
import { Eyebrow } from '../ui';

const FAILURE_COPY: Record<AnalysisFailure['code'], { title: string; icon: LucideIcon; hint: string }> = {
  unreachable: {
    title: 'Sayfaya ulaşılamadı',
    icon: Unplug,
    hint: 'Adresi doğru yazdığınızdan emin olun. Site kapanmış ya da geçici olarak erişilemez olabilir.',
  },
  timeout: {
    title: 'Sayfa zamanında yanıt vermedi',
    icon: Timer,
    hint: 'Birkaç dakika sonra yeniden deneyebilirsiniz. Yanıt vermeyen bir sayfa da dikkatle ele alınmalıdır.',
  },
  service_unavailable: {
    title: 'Analiz servisi kullanılamıyor',
    icon: CircleSlash,
    hint: 'Sorun bu adresten değil, analiz servisinden kaynaklanıyor. Servis hazır olduğunda adresi yeniden analiz edebilirsiniz.',
  },
  unknown: {
    title: 'Beklenmeyen bir sorun oluştu',
    icon: CircleSlash,
    hint: 'Analizi yeniden başlatmayı deneyin.',
  },
};

export function FailedVerdict({ failure, actions }: { failure: AnalysisFailure; actions: ReactNode }) {
  const copy = FAILURE_COPY[failure.code];
  const Icon = copy.icon;
  return (
    <section aria-labelledby="genel-sonuc" className="overflow-hidden rounded-2xl border border-line-strong bg-card">
      <div className="h-1.5 bg-ink-muted" aria-hidden />
      <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[1fr_320px] lg:gap-12">
        <div>
          <Eyebrow>Genel değerlendirme</Eyebrow>
          <div className="mt-3 flex items-start gap-4">
            <span className="inline-flex size-14 shrink-0 items-center justify-center rounded-2xl bg-paper-deep text-ink-soft">
              <Icon aria-hidden className="size-8" strokeWidth={2} />
            </span>
            <div>
              <h1 id="genel-sonuc" className="text-[28px] font-extrabold leading-tight tracking-[-0.02em] text-ink sm:text-4xl">
                Analiz tamamlanamadı
              </h1>
              <p className="mt-1 text-[16px] font-bold text-ink-soft">{copy.title}</p>
            </div>
          </div>
          <p className="mt-5 max-w-2xl text-[17px] leading-7 text-ink">{failure.message}</p>
          <p className="mt-2 max-w-2xl text-[15px] leading-6 text-ink-soft">{copy.hint}</p>
          <p className="mt-2 max-w-2xl text-[15px] leading-6 text-ink-soft">
            Bu sayfa için risk değerlendirmesi yapılmadı. Bu, sayfanın güvenli ya da tehlikeli olduğu anlamına gelmez.
          </p>
          <div className="mt-6 flex flex-wrap gap-2.5">{actions}</div>
        </div>

        <div className="border-t border-line pt-6 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-1">
          <p className="mb-4 text-[13px] font-bold text-ink-soft">İlerleme</p>
          <StageList states={stageStates({ failedAt: failure.stage })} compact />
        </div>
      </div>
    </section>
  );
}
