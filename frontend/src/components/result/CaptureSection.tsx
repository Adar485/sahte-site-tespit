import { ImageOff } from 'lucide-react';
import { useState } from 'react';
import { formatDuration, formatNumber } from '../../lib/format';
import { API_BASE_URL } from '../../services/apiService';
import type { PageCapture } from '../../types/analysis';
import { UrlText } from '../ui';
import { Facts } from './blocks';

const STATUS_LABELS: Record<PageCapture['status'], string> = {
  pending: 'Sırada',
  running: 'Sürüyor',
  completed: 'Tamamlandı',
  partial: 'Kısmen tamamlandı',
  failed: 'Yakalanamadı',
};

const available = (value: boolean) => (value ? 'Var' : 'Yok');

/** Sayfadan alınan ham kayıtlar. Yorum ya da risk değerlendirmesi içermez. */
export function CaptureSection({ capture }: { capture: PageCapture }) {
  const [imageFailed, setImageFailed] = useState(false);
  const { signals, artifacts } = capture;
  const notes = [
    signals?.httpError && `Sunucu bir hata sayfası döndürdü (HTTP ${capture.httpStatus}).`,
    signals?.blank && 'Sayfada görünür bir içerik bulunmadı.',
    signals?.captcha && 'Sayfada insan doğrulaması (CAPTCHA) bileşeni görüldü; doğrulama geçilmeye çalışılmadı.',
    capture.consistent === false && 'Kayıtlar alınırken sayfa adres değiştirdi; parçalar aynı ana ait olmayabilir.',
  ].filter((note): note is string => Boolean(note));

  return (
    <section aria-labelledby="sayfa-yakalama" className="rounded-2xl border border-line bg-card p-5 sm:p-7">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="sayfa-yakalama" className="text-lg font-bold text-ink">
          Sayfa yakalama
        </h2>
        <p className="text-[13px] font-semibold text-ink-muted">
          Durum: <span className="text-ink">{STATUS_LABELS[capture.status]}</span>
        </p>
      </div>

      {capture.error && (
        <p role="alert" className="mt-4 rounded-xl border border-amber/30 bg-amber-soft/50 p-4 text-[15px] leading-6 text-ink">
          {capture.error.message}
        </p>
      )}
      {notes.length > 0 && (
        <ul className="mt-4 list-disc space-y-1 pl-5 text-[15px] leading-6 text-ink-soft">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}

      <div className="mt-5">
        <Facts
          items={[
            { label: 'Açılan son adres', value: capture.finalUrl ? <UrlText url={capture.finalUrl} /> : 'Yok' },
            { label: 'Yönlendirme', value: capture.finalUrl ? (capture.redirected ? 'Var' : 'Yok') : 'Belirlenemedi' },
            { label: 'HTTP durumu', value: capture.httpStatus ?? 'Yok' },
            { label: 'Yakalama süresi', value: capture.durationMs === null ? 'Bilinmiyor' : formatDuration(capture.durationMs) },
            { label: 'Görünüm boyutu', value: `${capture.viewportWidth} × ${capture.viewportHeight}` },
            { label: 'Sayfa başlığı', value: capture.pageTitle || 'Yok' },
            { label: 'Ekran görüntüsü', value: available(artifacts.screenshot) },
            { label: 'İşlenmiş HTML (sunucuda saklanır)', value: available(artifacts.html) },
            { label: 'Görünür metin', value: available(artifacts.text) },
          ]}
        />
      </div>

      {capture.screenshotUrl && (
        <figure className="mt-6">
          {imageFailed ? (
            <p className="flex items-center gap-2 text-[15px] text-ink-muted">
              <ImageOff aria-hidden className="size-5" /> Ekran görüntüsü yüklenemedi.
            </p>
          ) : (
            <img
              src={`${API_BASE_URL}${capture.screenshotUrl}`}
              alt="Yakalanan sayfanın ekran görüntüsü"
              width={capture.viewportWidth}
              height={capture.viewportHeight}
              loading="lazy"
              onError={() => setImageFailed(true)}
              className="block h-auto w-full rounded-xl border border-line-strong bg-white"
            />
          )}
          <figcaption className="mt-2 text-[13px] text-ink-muted">
            İncelenen sayfanın görüntüsüdür; içindeki bağlantılar ve formlar etkin değildir.
          </figcaption>
        </figure>
      )}

      {capture.textPreview !== null && (
        <div className="mt-6">
          <h3 className="text-[16px] font-bold text-ink">Görünür metin önizlemesi</h3>
          {capture.textPreview.trim() ? (
            <>
              <pre
                tabIndex={0}
                className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-line bg-paper p-4 font-mono text-[13px] leading-6 text-ink-soft"
              >
                {capture.textPreview}
              </pre>
              {capture.textLength !== null && capture.textLength > capture.textPreview.length && (
                <p className="mt-2 text-[13px] text-ink-muted">
                  Toplam {formatNumber(capture.textLength)} karakterin ilk bölümü gösteriliyor.
                </p>
              )}
            </>
          ) : (
            <p className="mt-2 text-[15px] text-ink-muted">Sayfada okunabilir metin bulunamadı.</p>
          )}
        </div>
      )}
    </section>
  );
}
