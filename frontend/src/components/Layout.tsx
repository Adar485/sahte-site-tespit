import { History, Info, ScanSearch, TriangleAlert } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { isDemoMode } from '../services';
import { ErrorBoundary } from './ErrorBoundary';
import { StatePanel } from './StatePanel';
import { ButtonLink, Panel } from './ui';

/** Beklenmeyen bir hata tüm sayfayı boş bırakmak yerine bu mesajı gösterir. */
function PageCrashFallback() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
      <Panel className="p-6 sm:p-8">
        <StatePanel
          alert
          headingLevel="h1"
          tone="warning"
          icon={TriangleAlert}
          title="Bu sayfa görüntülenemedi"
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
          <p>Beklenmeyen bir sorun oluştu. Başka bir sayfaya geçebilir ya da sayfayı yenileyebilirsiniz.</p>
        </StatePanel>
      </Panel>
    </div>
  );
}

function LogoMark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className="size-8 shrink-0 sm:size-9">
      <rect width="32" height="32" rx="9" fill="#0F1E3D" />
      <circle cx="14" cy="14" r="6.5" fill="none" stroke="#19B3A2" strokeWidth="3" />
      <path d="M19 19l6 6" stroke="#19B3A2" strokeWidth="3" strokeLinecap="round" />
      <circle cx="14" cy="14" r="1.8" fill="#F0A21A" />
    </svg>
  );
}

const NAV_ITEMS = [
  { to: '/', label: 'Analiz', icon: ScanSearch, end: true },
  { to: '/gecmis', label: 'Geçmiş', icon: History, end: false },
];

function DemoNotice() {
  return (
    <div className="border-b border-blue/15 bg-blue-soft text-ink">
      <p className="mx-auto flex max-w-6xl items-start gap-2 px-4 py-2 text-[13px] leading-5 sm:items-center sm:px-6">
        <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-blue sm:mt-0" />
        <span>
          <strong className="font-bold">Demo modu:</strong> Arka uca bağlanılmıyor. Gösterilen sonuçlar ve geçmiş örnek
          verilerden üretilir ve yalnızca bu tarayıcıda saklanır.
        </span>
      </p>
    </div>
  );
}

export function Layout() {
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const firstRender = useRef(true);

  // Sayfa değiştiğinde odağı ana içeriğe taşı ve en üste kaydır (ekran okuyucular için).
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    window.scrollTo({ top: 0 });
    mainRef.current?.focus({ preventScroll: true });
  }, [location.pathname]);

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#icerik"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-4 focus:py-3 focus:text-white"
      >
        İçeriğe geç
      </a>

      {isDemoMode && <DemoNotice />}

      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link to="/" className="flex min-h-11 min-w-0 items-center gap-2.5 rounded-lg pr-2 sm:gap-3">
            <LogoMark />
            <span className="text-[16px] font-extrabold tracking-tight whitespace-nowrap text-ink sm:text-lg">Sahte Site Avcıları</span>
          </Link>

          <nav aria-label="Ana gezinme">
            <ul className="flex items-center gap-1">
              {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      [
                        'relative inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-[15px] font-semibold transition-colors',
                        isActive ? 'text-ink' : 'text-ink-muted hover:bg-paper-deep hover:text-ink',
                      ].join(' ')
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon aria-hidden className="hidden size-[18px] sm:block" strokeWidth={2.25} />
                        <span>{label}</span>
                        {isActive && <span aria-hidden className="absolute inset-x-3 -bottom-[13px] h-[3px] rounded-full bg-teal" />}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>

      <main id="icerik" ref={mainRef} tabIndex={-1} className="flex-1 outline-none">
        <ErrorBoundary resetKey={location.pathname} fallback={<PageCrashFallback />}>
          <Outlet />
        </ErrorBoundary>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-6 text-[13px] text-ink-muted sm:flex-row sm:justify-between sm:px-6">
          <p>Sahte Site Avcıları · Phishing risk değerlendirmesi</p>
          <p>Sonuçlar bir değerlendirmedir; hiçbir sonuç güvenlik garantisi değildir.</p>
        </div>
      </footer>
    </div>
  );
}
