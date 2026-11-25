import { ArrowLeft, FileX, History, Hourglass, Loader2, RotateCcw, ScanSearch, ServerOff } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { AnalysisProgress } from '../components/AnalysisProgress';
import { FailedVerdict } from '../components/result/FailedVerdict';
import { KeyFindings } from '../components/result/KeyFindings';
import { ModuleTabs } from '../components/result/ModuleTabs';
import { ResultMeta } from '../components/result/ResultMeta';
import { RiskVerdict } from '../components/result/RiskVerdict';
import { StatePanel } from '../components/StatePanel';
import { Button, ButtonLink, Panel } from '../components/ui';
import { useAnalysisJob } from '../hooks/useAnalysisJob';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useStartAnalysis } from '../hooks/useStartAnalysis';
import { FAILED_LABEL, RISK_LABELS } from '../lib/labels';
import { hostnameOf } from '../lib/url';
import type { AnalysisResult } from '../types/analysis';

export function ResultPage() {
  const { id = '' } = useParams();
  const { view, retry } = useAnalysisJob(id);

  const title =
    view.phase === 'done'
      ? `${view.result.risk ? RISK_LABELS[view.result.risk.level] : FAILED_LABEL} · ${hostnameOf(view.result.submittedUrl)}`
      : view.phase === 'error'
        ? 'Sonuç açılamadı'
        : 'Analiz sürüyor';
  useDocumentTitle(title);

  switch (view.phase) {
    case 'loading':
      return (
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-20 text-ink-soft sm:px-6" role="status">
          <Loader2 aria-hidden className="size-5 motion-safe:animate-spin" />
          Sonuç yükleniyor…
        </div>
      );
    case 'running':
      return <AnalysisProgress submittedUrl={view.submittedUrl} stage={view.stage} />;
    case 'finishing':
      return <AnalysisProgress submittedUrl={view.result.submittedUrl} completed />;
    case 'error':
      return (
        <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6 sm:py-20">
          <Panel className="p-6 sm:p-8">
            {view.error.code === 'not_found' ? (
              <StatePanel
                headingLevel="h1"
                icon={FileX}
                title="Sonuç bulunamadı"
                actions={
                  <>
                    <ButtonLink to="/" icon={ScanSearch}>
                      Yeni analiz başlat
                    </ButtonLink>
                    <ButtonLink to="/gecmis" variant="secondary" icon={History}>
                      Geçmişe dön
                    </ButtonLink>
                  </>
                }
              >
                <p>{view.error.message}</p>
              </StatePanel>
            ) : (
              <StatePanel
                alert
                headingLevel="h1"
                tone="warning"
                icon={view.error.code === 'client_timeout' ? Hourglass : ServerOff}
                title={
                  view.error.code === 'client_timeout'
                    ? 'Sonuç henüz hazır değil'
                    : view.error.code === 'request_timeout'
                      ? 'Sunucu zamanında yanıt vermedi'
                      : 'Analiz servisine ulaşılamıyor'
                }
                actions={
                  <>
                    <Button icon={RotateCcw} onClick={retry}>
                      {view.error.code === 'client_timeout' ? 'Yeniden kontrol et' : 'Yeniden dene'}
                    </Button>
                    <ButtonLink to="/" variant="secondary" icon={ArrowLeft}>
                      Ana sayfaya dön
                    </ButtonLink>
                  </>
                }
              >
                <p>{view.error.message}</p>
              </StatePanel>
            )}
          </Panel>
        </div>
      );
    case 'done':
      // key: başka bir analize geçildiğinde sekme vb. iç durum sıfırlanır.
      return <ResultView key={view.result.id} result={view.result} />;
  }
}

function ResultView({ result }: { result: AnalysisResult }) {
  const restart = useStartAnalysis();
  const anyModuleCompleted = Object.values(result.modules).some((module) => module.status === 'completed');

  const rerunButton = (variant: 'primary' | 'secondary') => (
    <Button variant={variant} icon={RotateCcw} loading={restart.pending} onClick={() => restart.start(result.submittedUrl)}>
      {result.status === 'failed' ? 'Yeniden dene' : 'Yeniden analiz et'}
    </Button>
  );

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6 sm:pt-8">
      <nav aria-label="Sonuç işlemleri" className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <ButtonLink to="/" variant="ghost" icon={ArrowLeft} className="-ml-3">
          Yeni analiz
        </ButtonLink>
        <div className="flex flex-wrap gap-2">
          {result.status !== 'failed' && rerunButton('secondary')}
          <ButtonLink to="/gecmis" variant="secondary" icon={History}>
            Geçmiş
          </ButtonLink>
        </div>
      </nav>

      {restart.error && (
        <div className="mb-6 rounded-2xl border border-amber/30 bg-amber-soft/50 p-5">
          <StatePanel alert tone="warning" icon={ServerOff} title="Analiz yeniden başlatılamadı" actions={
            <Button variant="secondary" onClick={restart.reset}>Kapat</Button>
          }>
            <p>{restart.error.message}</p>
          </StatePanel>
        </div>
      )}

      <div className="space-y-6">
        {result.risk ? (
          <RiskVerdict result={result} risk={result.risk} />
        ) : (
          <FailedVerdict
            failure={result.failure ?? { code: 'unknown', stage: 'scoring', message: 'Analiz sonucu oluşturulamadı.' }}
            actions={
              <>
                {rerunButton('primary')}
                <ButtonLink to={`/?url=${encodeURIComponent(result.submittedUrl)}`} variant="secondary" icon={ScanSearch}>
                  Adresi düzenle
                </ButtonLink>
              </>
            }
          />
        )}

        <ResultMeta result={result} />

        {result.risk && <KeyFindings result={result} />}
      </div>

      {anyModuleCompleted && (
        <div className="mt-12">
          <ModuleTabs result={result} />
        </div>
      )}

      {result.isDemo && (
        <p className="mt-10 border-t border-line pt-5 text-[13px] leading-5 text-ink-muted">
          Bu sonuç örnek veriden üretildi; girilen adres gerçekten incelenmedi.
        </p>
      )}
    </div>
  );
}
