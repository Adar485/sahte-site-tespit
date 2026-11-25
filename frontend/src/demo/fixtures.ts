/**
 * Örnek analiz senaryoları.
 *
 * Tüm alan adları IANA tarafından ayrılmış örnek alan adlarıdır
 * (example.com/.net/.org, .test, .invalid). Gerçek bir web sitesine dair
 * herhangi bir iddia içermez.
 */
import type {
  AnalysisFailure,
  AnalysisModules,
  AnalysisResult,
  AnalysisStage,
  HtmlModuleResult,
  TextModuleResult,
  UrlModuleData,
  VisualModuleResult,
} from '../types/analysis';

export type ScenarioKey = 'low' | 'suspicious' | 'high' | 'partial_url_only' | 'missing_content' | 'unreachable' | 'timeout';

export interface ScenarioContext {
  id: string;
  submittedUrl: string;
  requestedAt: string;
  completedAt: string;
  durationMs: number;
}

export interface DemoScenario {
  key: ScenarioKey;
  /** Demo listesinde gösterilen beklenen sonuç. */
  label: string;
  description: string;
  sampleUrl: string;
  hosts: string[];
  /** Her aşamanın demo süresi (ms). Başarısız senaryolarda son eleman hatanın oluştuğu aşamadır. */
  timeline: number[];
  build(context: ScenarioContext): AnalysisResult;
}

function urlParts(url: string): Pick<UrlModuleData, 'hostname' | 'topLevelDomain' | 'usesHttps' | 'urlLength'> {
  const parsed = new URL(url);
  const labels = parsed.hostname.split('.');
  return {
    hostname: parsed.hostname,
    topLevelDomain: labels[labels.length - 1] ?? '',
    usesHttps: parsed.protocol === 'https:',
    urlLength: url.length,
  };
}

function base(context: ScenarioContext) {
  return {
    id: context.id,
    submittedUrl: context.submittedUrl,
    requestedAt: context.requestedAt,
    completedAt: context.completedAt,
    durationMs: context.durationMs,
    analysisMode: 'full' as AnalysisResult['analysisMode'],
    modelVersion: null,
    isDemo: true as const,
  };
}

function skippedContentModules(reason: string): Omit<AnalysisModules, 'url'> {
  const visual: VisualModuleResult = {
    key: 'visual',
    status: 'skipped',
    summary: 'Görsel analiz çalıştırılmadı.',
    unavailableReason: reason,
    findings: [],
    data: null,
  };
  const text: TextModuleResult = {
    key: 'text',
    status: 'skipped',
    summary: 'Metin analizi çalıştırılmadı.',
    unavailableReason: reason,
    findings: [],
    data: null,
  };
  const html: HtmlModuleResult = {
    key: 'html',
    status: 'skipped',
    summary: 'HTML yapısı analizi çalıştırılmadı.',
    unavailableReason: reason,
    findings: [],
    data: null,
  };
  return { visual, text, html };
}

/* ------------------------------------------------------------------ */
/* Düşük risk                                                          */
/* ------------------------------------------------------------------ */

