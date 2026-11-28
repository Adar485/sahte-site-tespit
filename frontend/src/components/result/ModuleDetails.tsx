import { ArrowDown, Flag, ImageOff, Lock, LockOpen, TextSearch } from 'lucide-react';
import { formatNumber } from '../../lib/format';
import { MODULE_LABELS, PHRASE_CATEGORY_LABELS } from '../../lib/labels';
import { displayUrl } from '../../lib/url';
import type {
  HtmlModuleResult,
  KeyPhrase,
  ModuleResult,
  SimilarityMatch,
  TextModuleResult,
  UrlModuleResult,
  VisualModuleResult,
} from '../../types/analysis';
import { StatePanel } from '../StatePanel';
import { UrlText } from '../ui';
import { Block, Facts } from './blocks';
import { FindingList } from './FindingList';
import { SimilarityMeter, SimilarityNote } from './Similarity';
import { UrlInspectionDetails } from './UrlInspectionDetails';

function SimilarityBlock({ title, matches, emptyText }: { title: string; matches: SimilarityMatch[]; emptyText: string }) {
  return (
    <Block title={title}>
      {matches.length > 0 ? (
        <div className="space-y-4">
          {matches.map((match) => (
            <SimilarityMeter key={match.reference} match={match} />
          ))}
          <SimilarityNote />
        </div>
      ) : (
        <p className="text-[15px] text-ink-muted">{emptyText}</p>
      )}
    </Block>
  );
}

/** Modül hiç çalışmadıysa ya da veri üretemediyse gösterilen bilinçli boş durum. */
export function ModuleUnavailable({ module, assessed = true }: { module: ModuleResult; assessed?: boolean }) {
  const isSkipped = module.status === 'skipped';
  return (
    <StatePanel
      headingLevel="h3"
      icon={module.key === 'visual' ? ImageOff : TextSearch}
      title={isSkipped ? `${MODULE_LABELS[module.key]} çalıştırılmadı` : module.summary}
    >
      <p>{module.unavailableReason ?? 'Bu bölüm için veri alınamadı.'}</p>
      <p className="mt-2 text-[14px] text-ink-muted">
        {assessed ? 'Genel değerlendirme, yalnızca tamamlanan bölümlerin bulgularıyla yapıldı.' : 'Genel risk değerlendirmesi henüz yapılmadı.'}
      </p>
    </StatePanel>
  );
}

/* ------------------------------------------------------------------ */

