import {
  ArrowRight,
  ChevronRight,
  CircleDashed,
  DatabaseZap,
  History,
  Loader2,
  RotateCcw,
  ScanSearch,
  Search,
  SearchX,
  ServerOff,
  Trash2,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { RiskTag, toneOf } from '../components/risk';
import { StatePanel } from '../components/StatePanel';
import { Button, ButtonLink, Eyebrow, Panel } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useHistoryQuery } from '../hooks/useHistoryQuery';
import { formatShortDate, formatTime } from '../lib/format';
import { FILTER_LABELS } from '../lib/labels';
import { displayUrl } from '../lib/url';
import { analysisService, isDemoMode, toServiceError } from '../services';
import type { HistoryEntry, HistoryPage as HistoryPageData, ResultFilter } from '../types/analysis';

const FILTERS: ResultFilter[] = ['all', 'low', 'suspicious', 'high', 'failed'];
const EMPTY_COUNTS: Record<ResultFilter, number> = { all: 0, low: 0, suspicious: 0, high: 0, failed: 0 };

type PendingDelete = { kind: 'one'; entry: HistoryEntry } | { kind: 'all' } | null;

export function HistoryPage() {
  useDocumentTitle('Analiz geçmişi');
  const [params, setParams] = useSearchParams();
  const query = params.get('ara') ?? '';
  const filter = (FILTERS.includes(params.get('sonuc') as ResultFilter) ? params.get('sonuc') : 'all') as ResultFilter;
  const { view, reload } = useHistoryQuery(query.trim(), filter);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState('');

  const updateParam = (key: string, value: string, empty: string) => {
    const next = new URLSearchParams(params);
    if (value && value !== empty) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  // Yükleme sırasında önceki sonuç ekranda kalır; böylece arama kutusu odağını kaybetmez.
  const page: HistoryPageData | null = view.phase === 'ready' ? view.page : view.phase === 'loading' ? view.previous : null;
  const counts = page?.counts ?? EMPTY_COUNTS;
  const items = page?.items ?? [];
  const isLoading = view.phase === 'loading';
  const historyIsEmpty = page !== null && !query.trim() && filter === 'all' && counts.all === 0;

  const confirmDelete = async () => {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    setActionError(null);
    try {
      if (pendingDelete.kind === 'all') {
        await analysisService.clearHistory?.();
        setAnnouncement('Analiz geçmişi temizlendi.');
      } else {
        await analysisService.deleteAnalysis(pendingDelete.entry.id);
        setAnnouncement(`${displayUrl(pendingDelete.entry.submittedUrl)} kaydı silindi.`);
      }
    } catch (error) {
      const serviceError = toServiceError(error);
      // Kayıt zaten silinmişse listeyi yenilemek yeterli.
      if (serviceError.code !== 'not_found') setActionError(serviceError.message);
    } finally {
      setDeleting(false);
      setPendingDelete(null);
      reload();
    }
  };

  const loadSamples = async () => {
    await analysisService.loadSamples?.();
    setAnnouncement('Örnek geçmiş kayıtları yüklendi.');
    reload();
  };

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 sm:pt-14">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Eyebrow>Geçmiş</Eyebrow>
          <h1 className="mt-1 text-3xl font-extrabold tracking-[-0.02em] text-ink sm:text-4xl">Analiz geçmişi</h1>
          <p className="mt-2 max-w-xl text-[15px] leading-6 text-ink-soft">
            {isDemoMode
              ? 'Demo modu: örnek analizler yalnızca bu tarayıcıda saklanır.'
              : 'Analiz servisinde kayıtlı analizler. En yeni kayıtlar en üstte gösterilir.'}
          </p>
        </div>
        {analysisService.clearHistory && counts.all > 0 && (
          <Button variant="ghost" icon={Trash2} onClick={() => setPendingDelete({ kind: 'all' })} className="self-start text-coral hover:text-coral sm:self-auto">
            Geçmişi temizle
          </Button>
        )}
      </div>

      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {actionError && (
        <div className="mt-6 rounded-2xl border border-amber/30 bg-amber-soft/50 p-5">
          <StatePanel
            alert
            tone="warning"
            icon={ServerOff}
            title="Kayıt silinemedi"
            actions={
              <Button variant="secondary" onClick={() => setActionError(null)}>
                Kapat
              </Button>
            }
          >
            <p>{actionError}</p>
          </StatePanel>
        </div>
      )}

      {view.phase === 'error' ? (
        <Panel className="mt-8 p-6 sm:p-10">
          <StatePanel
            alert
            tone="warning"
            icon={ServerOff}
            title="Geçmiş yüklenemedi"
            actions={
              <Button icon={RotateCcw} onClick={reload}>
                Yeniden dene
              </Button>
            }
          >
            <p>{view.error.message}</p>
          </StatePanel>
        </Panel>
      ) : page === null ? (
        <p role="status" className="mt-10 flex items-center gap-3 text-ink-soft">
          <Loader2 aria-hidden className="size-5 motion-safe:animate-spin" />
          Geçmiş yükleniyor…
        </p>
      ) : historyIsEmpty ? (
        <Panel className="mt-8 p-6 sm:p-10">
          <StatePanel
            icon={History}
            title="Henüz bir analiz yapılmadı"
            actions={
              <>
                <ButtonLink to="/" icon={ScanSearch}>
                  İlk analizi başlat
                </ButtonLink>
                {analysisService.loadSamples && (
                  <Button variant="secondary" icon={DatabaseZap} onClick={loadSamples}>
                    Örnek geçmiş yükle
                  </Button>
                )}
              </>
            }
          >
            <p>Bir adresi analiz ettiğinizde sonucu burada görür, daha sonra yeniden açabilirsiniz.</p>
          </StatePanel>
        </Panel>
      ) : (
        <>
          <div className="mt-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative w-full lg:max-w-sm">
              <label htmlFor="gecmis-ara" className="sr-only">
                Geçmişte adres ara
              </label>
              <Search aria-hidden className="pointer-events-none absolute left-3.5 top-1/2 size-[18px] -translate-y-1/2 text-ink-muted" />
              <input
                id="gecmis-ara"
                type="search"
                value={query}
                onChange={(event) => updateParam('ara', event.target.value, '')}
                placeholder="Adres ara"
                autoComplete="off"
                spellCheck={false}
                className="h-12 w-full rounded-xl border-2 border-line-strong bg-white pl-10 pr-11 text-[15px] text-ink outline-none placeholder:text-ink-muted/80 focus:border-teal focus-visible:outline-none [&::-webkit-search-cancel-button]:hidden"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => updateParam('ara', '', '')}
                  className="absolute right-1 top-1/2 inline-flex size-10 -translate-y-1/2 items-center justify-center rounded-lg text-ink-muted hover:bg-paper-deep hover:text-ink"
                >
                  <X aria-hidden className="size-[18px]" />
                  <span className="sr-only">Aramayı temizle</span>
                </button>
              )}
            </div>

            <fieldset className="min-w-0">
              <legend className="sr-only">Sonuca göre filtrele</legend>
              <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 lg:mx-0 lg:px-0 lg:pb-0">
                {FILTERS.map((item) => {
                  const selected = item === filter;
                  return (
                    <label
                      key={item}
                      className={[
                        'relative inline-flex min-h-11 shrink-0 cursor-pointer items-center gap-2 rounded-full border px-4 text-[14px] font-semibold transition-colors',
                        'has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-blue',
                        selected ? 'border-ink bg-ink text-white' : 'border-line-strong bg-card text-ink-soft hover:border-ink/50',
                      ].join(' ')}
                    >
                      <input
                        type="radio"
                        name="sonuc"
                        value={item}
                        checked={selected}
                        onChange={() => updateParam('sonuc', item, 'all')}
                        className="sr-only"
                      />
                      {FILTER_LABELS[item]}
                      <span className={`tabular-nums text-[13px] ${selected ? 'text-white/75' : 'text-ink-muted'}`}>{counts[item]}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          </div>

          <p className="mt-5 flex items-center gap-2 text-[14px] text-ink-muted" aria-live="polite">
            {isLoading && <Loader2 aria-hidden className="size-4 motion-safe:animate-spin" />}
            {page.total === counts.all ? `${counts.all} kayıt` : `${counts.all} kayıttan ${page.total} tanesi gösteriliyor`}
            {items.length < page.total && ` (ilk ${items.length})`}
          </p>

          {items.length === 0 ? (
            <Panel className="mt-3 p-6 sm:p-8">
              <StatePanel
                icon={SearchX}
                title="Eşleşen kayıt yok"
                actions={
                  <Button variant="secondary" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
                    Aramayı ve filtreyi temizle
                  </Button>
                }
              >
                <p>Farklı bir arama deneyin ya da tüm sonuçları gösterin.</p>
              </StatePanel>
            </Panel>
          ) : (
            <ul
              aria-busy={isLoading}
              className={`mt-3 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-card transition-opacity ${isLoading ? 'opacity-60' : ''}`}
            >
              {items.map((entry) => (
                <HistoryRow key={entry.id} entry={entry} onDelete={() => setPendingDelete({ kind: 'one', entry })} />
              ))}
            </ul>
          )}
        </>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title={pendingDelete?.kind === 'all' ? 'Tüm geçmiş silinsin mi?' : 'Bu kayıt silinsin mi?'}
        description={
          pendingDelete?.kind === 'all'
            ? `${counts.all} analiz kaydı kalıcı olarak silinecek. Bu işlem geri alınamaz.`
            : pendingDelete?.kind === 'one'
              ? `${displayUrl(pendingDelete.entry.submittedUrl)} için yapılan analiz kaydı kalıcı olarak silinecek. Bu işlem geri alınamaz.`
              : ''
        }
        confirmLabel={pendingDelete?.kind === 'all' ? 'Geçmişi temizle' : 'Kaydı sil'}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}

function HistoryRow({ entry, onDelete }: { entry: HistoryEntry; onDelete(): void }) {
  const redirected = entry.finalUrl && entry.finalUrl !== entry.submittedUrl;
  return (
    <li className="group relative flex items-center gap-3 px-4 py-4 transition-colors hover:bg-paper sm:gap-5 sm:px-6">
      <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-[150px_minmax(0,1fr)_130px] sm:items-center sm:gap-5">
        <div className="flex flex-wrap items-center gap-1.5 sm:order-none">
          <RiskTag tone={toneOf(entry.riskLevel, entry.status)} />
          {entry.status === 'partial' && entry.riskLevel && (
            <span className="inline-flex items-center gap-1 text-[12px] font-semibold text-ink-muted">
              <CircleDashed aria-hidden className="size-3.5" /> Kısmi
            </span>
          )}
        </div>

        <div className="min-w-0">
          <Link
            to={`/analiz/${encodeURIComponent(entry.id)}`}
            className="block truncate font-mono text-[15px] font-semibold text-ink after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:outline-none group-has-[a:focus-visible]:underline"
          >
            {displayUrl(entry.submittedUrl)}
            <span className="sr-only"> analiz sonucunu aç</span>
          </Link>
          {redirected && (
            <p className="mt-0.5 flex min-w-0 items-center gap-1 text-[13px] text-ink-muted">
              <ArrowRight aria-hidden className="size-3.5 shrink-0" />
              <span className="sr-only">Son adres: </span>
              <span className="truncate font-mono">{displayUrl(entry.finalUrl!)}</span>
            </p>
          )}
        </div>

        <p className="text-[13px] text-ink-muted sm:text-right">
          <time dateTime={entry.analyzedAt}>
            {formatShortDate(entry.analyzedAt)} · {formatTime(entry.analyzedAt)}
          </time>
        </p>
      </div>

      <button
        type="button"
        onClick={onDelete}
        className="relative z-10 inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-coral-soft hover:text-coral"
      >
        <Trash2 aria-hidden className="size-[18px]" />
        <span className="sr-only">{displayUrl(entry.submittedUrl)} kaydını sil</span>
      </button>
      <ChevronRight aria-hidden className="hidden size-5 shrink-0 text-ink-muted sm:block" />
    </li>
  );
}