const low: DemoScenario = {
  key: 'low',
  label: 'Düşük risk',
  description: 'Belirgin bir phishing işareti taşımayan bilgilendirme sayfası.',
  sampleUrl: 'https://www.example.com/',
  hosts: ['example.com', 'www.example.com'],
  timeline: [900, 1300, 1700, 800],
  build(context) {
    const parts = urlParts(context.submittedUrl);
    return {
      ...base(context),
      finalUrl: context.submittedUrl,
      status: 'completed',
      failure: null,
      risk: {
        level: 'low',
        score: 12,
        summary: 'İncelenen dört bölümde belirgin bir phishing işareti bulunmadı.',
        recommendation:
          'Düşük risk, sitenin güvenli olduğu anlamına gelmez. Kişisel bilgilerinizi yalnızca adresini kendiniz yazdığınız ya da doğruladığınız sitelerle paylaşın.',
      },
      modules: {
        url: {
          key: 'url',
          status: 'completed',
          summary: 'Adreste yazım hilesi ya da olağan dışı yönlendirme görülmedi.',
          findings: [
            {
              id: 'low-url-1',
              severity: 'info',
              title: 'Alan adı başka bir adı taklit etmiyor',
              description: 'Alan adında harf değişimi, ek kelime ya da benzer görünen karakter bulunmadı.',
            },
            {
              id: 'low-url-2',
              severity: 'info',
              title: 'Bağlantı HTTPS ile şifreleniyor',
              description:
                'Şifreli bağlantı, verinin yolda okunmasını zorlaştırır; ancak sitenin kime ait olduğunu tek başına kanıtlamaz.',
            },
          ],
          data: {
            ...parts,
            registeredDomain: 'example.com',
            subdomains: parts.hostname.startsWith('www.') ? ['www'] : [],
            redirectChain: [],
            lookalikes: [],
          },
        },
        visual: {
          key: 'visual',
          status: 'completed',
          summary: 'Sayfa, tanınan bir giriş ekranına benzemiyor.',
          findings: [
            {
              id: 'low-visual-1',
              severity: 'info',
              title: 'Giriş ya da ödeme ekranı görünümü yok',
              description: 'Sayfa yalnızca başlık, kısa bir metin ve bağlantıdan oluşuyor.',
            },
          ],
          data: {
            screenshotUrl: '/demo/screenshot-low.svg',
            screenshotAlt: 'Başlık, iki paragraf metin ve tek bir bağlantıdan oluşan sade bilgilendirme sayfası.',
            viewport: '1366 × 768',
            closestMatch: { reference: 'Genel bilgilendirme sayfası şablonu', score: 0.36 },
          },
        },
        text: {
          key: 'text',
          status: 'completed',
          summary: 'Metinde kimlik bilgisi, ödeme ya da acil işlem isteği yok.',
          findings: [
            {
              id: 'low-text-1',
              severity: 'info',
              title: 'Baskı oluşturan ifade bulunmadı',
              description: 'Sayfa metni bilgilendirme amaçlı; kullanıcıdan bir işlem yapması istenmiyor.',
            },
          ],
          data: {
            language: 'Türkçe',
            wordCount: 64,
            excerpt:
              'Bu alan adı, belgelerde örnek olarak kullanılmak üzere ayrılmıştır. Önceden izin almadan yayınlarınızda kullanabilirsiniz.',
            keyPhrases: [{ phrase: 'örnek olarak kullanılmak üzere', category: 'neutral' }],
            closestMatch: null,
          },
        },
        html: {
          key: 'html',
          status: 'completed',
          summary: 'Sayfada form, gizli çerçeve ya da dış kaynaklı betik yok.',
          findings: [],
          data: {
            title: 'Örnek Alan Adı',
            signals: [
              { label: 'Form sayısı', value: '0', flagged: false },
              { label: 'Parola alanı', value: 'Yok', flagged: false },
              { label: 'Başka alan adına gönderilen form', value: 'Yok', flagged: false },
              { label: 'Gizli iframe', value: '0', flagged: false },
              { label: 'Dış kaynaklı betik oranı', value: '%0', flagged: false },
              { label: 'Sağ tık veya kopyalama engeli', value: 'Yok', flagged: false },
            ],
            closestMatch: null,
          },
        },
      },
    };
  },
};

/* ------------------------------------------------------------------ */
/* Şüpheli                                                             */
/* ------------------------------------------------------------------ */

