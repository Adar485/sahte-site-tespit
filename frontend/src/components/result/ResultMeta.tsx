import { Check, CircleDashed, Clock, Loader2, Minus, X } from 'lucide-react';
import { formatDateTime, formatDuration } from '../../lib/format';
import { ANALYSIS_MODE_LABELS, MODULE_LABELS, MODULE_ORDER, MODULE_STATUS_LABELS } from '../../lib/labels';
import type { AnalysisResult, ModuleStatus } from '../../types/analysis';
import { isDifferentAddress } from '../../lib/url';
import { UrlText } from '../ui';

export const MODULE_STATUS_ICONS: Record<ModuleStatus, typeof Check> = {
  pending: Clock,
  running: Loader2,
  completed: Check,
  unavailable: CircleDashed,
  skipped: Minus,
  failed: X,
};

export function ResultMeta({ result }: { result: AnalysisResult }) {
  const completed = MODULE_ORDER.filter((key) => result.modules[key].status === 'completed').length;
  const redirected = result.finalUrl && isDifferentAddress(result.submittedUrl, result.finalUrl);
  const analyzedAt = result.completedAt ?? result.requestedAt;

  return (
    <section aria-labelledby="analiz-bilgileri" className="rounded-2xl border border-line bg-card">
      <h2 id="analiz-bilgileri" className="sr-only">
        Analiz bilgileri
      </h2>
      <dl className="grid divide-y divide-line md:grid-cols-2 md:divide-y-0">
        <div className="space-y-4 p-5 sm:p-6 md:border-r md:border-line">
          <div>
            <dt className="text-[13px] font-bold text-ink-muted">Gönderilen adres</dt>
            <dd className="mt-1 text-[15px] text-ink">
              <UrlText url={result.submittedUrl} />
            </dd>
          </div>
          <div>
            <dt className="text-[13px] font-bold text-ink-muted">Son adres</dt>
            <dd className="mt-1 text-[15px] text-ink">
              {result.finalUrl ? (
                <>
                  <UrlText url={result.finalUrl} />
                  {redirected && <span className="mt-1 block text-[13px] font-semibold text-amber">Yönlendirme sonrası farklı adres</span>}
                </>
              ) : (
                <span className="text-ink-muted">
                  {result.analysisMode === 'url_only' && !result.isDemo && !result.capture ? 'Sayfa açılmadı' : 'Belirlenemedi'}
                </span>
              )}
            </dd>
          </div>
        </div>

        <div className="grid gap-4 p-5 sm:grid-cols-2 sm:p-6">
          <div>
            <dt className="text-[13px] font-bold text-ink-muted">Analiz zamanı</dt>
            <dd className="mt-1 text-[15px] text-ink">
              <time dateTime={analyzedAt}>{formatDateTime(analyzedAt)}</time>
            </dd>
          </div>
          <div>
            <dt className="text-[13px] font-bold text-ink-muted">Süre</dt>
            <dd className="mt-1 text-[15px] tabular-nums text-ink">{result.durationMs === null ? <span className="text-ink-muted">Bilinmiyor</span> : formatDuration(result.durationMs)}</dd>
          </div>
          <div>
            <dt className="text-[13px] font-bold text-ink-muted">Analiz kapsamı</dt>
            <dd className="mt-1 text-[15px] text-ink">
              {result.analysisMode ? ANALYSIS_MODE_LABELS[result.analysisMode] : <span className="text-ink-muted">Belirtilmedi</span>}
            </dd>
          </div>
          <div>
            <dt className="text-[13px] font-bold text-ink-muted">Model sürümü</dt>
            <dd className="mt-1 text-[15px] text-ink">
              {result.modelVersion ? <span className="font-mono text-[14px]">{result.modelVersion}</span> : <span className="text-ink-muted">Yok</span>}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-[13px] font-bold text-ink-muted">
              Tamamlanan bölümler <span className="tabular-nums">({completed}/{MODULE_ORDER.length})</span>
            </dt>
            <dd className="mt-2">
              <ul className="flex flex-wrap gap-1.5">
                {MODULE_ORDER.map((key) => {
                  const status = result.modules[key].status;
                  const Icon = MODULE_STATUS_ICONS[status];
                  const ok = status === 'completed';
                  return (
                    <li
                      key={key}
                      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[13px] font-semibold ${
                        ok ? 'border-teal/25 bg-teal-soft text-teal-strong' : 'border-line-strong bg-paper text-ink-muted'
                      }`}
                    >
                      <Icon aria-hidden className="size-3.5" strokeWidth={2.75} />
                      {MODULE_LABELS[key].replace(' analizi', '').replace(' analiz', '')}
                      <span className="sr-only">: {MODULE_STATUS_LABELS[status]}</span>
                    </li>
                  );
                })}
              </ul>
            </dd>
          </div>
        </div>
      </dl>
    </section>
  );
}