export function UrlDetails({ module }: { module: UrlModuleResult }) {
  const data = module.data;
  if (data && 'featureSchemaVersion' in data) return <UrlInspectionDetails findings={module.findings} data={data} />;
  return (
    <div className="space-y-6">
      <Block title="Bulgular">
        <FindingList findings={module.findings} />
      </Block>

      {data && (
        <>
          <Block title="Adres bilgileri">
            <Facts
              items={[
                { label: 'Ana makine', value: <UrlText url={data.hostname} /> },
                { label: 'Kayıtlı alan adı', value: <UrlText url={data.registeredDomain} /> },
                { label: 'Uzantı', value: <span className="font-mono">.{data.topLevelDomain}</span> },
                { label: 'Alt alan adları', value: data.subdomains.length ? <span className="font-mono">{data.subdomains.join(', ')}</span> : 'Yok' },
                {
                  label: 'Bağlantı',
                  value: (
                    <span className="inline-flex items-center gap-1.5">
                      {data.usesHttps ? <Lock aria-hidden className="size-4 text-ink-soft" /> : <LockOpen aria-hidden className="size-4 text-amber" />}
                      {data.usesHttps ? 'HTTPS (şifreli)' : 'HTTP (şifresiz)'}
                    </span>
                  ),
                },
                { label: 'Adres uzunluğu', value: `${formatNumber(data.urlLength)} karakter` },
              ]}
            />
          </Block>

          <Block title="Yönlendirme zinciri" aside={<span className="text-[13px] font-semibold text-ink-muted">{data.redirectChain.length ? `${data.redirectChain.length - 1} yönlendirme` : 'Yönlendirme yok'}</span>}>
            {data.redirectChain.length ? (
              <ol className="space-y-1">
                {data.redirectChain.map((url, index) => (
                  <li key={`${url}-${index}`}>
                    {index > 0 && <ArrowDown aria-hidden className="mb-1 ml-3 size-4 text-ink-muted" />}
                    <div className="flex items-baseline gap-3 rounded-lg border border-line bg-paper px-3 py-2">
                      <span className="shrink-0 text-[12px] font-bold text-ink-muted">{index === 0 ? 'Başlangıç' : index === data.redirectChain.length - 1 ? 'Son' : `${index}.`}</span>
                      <UrlText url={displayUrl(url)} className="text-[14px] text-ink" />
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-[15px] text-ink-muted">Adres doğrudan açıldı; başka bir adrese yönlendirilmedi.</p>
            )}
          </Block>

          <SimilarityBlock
            title="Yazım benzerliği"
            matches={data.lookalikes}
            emptyText="Bu alan adına yazımca belirgin biçimde benzeyen başka bir alan adı bulunmadı."
          />
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function Screenshot({ data, pageUrl }: { data: NonNullable<VisualModuleResult['data']>; pageUrl: string | null }) {
  return (
    <figure>
      <div className="overflow-hidden rounded-xl border border-line-strong bg-white">
        <div className="flex items-center gap-2 border-b border-line bg-paper-deep px-3 py-2" aria-hidden>
          <span className="flex gap-1.5">
            <span className="size-2.5 rounded-full bg-line-strong" />
            <span className="size-2.5 rounded-full bg-line-strong" />
            <span className="size-2.5 rounded-full bg-line-strong" />
          </span>
          {pageUrl && <span className="ml-2 min-w-0 truncate rounded-md bg-card px-2 py-0.5 font-mono text-[12px] text-ink-muted">{displayUrl(pageUrl)}</span>}
        </div>
        {data.screenshotUrl ? (
          <img src={data.screenshotUrl} alt={data.screenshotAlt} loading="lazy" width={1366} height={768} className="block aspect-[1366/768] w-full object-cover object-top" />
        ) : (
          <div className="flex aspect-[1366/768] flex-col items-center justify-center gap-2 bg-[repeating-linear-gradient(135deg,var(--color-paper)_0_12px,var(--color-paper-deep)_12px_24px)] p-6 text-center">
            <ImageOff aria-hidden className="size-8 text-ink-muted" />
            <p className="text-[15px] font-bold text-ink">Ekran görüntüsü yok</p>
          </div>
        )}
      </div>
      <figcaption className="mt-2 text-[13px] text-ink-muted">
        {data.screenshotUrl ? `Güvenli ortamda alınan ekran görüntüsü · ${data.viewport}` : 'Bu analizde ekran görüntüsü alınamadı.'}
      </figcaption>
    </figure>
  );
}

export function VisualDetails({ module, pageUrl, assessed }: { module: VisualModuleResult; pageUrl: string | null; assessed?: boolean }) {
  if (module.status !== 'completed' || !module.data) {
    return (
      <div className="rounded-xl border-2 border-dashed border-line-strong bg-[repeating-linear-gradient(135deg,var(--color-paper)_0_12px,var(--color-card)_12px_24px)] p-5 sm:p-7">
        <ModuleUnavailable module={module} assessed={assessed} />
      </div>
    );
  }
  const data = module.data;
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
      <Screenshot data={data} pageUrl={pageUrl} />
      <div className="space-y-6">
        {data.embedding && (
          <Block title="Görsel özellikler">
            <Facts items={[
              { label: 'Model', value: data.embedding.modelId },
              { label: 'Vektör boyutu', value: `${data.embedding.dimensions}` },
              { label: 'Görüntü boyutu', value: `${data.embedding.imageWidth} × ${data.embedding.imageHeight}` },
              { label: 'Normalizasyon', value: data.embedding.normalized ? 'L2' : 'Yok' },
            ]} />
            <p className="mt-3 text-[13px] text-ink-muted">Görüntü kırpılmadan 224 × 224 alana sığdırılır. Bu özellikler tek başına güvenlik kararı vermez.</p>
          </Block>
        )}
        <SimilarityBlock
          title="En yakın görsel eşleşme"
          matches={data.closestMatch ? [data.closestMatch] : []}
          emptyText={data.reference?.status === 'unavailable'
            ? 'Referans görsel deposu henüz yapılandırılmadı; görsel benzerlik karşılaştırması yapılmadı.'
            : 'Bilinen sayfalarla belirgin bir görsel eşleşme bulunmadı.'}
        />
        <Block title="Bulgular">
          <FindingList findings={module.findings} />
        </Block>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

const PHRASE_STYLES: Record<KeyPhrase['category'], string> = {
  urgency: 'bg-amber-soft text-amber border-amber/25',
  credentials: 'bg-coral-soft text-coral border-coral/25',
  payment: 'bg-coral-soft text-coral border-coral/25',
  reward: 'bg-amber-soft text-amber border-amber/25',
  neutral: 'bg-paper-deep text-ink-soft border-line-strong',
};

export function TextDetails({ module, assessed }: { module: TextModuleResult; assessed?: boolean }) {
  if (module.status !== 'completed' || !module.data) return <ModuleUnavailable module={module} assessed={assessed} />;
  const data = module.data;
  return (
    <div className="space-y-6">
      <Block title="Sayfadaki metinden alıntı" aside={<span className="text-[13px] font-semibold text-ink-muted">{data.language} · {formatNumber(data.wordCount)} kelime</span>}>
        {data.excerpt ? (
          <blockquote className="border-l-4 border-line-strong bg-paper py-3 pl-4 pr-3 text-[16px] leading-7 text-ink">“{data.excerpt}”</blockquote>
        ) : (
          <p className="text-[15px] text-ink-muted">Sayfada okunabilir metin bulunamadı.</p>
        )}
      </Block>

      <Block title="Dikkat çeken ifadeler">
        {data.keyPhrases.length ? (
          <ul className="flex flex-wrap gap-2">
            {data.keyPhrases.map((item) => (
              <li key={item.phrase} className={`rounded-lg border px-3 py-1.5 ${PHRASE_STYLES[item.category]}`}>
                <span className="block text-[15px] font-semibold">“{item.phrase}”</span>
                <span className="block text-[12px] font-bold opacity-90">{PHRASE_CATEGORY_LABELS[item.category]}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[15px] text-ink-muted">Dikkat çeken bir ifade bulunmadı.</p>
        )}
      </Block>

      <SimilarityBlock title="Metin benzerliği" matches={data.closestMatch ? [data.closestMatch] : []} emptyText="Metin, bilinen sayfalarla belirgin bir benzerlik göstermiyor." />

      <Block title="Bulgular">
        <FindingList findings={module.findings} />
      </Block>
    </div>
  );
}

/* ------------------------------------------------------------------ */

export function HtmlDetails({ module, assessed }: { module: HtmlModuleResult; assessed?: boolean }) {
  if (module.status !== 'completed' || !module.data) return <ModuleUnavailable module={module} assessed={assessed} />;
  const data = module.data;
  return (
    <div className="space-y-6">
      <Block title="Yapı sinyalleri" aside={<span className="text-[13px] text-ink-muted">Sayfa başlığı: <span className="font-semibold text-ink-soft">{data.title ?? 'yok'}</span></span>}>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-left text-[15px]">
            <caption className="sr-only">HTML yapısında incelenen sinyaller</caption>
            <thead className="bg-paper text-[13px] text-ink-muted">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-bold">Sinyal</th>
                <th scope="col" className="px-4 py-2.5 font-bold">Değer</th>
                <th scope="col" className="px-4 py-2.5 font-bold">Durum</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.signals.map((signal) => (
                <tr key={signal.label}>
                  <th scope="row" className="px-4 py-3 font-semibold text-ink">{signal.label}</th>
                  <td className="px-4 py-3 font-mono text-[14px] text-ink-soft break-all">{signal.value}</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {signal.flagged ? (
                      <span className="inline-flex items-center gap-1.5 text-[13px] font-bold text-amber">
                        <Flag aria-hidden className="size-4" /> Dikkat
                      </span>
                    ) : (
                      <span className="text-[13px] font-semibold text-ink-muted">Olağan</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Block>

      <SimilarityBlock title="Yapısal benzerlik" matches={data.closestMatch ? [data.closestMatch] : []} emptyText="HTML yapısı, bilinen sayfalarla belirgin bir benzerlik göstermiyor." />

      <Block title="Bulgular">
        <FindingList findings={module.findings} />
      </Block>
    </div>
  );
}