const suspicious: DemoScenario = {
  key: 'suspicious',
  label: 'Şüpheli',
  description: 'Destek sayfası görünümünde, hesap bilgisi güncellemesi isteyen sayfa.',
  sampleUrl: 'https://example-destek.test/hesap/guncelle',
  hosts: ['example-destek.test', 'www.example-destek.test'],
  timeline: [1000, 1400, 1900, 900],
  build(context) {
    const parts = urlParts(context.submittedUrl);
    return {
      ...base(context),
      finalUrl: context.submittedUrl,
      status: 'completed',
      failure: null,
      risk: {
        level: 'suspicious',
        score: 58,
        summary:
          'Sayfa bir destek ekranı gibi görünüyor ve hesap bilgilerinizi kısa süre içinde güncellemenizi istiyor. Bazı işaretler dikkat gerektiriyor.',
        recommendation:
          'Bu sayfaya bilgi girmeyin. Hesabınızı kontrol etmek istiyorsanız hizmet sağlayıcınızın adresini tarayıcıya kendiniz yazın.',
      },
      modules: {
        url: {
          key: 'url',
          status: 'completed',
          summary: 'Alan adı, başka bir adın sonuna kelime eklenerek oluşturulmuş.',
          findings: [
            {
              id: 'sus-url-1',
              severity: 'medium',
              title: 'Alan adına “-destek” eklenmiş',
              description:
                '“example-destek” adı, “example” adının sonuna “-destek” eklenerek oluşturulmuş. Bu kalıp, resmî bir destek sayfası izlenimi vermek için sık kullanılır.',
            },
            {
              id: 'sus-url-2',
              severity: 'low',
              title: 'Adres yolunda hesap güncelleme ifadesi var',
              description: '“/hesap/guncelle” yolu, kullanıcıyı hesabıyla ilgili bir işlem yapmaya yönlendiriyor.',
            },
          ],
          data: {
            ...parts,
            registeredDomain: 'example-destek.test',
            subdomains: [],
            redirectChain: [],
            lookalikes: [{ reference: 'example.com', score: 0.78 }],
          },
        },
        visual: {
          key: 'visual',
          status: 'completed',
          summary: 'Sayfa düzeni bilinen bir destek sayfasına kısmen benziyor.',
          findings: [
            {
              id: 'sus-visual-1',
              severity: 'medium',
              title: 'Yerleşim ve renkler bir referans sayfaya yakın',
              description: 'Üst menü, renkler ve form yerleşimi benzer; logo alanı ve alt bilgi ise farklı.',
            },
          ],
          data: {
            screenshotUrl: '/demo/screenshot-suspicious.svg',
            screenshotAlt: 'Üstte destek merkezi başlığı, altında ad, e-posta ve telefon alanlarından oluşan bir güncelleme formu.',
            viewport: '1366 × 768',
            closestMatch: { reference: 'example.com destek sayfası', score: 0.64 },
          },
        },
        text: {
          key: 'text',
          status: 'completed',
          summary: 'Metin, süre baskısıyla bilgi güncellemesi istiyor.',
          findings: [
            {
              id: 'sus-text-1',
              severity: 'medium',
              title: 'Aciliyet baskısı oluşturan ifadeler var',
              description: '“24 saat içinde” ve “hizmetinizin kesintiye uğramaması için” gibi ifadeler, düşünmeden işlem yapmaya yönlendirir.',
            },
          ],
          data: {
            language: 'Türkçe',
            wordCount: 182,
            excerpt:
              'Hesabınızda olağan dışı bir etkinlik tespit ettik. Hizmetinizin kesintiye uğramaması için iletişim bilgilerinizi 24 saat içinde güncelleyin.',
            keyPhrases: [
              { phrase: '24 saat içinde', category: 'urgency' },
              { phrase: 'kesintiye uğramaması için', category: 'urgency' },
              { phrase: 'bilgilerinizi güncelleyin', category: 'credentials' },
            ],
            closestMatch: { reference: 'example.com destek sayfası', score: 0.52 },
          },
        },
        html: {
          key: 'html',
          status: 'completed',
          summary: 'Tek bir iletişim formu var; betiklerin çoğu dış kaynaklardan yükleniyor.',
          findings: [
            {
              id: 'sus-html-1',
              severity: 'low',
              title: 'Betiklerin çoğu dış kaynaklardan geliyor',
              description: 'Sayfadaki betiklerin yaklaşık üçte ikisi farklı alan adlarından yükleniyor.',
            },
          ],
          data: {
            title: 'Destek Merkezi – Hesap Güncelleme',
            signals: [
              { label: 'Form sayısı', value: '1', flagged: false },
              { label: 'Parola alanı', value: 'Yok', flagged: false },
              { label: 'E-posta ve telefon alanı', value: 'Var', flagged: false },
              { label: 'Başka alan adına gönderilen form', value: 'Yok', flagged: false },
              { label: 'Gizli iframe', value: '0', flagged: false },
              { label: 'Dış kaynaklı betik oranı', value: '%62', flagged: true },
            ],
            closestMatch: { reference: 'example.com destek sayfası', score: 0.48 },
          },
        },
      },
    };
  },
};

