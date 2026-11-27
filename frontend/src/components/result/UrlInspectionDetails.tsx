import { formatNumber, formatPercent } from '../../lib/format';
import type { Finding, UrlInspectionData } from '../../types/analysis';
import { UrlText } from '../ui';
import { Block, Facts } from './blocks';
import { FindingList } from './FindingList';
import { SimilarityMeter } from './Similarity';

const HOST_TYPES = { domain: 'Alan adı', ipv4: 'IPv4 adresi', ipv6: 'IPv6 adresi' };

const REFERENCE_REASONS: Record<NonNullable<UrlInspectionData['reference']['reason']>, string> = {
  not_configured: 'Karşılaştırma yapılmadı: bir referans alan adı listesi tanımlanmamış.',
  load_error: 'Karşılaştırma yapılamadı: referans listesi okunamadı.',
  empty_collection: 'Karşılaştırma yapılamadı: referans listesinde kullanılabilir alan adı yok.',
  no_registered_domain: 'Karşılaştırma yapılamadı: bu adres için kayıtlı alan adı belirlenemiyor.',
};

const yesNo = (value: boolean) => (value ? 'Var' : 'Yok');
const mono = (value: string) => <UrlText url={value} />;

export function UrlInspectionDetails({ findings, data }: { findings: Finding[]; data: UrlInspectionData }) {
  const { address, features, unicode, reference } = data;
  const isIp = address.hostType !== 'domain';
  const missing = <span className="text-ink-muted">{isIp ? 'Uygulanamaz (IP adresi)' : 'Belirlenemedi'}</span>;
  const optionalNumber = (value: number | null) => (value === null ? missing : formatNumber(value));
  const { query } = address;

  return (
    <div className="space-y-6">
      <Block title="Bulgular">
        <FindingList findings={findings} emptyText="Bu adres için ek bir gözlem yok. Bu, adresin güvenli olduğu anlamına gelmez." />
      </Block>

      <Block title="Adres bilgileri">
        <Facts
          items={[
            { label: 'Normalleştirilmiş adres', value: mono(address.normalizedUrl) },
            { label: 'Şema', value: `${address.scheme.toUpperCase()}${address.schemeAssumed ? ' (varsayıldı)' : ''}` },
            { label: 'Ana makine türü', value: HOST_TYPES[address.hostType] },
            { label: 'Ana makine', value: mono(address.unicodeHostname) },
            ...(address.hostname !== address.unicodeHostname ? [{ label: 'ASCII (IDNA) karşılığı', value: mono(address.hostname) }] : []),
            { label: 'Port', value: address.port ?? `Yazılmamış (varsayılan ${address.effectivePort})` },
            { label: 'Alt alan adı', value: address.subdomain === null ? missing : address.subdomain ? mono(address.subdomain) : 'Yok' },
            { label: 'Kayıtlı alan adı', value: address.registeredDomain ? mono(address.registeredDomain) : missing },
            { label: 'Genel uzantı', value: address.publicSuffix ? mono(address.publicSuffix) : missing },
            { label: 'Yol', value: mono(address.path) },
            { label: 'Sorgu parametre adları', value: query.names.length ? mono(query.names.join(', ')) : 'Yok' },
            { label: 'Tekrarlanan parametreler', value: query.repeatedNames.length ? mono(query.repeatedNames.join(', ')) : 'Yok' },
            { label: 'Boş değerli parametre sayısı', value: formatNumber(query.emptyValueCount) },
            { label: 'Parça (#) bölümü', value: yesNo(address.hasFragment) },
            ...(address.hasCredentials ? [{ label: 'Adreste kullanıcı bilgisi', value: 'Var' }] : []),
          ]}
        />
      </Block>

      <Block title="Ölçülen özellikler" aside={<span className="text-[13px] font-semibold text-ink-muted">Şema sürümü {data.featureSchemaVersion}</span>}>
        <Facts
          items={[
            { label: 'Normalleştirilmiş adres uzunluğu', value: `${formatNumber(features.normalizedUrlLength)} karakter` },
            { label: 'Ana makine uzunluğu', value: `${formatNumber(features.hostnameLength)} karakter` },
            { label: 'Kayıtlı alan adı uzunluğu', value: optionalNumber(features.registeredDomainLength) },
            { label: 'Alt alan adı sayısı', value: optionalNumber(features.subdomainCount) },
            { label: 'Ana makinede rakam oranı', value: formatPercent(features.hostnameDigitRatio) },
            { label: 'Ana makinede tire sayısı', value: formatNumber(features.hostnameHyphenCount) },
            { label: 'Yol derinliği', value: formatNumber(features.pathDepth) },
            { label: 'Sorgu parametresi sayısı', value: formatNumber(features.queryParameterCount) },
            { label: 'Açıkça yazılmış port', value: yesNo(features.hasExplicitPort) },
            { label: 'IP adresi kullanımı', value: yesNo(features.isIpAddress) },
            { label: 'HTTPS şeması', value: yesNo(features.usesHttps) },
            { label: 'Yüzde kodlaması', value: yesNo(features.hasPercentEncoding) },
            { label: 'IDN / punycode', value: yesNo(features.hasIdn) },
          ]}
        />
      </Block>

      <Block title="Karakter incelemesi">
        <Facts
          items={[
            {
              label: 'Birden fazla yazı sistemi içeren bölümler',
              value: unicode.mixedScriptLabels.length ? mono(unicode.mixedScriptLabels.map((item) => item.label).join(', ')) : 'Tespit edilmedi',
            },
            {
              label: 'Karıştırılabilecek karakterler',
              value: unicode.confusableCharacters.length
                ? unicode.confusableCharacters.map((item) => `${item.character} (${item.codePoint}) ≈ ${item.looksLike}`).join(', ')
                : 'Tespit edilmedi',
            },
          ]}
        />
        <p className="mt-3 text-[13px] leading-5 text-ink-muted">
          Bu kontrol tüm taklit yöntemlerini kapsamaz; örneğin “0” ile “o” ya da “rn” ile “m” benzerliğini yakalamaz.
        </p>
      </Block>

      <Block
        title="Yazım benzerliği"
        aside={
          reference.collectionVersion && (
            <span className="text-[13px] font-semibold text-ink-muted">
              Referans listesi {reference.collectionVersion} · {formatNumber(reference.collectionSize)} alan adı
            </span>
          )
        }
      >
        {reference.match ? (
          <div className="space-y-4">
            <p className="text-[15px] text-ink">
              En yakın referans: {mono(reference.match.reference)}
              {reference.match.exactMatch && ' (birebir aynı)'}
            </p>
            <SimilarityMeter label="Levenshtein" match={{ reference: reference.match.reference, score: reference.match.levenshteinSimilarity }} />
            <SimilarityMeter label="Jaro-Winkler" match={{ reference: reference.match.reference, score: reference.match.jaroWinklerSimilarity }} />
            <p className="text-[13px] leading-5 text-ink-muted">
              Yalnızca alan adının yazım benzerliğidir; risk puanı ya da olasılık değildir. Birebir eşleşme de güvenlik garantisi
              vermez.
            </p>
          </div>
        ) : (
          <p className="text-[15px] text-ink-muted">
            {reference.reason ? REFERENCE_REASONS[reference.reason] : 'Karşılaştırma sonucu yok.'}
          </p>
        )}
      </Block>

      <p className="text-[13px] leading-5 text-ink-muted">Bu bölüm yalnızca adres metnine dayanır; DNS, sertifika ve alan adı kaydı incelenmedi.</p>
    </div>
  );
}
