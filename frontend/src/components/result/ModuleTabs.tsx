import { FileCode2, FileWarning, Image, Link2, Type, type LucideIcon } from 'lucide-react';
import { ErrorBoundary } from '../ErrorBoundary';
import { StatePanel } from '../StatePanel';
import { FindingList } from './FindingList';
import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { MODULE_LABELS, MODULE_ORDER, MODULE_STATUS_LABELS } from '../../lib/labels';
import type { AnalysisResult, ModuleKey } from '../../types/analysis';
import { Eyebrow } from '../ui';
import { HtmlDetails, TextDetails, UrlDetails, VisualDetails } from './ModuleDetails';
import { MODULE_STATUS_ICONS } from './ResultMeta';

const MODULE_ICONS: Record<ModuleKey, LucideIcon> = {
  url: Link2,
  visual: Image,
  text: Type,
  html: FileCode2,
};

/** Dört analiz bölümü için klavyeyle gezilebilir sekmeler (WAI-ARIA Tabs). */
export function ModuleTabs({ result, initial = 'url' }: { result: AnalysisResult; initial?: ModuleKey }) {
  const [active, setActive] = useState<ModuleKey>(initial);
  const baseId = useId();
  const tabRefs = useRef<Record<ModuleKey, HTMLButtonElement | null>>({ url: null, visual: null, text: null, html: null });

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const index = MODULE_ORDER.indexOf(active);
    let next: number | null = null;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % MODULE_ORDER.length;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + MODULE_ORDER.length) % MODULE_ORDER.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = MODULE_ORDER.length - 1;
    if (next === null) return;
    event.preventDefault();
    const key = MODULE_ORDER[next];
    setActive(key);
    tabRefs.current[key]?.focus();
  }

  const module = result.modules[active];
  const pageUrl = result.finalUrl ?? result.submittedUrl;

  return (
    <section aria-labelledby={`${baseId}-heading`}>
      <Eyebrow>Ayrıntılar</Eyebrow>
      <h2 id={`${baseId}-heading`} className="mt-1 text-2xl font-bold tracking-tight text-ink">
        Bölüm bölüm inceleme
      </h2>

      <div className="mt-5 overflow-hidden rounded-2xl border border-line bg-card">
        <div role="tablist" aria-label="Analiz bölümleri" className="grid grid-cols-2 border-b border-line md:grid-cols-4">
          {MODULE_ORDER.map((key, index) => {
            const selected = key === active;
            const status = result.modules[key].status;
            const StatusIcon = MODULE_STATUS_ICONS[status];
            const Icon = MODULE_ICONS[key];
            return (
              <button
                key={key}
                ref={(node) => {
                  tabRefs.current[key] = node;
                }}
                role="tab"
                type="button"
                id={`${baseId}-tab-${key}`}
                aria-selected={selected}
                aria-controls={`${baseId}-panel`}
                tabIndex={selected ? 0 : -1}
                onClick={() => setActive(key)}
                onKeyDown={onKeyDown}
                className={[
                  'relative flex min-h-16 items-center gap-3 px-4 py-3 text-left transition-colors',
                  index % 2 === 1 ? 'border-l border-line' : '',
                  index >= 2 ? 'border-t border-line md:border-t-0' : '',
                  index === 2 ? 'md:border-l' : '',
                  selected ? 'bg-card' : 'bg-paper/60 hover:bg-paper-deep',
                ].join(' ')}
              >
                {selected && <span aria-hidden className="absolute inset-x-0 bottom-0 h-[3px] bg-teal" />}
                <Icon aria-hidden className={`size-5 shrink-0 ${selected ? 'text-teal-strong' : 'text-ink-muted'}`} strokeWidth={2.25} />
                <span className="min-w-0">
                  <span className={`block text-[14px] font-bold leading-5 ${selected ? 'text-ink' : 'text-ink-soft'}`}>{MODULE_LABELS[key]}</span>
                  <span
                    className={`mt-0.5 flex items-center gap-1 text-[12px] font-semibold ${status === 'completed' ? 'text-teal-strong' : 'text-ink-muted'}`}
                  >
                    <StatusIcon aria-hidden className="size-3.5" strokeWidth={2.75} />
                    {MODULE_STATUS_LABELS[status]}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <div
          role="tabpanel"
          id={`${baseId}-panel`}
          aria-labelledby={`${baseId}-tab-${active}`}
          tabIndex={0}
          className="p-5 focus-visible:outline-offset-[-3px] sm:p-7"
        >
          <p className="mb-6 text-[16px] font-semibold leading-6 text-ink">{module.summary}</p>
          {/* Modül verisi beklenen biçimde değilse yalnızca bu bölüm yedek içerikle gösterilir. */}
          <ErrorBoundary
            resetKey={`${result.id}:${active}`}
            fallback={
              <div className="space-y-6">
                <StatePanel headingLevel="h3" icon={FileWarning} tone="warning" title="Bu bölümün ayrıntıları görüntülenemedi">
                  <p>Analiz servisinden gelen ayrıntılı veriler beklenen biçimde değil. Bulgular aşağıda listelenmiştir.</p>
                </StatePanel>
                <FindingList findings={module.findings} />
              </div>
            }
          >
            {module.key === 'url' && <UrlDetails module={module} />}
            {module.key === 'visual' && <VisualDetails module={module} pageUrl={pageUrl} />}
            {module.key === 'text' && <TextDetails module={module} />}
            {module.key === 'html' && <HtmlDetails module={module} />}
          </ErrorBoundary>
        </div>
      </div>
    </section>
  );
}
