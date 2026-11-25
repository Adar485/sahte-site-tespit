import { RotateCcw, ServerOff } from 'lucide-react';
import { useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DemoScenarioList } from '../components/DemoScenarioList';
import { StatePanel } from '../components/StatePanel';
import { Button, Eyebrow } from '../components/ui';
import { UrlForm, type UrlFormHandle } from '../components/UrlForm';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useStartAnalysis } from '../hooks/useStartAnalysis';
import { STAGE_DESCRIPTIONS } from '../lib/labels';
import { isDemoMode } from '../services';

const CHECKS = [
  { title: 'Adres', text: 'Alan adının yazımı, başka adlara benzerliği ve yönlendirmeler.' },
  { title: 'Görünüm', text: 'Sayfanın ekran görüntüsü, bilinen sayfalarla karşılaştırılır.' },
  { title: 'Metin', text: 'Parola, ödeme ya da acele işlem isteyen ifadeler.' },
  { title: 'HTML yapısı', text: 'Formların verileri nereye gönderdiği, gizli öğeler ve betikler.' },
];

export function AnalyzePage() {
  useDocumentTitle();
  const [params] = useSearchParams();
  const formRef = useRef<UrlFormHandle>(null);
  const { start, pending, error, reset } = useStartAnalysis();
  const [lastUrl, setLastUrl] = useState<string | null>(null);

  const submit = (url: string) => {
    setLastUrl(url);
    start(url);
  };

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 sm:pt-16 lg:pt-20">
      <div className="max-w-3xl">
        <Eyebrow className="text-teal-strong">Phishing risk değerlendirmesi</Eyebrow>
        <h1 className="mt-3 text-[34px] font-extrabold leading-[1.08] tracking-[-0.025em] text-ink sm:text-5xl lg:text-[56px]">
          Şüphelendiğiniz bağlantıyı açmadan önce kontrol edin.
        </h1>
        <p className="mt-4 max-w-2xl text-[17px] leading-7 text-ink-soft">
          Web adresini girin; adresi, sayfanın görünümünü, metnini ve HTML yapısını inceleyip phishing riskine dair bir
          değerlendirme hazırlayalım.
        </p>
      </div>

      <div className="mt-8 max-w-3xl rounded-2xl border border-line bg-card p-5 shadow-[0_1px_0_rgb(15_30_61/0.04),0_12px_32px_-20px_rgb(15_30_61/0.25)] sm:mt-10 sm:p-7">
        <UrlForm
          ref={formRef}
          initialValue={params.get('url') ?? ''}
          submitting={pending}
          onSubmit={submit}
          onChange={() => error && reset()}
        />

        {pending && (
          <p role="status" className="sr-only">
            Analiz başlatılıyor, lütfen bekleyin.
          </p>
        )}

        {error && !pending && (
          <div className="mt-2 border-t border-line pt-5">
            <StatePanel
              alert
              icon={ServerOff}
              tone="warning"
              title={error.code === 'service_unavailable' ? 'Analiz servisine ulaşılamıyor' : 'Analiz başlatılamadı'}
              actions={
                <>
                  <Button icon={RotateCcw} variant="secondary" onClick={() => lastUrl && start(lastUrl)} disabled={!lastUrl}>
                    Yeniden dene
                  </Button>
                  {isDemoMode && (
                    <Button
                      variant="ghost"
                      onClick={() => {
                        reset();
                        document.getElementById('demo-adresleri')?.scrollIntoView({ block: 'center' });
                        (document.querySelector('#demo-adresleri ~ ul button') as HTMLButtonElement | null)?.focus({
                          preventScroll: true,
                        });
                      }}
                    >
                      Örnek adresleri göster
                    </Button>
                  )}
                </>
              }
            >
              <p>{error.message}</p>
            </StatePanel>
          </div>
        )}
      </div>

      <div className="mt-14 grid grid-cols-[minmax(0,1fr)] gap-10 lg:mt-20 lg:grid-cols-[1.1fr_1fr] lg:gap-14">
        <section aria-labelledby="neler-inceleniyor">
          <Eyebrow>Nasıl çalışır</Eyebrow>
          <h2 id="neler-inceleniyor" className="mt-1 text-2xl font-bold tracking-tight text-ink">
            Dört açıdan inceleme
          </h2>
          <p className="mt-2 max-w-xl text-[15px] leading-6 text-ink-soft">
            Her bölüm kendi bulgularını üretir; genel değerlendirme bu bulguların birlikte yorumlanmasıyla hazırlanır. Belirli
            bir marka listesine bağlı değildir.
          </p>
          <ol className="mt-6 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2">
            {CHECKS.map((check, index) => (
              <li key={check.title} className="bg-card p-5">
                <span className="font-mono text-[13px] font-semibold text-teal-strong">0{index + 1}</span>
                <h3 className="mt-2 text-[16px] font-bold text-ink">{check.title}</h3>
                <p className="mt-1 text-[14px] leading-6 text-ink-muted">{check.text}</p>
              </li>
            ))}
          </ol>
          <p className="mt-5 max-w-xl text-[14px] leading-6 text-ink-muted">
            {STAGE_DESCRIPTIONS.page_fetch} Sonuçlar bir değerlendirmedir: düşük risk, sitenin güvenli olduğunu garanti etmez.
          </p>
        </section>

        {isDemoMode && <DemoScenarioList onPick={(url) => formRef.current?.fill(url)} />}
      </div>
    </div>
  );
}