/* ------------------------------------------------------------------ */
/* Yüksek phishing riski                                               */
/* ------------------------------------------------------------------ */

const HIGH_FINAL_URL = 'https://oturum.examp1e-guvenlik.test/giris?ref=eposta';

const high: DemoScenario = {
  key: 'high',
  label: 'Yüksek phishing riski',
  description: 'Yönlendirmeyle açılan, bilinen bir oturum açma ekranını taklit eden sayfa.',
  sampleUrl: 'http://examp1e.test/giris',
  hosts: ['examp1e.test', 'www.examp1e.test', 'oturum.examp1e-guvenlik.test', 'examp1e-guvenlik.test'],
  timeline: [1100, 1600, 2000, 900],
  build(context) {
    const parts = urlParts(HIGH_FINAL_URL);
    return {
      ...base(context),
      finalUrl: HIGH_FINAL_URL,
      status: 'completed',
      failure: null,
      risk: {
        level: 'high',
        score: 91,
        summary:
          'Sayfa, tanınan bir oturum açma ekranını yakından taklit ediyor ve girilen parolayı başka bir alan adına gönderiyor.',
        recommendation:
          'Bu sayfaya parola, kart bilgisi ya da doğrulama kodu girmeyin. Bilgi girdiyseniz parolanızı hemen değiştirin ve hizmet sağlayıcınıza bildirin.',
      },
      modules: {
        url: {
          key: 'url',
          status: 'completed',
          summary: 'Alan adında harf yerine rakam kullanılmış ve adres iki kez yönlendiriliyor.',
          findings: [
            {
              id: 'high-url-1',
              severity: 'high',
              title: '“l” harfi yerine “1” rakamı kullanılmış',
              description:
                '“examp1e” adı, hızlı okunduğunda “example” gibi görünüyor. Bu, okuyanı yanıltmaya yönelik bir yazım benzerliği.',
            },
            {
              id: 'high-url-2',
              severity: 'medium',
              title: 'Bağlantı farklı bir alan adına yönlendiriliyor',
              description: 'Gönderdiğiniz adres iki yönlendirmeden sonra başka bir alan adındaki oturum açma sayfasına ulaştı.',
            },
            {
              id: 'high-url-3',
              severity: 'low',
              title: 'İlk bağlantı şifrelenmemiş',
              description: 'Gönderilen adres HTTP ile başlıyor; son sayfa HTTPS kullanıyor.',
            },
          ],
          data: {
            ...parts,
            registeredDomain: 'examp1e-guvenlik.test',
            subdomains: ['oturum'],
            redirectChain: [context.submittedUrl, 'https://kisa.examp1e.test/r/8f2a', HIGH_FINAL_URL],
            lookalikes: [
              { reference: 'example.com', score: 0.91 },
              { reference: 'example.net', score: 0.83 },
            ],
          },
        },
        visual: {
          key: 'visual',
          status: 'completed',
          summary: 'Sayfa, bilinen bir oturum açma ekranının neredeyse aynısı.',
          findings: [
            {
              id: 'high-visual-1',
              severity: 'high',
              title: 'Oturum açma ekranı büyük ölçüde kopyalanmış',
              description:
                'Yerleşim, renkler ve logo alanı referans sayfayla büyük ölçüde örtüşüyor; ancak sayfa referansın alan adında yayınlanmıyor.',
            },
          ],
          data: {
            screenshotUrl: '/demo/screenshot-high.svg',
            screenshotAlt: 'Ortada logo alanı, e-posta, parola ve doğrulama kodu alanları ile “Oturum aç” düğmesi bulunan giriş formu.',
            viewport: '1366 × 768',
            closestMatch: { reference: 'example.com oturum açma sayfası', score: 0.94 },
          },
        },
        text: {
          key: 'text',
          status: 'completed',
          summary: 'Metin, hesabın askıya alındığını söyleyip parola ve doğrulama kodu istiyor.',
          findings: [
            {
              id: 'high-text-1',
              severity: 'high',
              title: 'Parola ve doğrulama kodu birlikte isteniyor',
              description: 'Meşru hizmetler, doğrulama kodunu parola ile aynı formda nadiren ister.',
            },
            {
              id: 'high-text-2',
              severity: 'medium',
              title: 'Hesap askıya alındı uyarısı',
              description: 'Hesabın kapatılacağı ya da askıya alındığı uyarısı, phishing sayfalarında sık görülen bir baskı yöntemidir.',
            },
          ],
          data: {
            language: 'Türkçe',
            wordCount: 96,
            excerpt:
              'Güvenliğiniz için oturumunuz askıya alındı. Hesabınızı yeniden etkinleştirmek için e-posta adresinizi, parolanızı ve telefonunuza gelen doğrulama kodunu girin.',
            keyPhrases: [
              { phrase: 'oturumunuz askıya alındı', category: 'urgency' },
              { phrase: 'parolanızı', category: 'credentials' },
              { phrase: 'doğrulama kodunu', category: 'credentials' },
            ],
            closestMatch: { reference: 'example.com oturum açma sayfası', score: 0.83 },
          },
        },
        html: {
          key: 'html',
          status: 'completed',
          summary: 'Parola formu başka bir alan adına gönderiliyor; sayfada gizli bir iframe var.',
          findings: [
            {
              id: 'high-html-1',
              severity: 'high',
              title: 'Form verisi farklı bir alan adına gönderiliyor',
              description: 'Girilen bilgiler, sayfanın kendi alan adı yerine “toplama.examp1e-veri.test” adresine gönderiliyor.',
            },
            {
              id: 'high-html-2',
              severity: 'medium',
              title: 'Gizli iframe bulundu',
              description: 'Görünmeyen bir çerçeve, kullanıcıdan habersiz başka bir sayfayı yüklüyor.',
            },
            {
              id: 'high-html-3',
              severity: 'low',
              title: 'Sağ tık ve kopyalama engellenmiş',
              description: 'Sayfanın kaynağını incelemeyi zorlaştıran bir betik çalışıyor.',
            },
          ],
          data: {
            title: 'Oturum Aç | Hesap Doğrulama',
            signals: [
              { label: 'Form sayısı', value: '1', flagged: false },
              { label: 'Parola alanı', value: 'Var', flagged: false },
              { label: 'Başka alan adına gönderilen form', value: 'toplama.examp1e-veri.test', flagged: true },
              { label: 'Gizli iframe', value: '1', flagged: true },
              { label: 'Dış kaynaklı betik oranı', value: '%80', flagged: true },
              { label: 'Sağ tık veya kopyalama engeli', value: 'Var', flagged: true },
            ],
            closestMatch: { reference: 'example.com oturum açma sayfası', score: 0.88 },
          },
        },
      },
    };
  },
};

