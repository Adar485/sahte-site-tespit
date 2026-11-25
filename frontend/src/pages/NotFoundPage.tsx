import { Compass, History, ScanSearch } from 'lucide-react';
import { StatePanel } from '../components/StatePanel';
import { ButtonLink, Panel } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function NotFoundPage() {
  useDocumentTitle('Sayfa bulunamadı');
  return (
    <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6 sm:py-24">
      <Panel className="p-6 sm:p-8">
        <StatePanel
          headingLevel="h1"
          icon={Compass}
          title="Aradığınız sayfa bulunamadı"
          actions={
            <>
              <ButtonLink to="/" icon={ScanSearch}>
                Analiz sayfasına git
              </ButtonLink>
              <ButtonLink to="/gecmis" variant="secondary" icon={History}>
                Geçmişi aç
              </ButtonLink>
            </>
          }
        >
          <p>Bağlantı eksik ya da hatalı olabilir.</p>
        </StatePanel>
      </Panel>
    </div>
  );
}
