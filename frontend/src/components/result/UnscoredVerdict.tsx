import { ScanSearch } from 'lucide-react';
import type { PageCapture } from '../../types/analysis';
import { Eyebrow } from '../ui';

function scope(capture: PageCapture | null, visualReady: boolean): string {
  if (visualReady) return 'Adres metni incelendi ve DINOv2 ile görsel özellikler çıkarıldı. Referans karşılaştırması ve genel risk sınıflandırması henüz yapılmadı.';
  if (!capture) return 'Yalnızca adres metni incelendi; sayfa açılmadı.';
  if (capture.status === 'failed') return 'Adres metni incelendi; sayfa yakalanamadı.';
  return 'Adres metni incelendi ve sayfa yakalandı. Görüntü, metin ve sayfa yapısı henüz analiz edilmedi.';
}

/** İnceleme yapıldı ama sınıflandırıcı çalışmadı: hiçbir risk düzeyi gösterilmez. */
export function UnscoredVerdict({ capture, visualReady = false }: { capture: PageCapture | null; visualReady?: boolean }) {
  return (
    <section aria-labelledby="genel-sonuc" className="overflow-hidden rounded-2xl border border-line-strong bg-card">
      <div className="h-1.5 bg-ink-muted" aria-hidden />
      <div className="p-6 sm:p-8">
        <Eyebrow>Genel değerlendirme</Eyebrow>
        <div className="mt-3 flex items-start gap-4">
          <span className="inline-flex size-14 shrink-0 items-center justify-center rounded-2xl bg-paper-deep text-ink-soft">
            <ScanSearch aria-hidden className="size-8" strokeWidth={2} />
          </span>
          <h1 id="genel-sonuc" className="max-w-3xl text-[24px] font-extrabold leading-tight tracking-[-0.02em] text-ink sm:text-3xl">
            {visualReady ? 'URL ve görsel özellik çıkarımı tamamlandı; genel risk değerlendirmesi henüz yapılmadı.' : 'URL incelemesi tamamlandı; genel risk değerlendirmesi henüz yapılmadı.'}
          </h1>
        </div>
        <p className="mt-5 max-w-2xl text-[15px] leading-6 text-ink-soft">
          {scope(capture, visualReady)} Aşağıdaki gözlemler tek başına sitenin güvenli ya da tehlikeli olduğunu göstermez.
        </p>
      </div>
    </section>
  );
}