/* ------------------------------------------------------------------ */
/* Kısmi: yalnızca URL incelenebildi                                   */
/* ------------------------------------------------------------------ */

const partialUrlOnly: DemoScenario = {
  key: 'partial_url_only',
  label: 'Kısmi analiz',
  description: 'Sayfa otomatik erişimi engellediği için yalnızca adres incelenebildi.',
  sampleUrl: 'https://kampanya.example.net/odul-kazandiniz',
  hosts: ['kampanya.example.net'],
  timeline: [1000, 1900, 400, 800],
  build(context) {
    const parts = urlParts(context.submittedUrl);
    return {
      ...base(context),
      analysisMode: 'url_only',
      finalUrl: null,
      status: 'partial',
      failure: null,
      risk: {
        level: 'suspicious',
        score: 47,
        summary:
          'Sayfa içeriğine erişilemedi; değerlendirme yalnızca adres üzerinden yapıldı. Adres, ödül kampanyalarında sık görülen kalıplar içeriyor.',
        recommendation:
          'Bu sonuç sınırlı veriye dayanıyor. Kampanyayı kurumun resmî kanallarından doğrulamadan kişisel bilgi paylaşmayın.',
      },
      modules: {
        url: {
          key: 'url',
          status: 'completed',
          summary: 'Adres, ödül vaadi içeren bir yol ve kampanya alt alan adı kullanıyor.',
          findings: [
            {
              id: 'par-url-1',
              severity: 'medium',
              title: 'Adreste ödül vaadi var',
              description: '“/odul-kazandiniz” yolu, kullanıcıyı hızlıca tıklamaya ve bilgi paylaşmaya yönlendirebilir.',
            },
            {
              id: 'par-url-2',
              severity: 'low',
              title: 'Kampanya alt alan adı',
              description: '“kampanya.” alt alan adı tek başına zararlı değildir, ancak ödül vaadiyle birlikte dikkat gerektirir.',
            },
          ],
          data: {
            ...parts,
            registeredDomain: 'example.net',
            subdomains: ['kampanya'],
            redirectChain: [],
            lookalikes: [],
          },
        },
        ...skippedContentModules('Sayfa otomatik erişimi engelledi (HTTP 403). Sayfa içeriği alınamadığı için bu bölüm çalıştırılmadı.'),
      },
    };
  },
};

/* ------------------------------------------------------------------ */
/* Kısmi: ekran görüntüsü ve metin eksik                               */
/* ------------------------------------------------------------------ */

const missingContent: DemoScenario = {
  key: 'missing_content',
  label: 'Eksik veri',
  description: 'Sayfa açıldı ama ekran görüntüsü ve görünür metin alınamadı.',
  sampleUrl: 'https://bos-sayfa.example.org/',
  hosts: ['bos-sayfa.example.org'],
  timeline: [900, 1500, 1800, 800],
  build(context) {
    const parts = urlParts(context.submittedUrl);
    return {
      ...base(context),
      finalUrl: context.submittedUrl,
      status: 'partial',
      failure: null,
      risk: {
        level: 'low',
        score: 24,
        summary:
          'İncelenebilen bölümlerde belirgin bir phishing işareti bulunmadı; ancak ekran görüntüsü ve metin alınamadığı için değerlendirme eksik.',
        recommendation:
          'Düşük risk bir güvence değildir. Sayfa daha sonra farklı içerik gösterebilir; bilgi girmeden önce adresi yeniden kontrol edin.',
      },
      modules: {
        url: {
          key: 'url',
          status: 'completed',
          summary: 'Adreste dikkat çeken bir kalıp bulunmadı.',
          findings: [
            {
              id: 'mis-url-1',
              severity: 'info',
              title: 'Alan adı başka bir adı taklit etmiyor',
              description: 'Yazım benzerliği ya da yönlendirme görülmedi.',
            },
          ],
          data: {
            ...parts,
            registeredDomain: 'example.org',
            subdomains: ['bos-sayfa'],
            redirectChain: [],
            lookalikes: [],
          },
        },
        visual: {
          key: 'visual',
          status: 'unavailable',
          summary: 'Ekran görüntüsü alınamadı.',
          unavailableReason:
            'Sayfa açıldı ancak yükleme süresi boyunca boş kaldı. Bu yüzden görsel karşılaştırma yapılamadı.',
          findings: [],
          data: {
            screenshotUrl: null,
            screenshotAlt: '',
            viewport: '1366 × 768',
            closestMatch: null,
          },
        },
        text: {
          key: 'text',
          status: 'unavailable',
          summary: 'Sayfada okunabilir metin bulunamadı.',
          unavailableReason:
            'Sayfa içeriği görsel ya da tuval (canvas) öğesi içinde olabilir veya metin sonradan yükleniyor olabilir.',
          findings: [],
          data: {
            language: 'Belirlenemedi',
            wordCount: 0,
            excerpt: null,
            keyPhrases: [],
            closestMatch: null,
          },
        },
        html: {
          key: 'html',
          status: 'completed',
          summary: 'Sayfa neredeyse boş bir HTML iskeletinden oluşuyor.',
          findings: [
            {
              id: 'mis-html-1',
              severity: 'info',
              title: 'İçerik betikle yükleniyor olabilir',
              description: 'Sayfada yalnızca birkaç betik ve boş bir kapsayıcı öğe var.',
            },
          ],
          data: {
            title: null,
            signals: [
              { label: 'Sayfa başlığı', value: 'Yok', flagged: false },
              { label: 'Form sayısı', value: '0', flagged: false },
              { label: 'Parola alanı', value: 'Yok', flagged: false },
              { label: 'Gizli iframe', value: '0', flagged: false },
              { label: 'Dış kaynaklı betik oranı', value: '%33', flagged: false },
            ],
            closestMatch: null,
          },
        },
      },
    };
  },
};

/* ------------------------------------------------------------------ */
/* Başarısız: ulaşılamayan sayfa ve zaman aşımı                         */
/* ------------------------------------------------------------------ */

function failedResult(
  context: ScenarioContext,
  failure: AnalysisFailure,
  urlSummary: string,
  urlFinding: { title: string; description: string },
  skipReason: string,
): AnalysisResult {
  const parts = urlParts(context.submittedUrl);
  const labels = parts.hostname.split('.');
  return {
    ...base(context),
    analysisMode: null,
    finalUrl: null,
    status: 'failed',
    failure,
    risk: null,
    modules: {
      url: {
        key: 'url',
        status: 'completed',
        summary: urlSummary,
        findings: [{ id: `${context.id}-url-1`, severity: 'info', ...urlFinding }],
        data: {
          ...parts,
          registeredDomain: labels.slice(-2).join('.'),
          subdomains: labels.slice(0, -2),
          redirectChain: [],
          lookalikes: [],
        },
      },
      ...skippedContentModules(skipReason),
    },
  };
}

const unreachable: DemoScenario = {
  key: 'unreachable',
  label: 'Ulaşılamayan sayfa',
  description: 'Alan adı çözümlenemediği için sayfa açılamadı.',
  sampleUrl: 'https://ulasilamayan.invalid/',
  hosts: ['ulasilamayan.invalid', 'www.ulasilamayan.invalid'],
  timeline: [900, 1700],
  build(context) {
    return failedResult(
      context,
      {
        code: 'unreachable',
        stage: 'page_fetch' satisfies AnalysisStage,
        message: 'Sayfaya ulaşılamadı. Alan adı çözümlenemedi ya da sunucu bağlantıyı kabul etmedi.',
      },
      'Adres incelendi; ancak sayfaya ulaşılamadığı için genel değerlendirme yapılamadı.',
      {
        title: 'Alan adı genel internette kullanılmıyor',
        description: '“.invalid” uzantısı, genel internette çözümlenmeyen ayrılmış bir uzantıdır.',
      },
      'Sayfaya ulaşılamadığı için bu bölüm çalıştırılmadı.',
    );
  },
};

const timeout: DemoScenario = {
  key: 'timeout',
  label: 'Zaman aşımı',
  description: 'Sunucu, izin verilen süre içinde yanıt vermedi.',
  sampleUrl: 'https://yavas.example.net/',
  hosts: ['yavas.example.net'],
  timeline: [900, 4200],
  build(context) {
    return failedResult(
      context,
      {
        code: 'timeout',
        stage: 'page_fetch',
        message:
          'Sayfa izin verilen süre içinde yanıt vermedi. Sunucu yoğun olabilir ya da bağlantıyı bilerek yavaşlatıyor olabilir.',
      },
      'Adres incelendi; sayfa zamanında yanıt vermediği için genel değerlendirme yapılamadı.',
      {
        title: 'Adreste dikkat çeken bir kalıp yok',
        description: 'Yalnızca adres üzerinden yapılan inceleme, tek başına bir değerlendirme için yeterli değil.',
      },
      'Sayfa zamanında yanıt vermediği için bu bölüm çalıştırılmadı.',
    );
  },
};

export const DEMO_SCENARIOS: DemoScenario[] = [low, suspicious, high, partialUrlOnly, missingContent, unreachable, timeout];

export function findScenario(url: string): DemoScenario | undefined {
  let host: string;
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch {
    return undefined;
  }
  return DEMO_SCENARIOS.find((scenario) => scenario.hosts.includes(host));
}

export function scenarioByKey(key: ScenarioKey): DemoScenario {
  const scenario = DEMO_SCENARIOS.find((item) => item.key === key);
  if (!scenario) throw new Error(`Bilinmeyen demo senaryosu: ${key}`);
  return scenario;
}
