/**
 * Analiz alan modeli.
 *
 * FastAPI arka ucunun döndürdüğü JSON yapısıyla birebir eşleşir
 * (backend/app/schemas/analysis.py):
 *   POST   /api/analyze         -> AnalyzeResponse
 *   GET    /api/result/{id}     -> AnalysisJob
 *   GET    /api/history         -> HistoryPage
 *   DELETE /api/analyses/{id}   -> 204
 */

/** Genel risk düzeyi. Benzerlik puanlarından bağımsızdır. */
export type RiskLevel = 'low' | 'suspicious' | 'high';

/**
 * Analizin bütünsel durumu.
 * - completed: tüm modüller çalıştı
 * - partial:   en az bir modül veri üretemedi, sonuç eldeki verilerle hesaplandı
 * - failed:    risk değerlendirmesi yapılamadı
 */
export type AnalysisStatus = 'completed' | 'partial' | 'failed';

export type ModuleKey = 'url' | 'visual' | 'text' | 'html';

/**
 * - pending / running: modül henüz bitmedi
 * - completed:   modül çalıştı ve bulgu üretti
 * - unavailable: modül çalıştı ama incelenecek veri yoktu (ör. ekran görüntüsü alınamadı)
 * - skipped:     önceki bir adım başarısız olduğu için modül çalıştırılmadı
 * - failed:      modül hata ile sonlandı
 */
export type ModuleStatus = 'pending' | 'running' | 'completed' | 'unavailable' | 'skipped' | 'failed';

/** İlerleme ekranında gösterilen aşamalar. */
export type AnalysisStage = 'url_check' | 'page_fetch' | 'content_inspection' | 'scoring';

export type FailureCode = 'unreachable' | 'timeout' | 'service_unavailable' | 'unknown';

export type FindingSeverity = 'info' | 'low' | 'medium' | 'high';

export interface AnalyzeRequest {
  /** Canlı modda kullanıcının yazdığı adres (kırpılmış). Normalleştirmeyi arka uç yapar. */
  url: string;
}

export interface AnalyzeResponse {
  id: string;
  /** "done": istek hemen sonuçlandı (URL incelemesi her zaman böyledir). */
  state: 'queued' | 'running' | 'done';
  status?: string;
  error?: { code: string; message: string } | null;
}

export type AnalysisMode = 'full' | 'url_only';

export interface Finding {
  id: string;
  severity: FindingSeverity;
  title: string;
  description: string;
}

/**
 * Benzerlik puanı: incelenen sayfanın bir referansa ne kadar benzediği (0–1).
 * Bir olasılık ya da risk puanı DEĞİLDİR.
 */
export interface SimilarityMatch {
  reference: string;
  score: number;
}

interface ModuleBase<K extends ModuleKey, D> {
  key: K;
  status: ModuleStatus;
  /** Modülün tek cümlelik özeti. */
  summary: string;
  /** status completed değilse neden. */
  unavailableReason?: string;
  findings: Finding[];
  data: D | null;
  durationMs?: number | null;
}

export interface UrlModuleData {
  hostname: string;
  registeredDomain: string;
  topLevelDomain: string;
  subdomains: string[];
  usesHttps: boolean;
  urlLength: number;
  redirectChain: string[];
  lookalikes: SimilarityMatch[];
}

/**
 * Gerçek URL incelemesinin verisi (backend/app/services/url_inspection).
 * Yalnızca adres metninden elde edilir; risk puanı içermez.
 */
export interface UrlInspectionData {
  featureSchemaVersion: string;
  address: {
    normalizedUrl: string;
    scheme: 'http' | 'https';
    schemeAssumed: boolean;
    hostType: 'domain' | 'ipv4' | 'ipv6';
    /** ASCII (punycode) biçimi */
    hostname: string;
    unicodeHostname: string;
    /** Yalnızca adreste yazılıysa */
    port: number | null;
    effectivePort: number;
    /** null: bilinmiyor ya da uygulanamaz; "": alt alan adı yok */
    subdomain: string | null;
    registeredDomain: string | null;
    publicSuffix: string | null;
    /** IP adreslerinde null */
    suffixKnown: boolean | null;
    path: string;
    query: { parameterCount: number; names: string[]; repeatedNames: string[]; emptyValueCount: number };
    hasFragment: boolean;
    /** Yalnızca eski kayıtlarda; giriş bilgisi içeren adresler artık reddedilir. */
    hasCredentials?: boolean;
  };
  features: {
    normalizedUrlLength: number;
    hostnameLength: number;
    registeredDomainLength: number | null;
    subdomainCount: number | null;
    hostnameDigitRatio: number;
    hostnameHyphenCount: number;
    pathDepth: number;
    queryParameterCount: number;
    hasExplicitPort: boolean;
    isIpAddress: boolean;
    usesHttps: boolean;
    hasPercentEncoding: boolean;
    hasIdn: boolean;
  };
  unicode: {
    mixedScriptLabels: Array<{ label: string; scripts: string[] }>;
    confusableCharacters: Array<{ label: string; character: string; codePoint: string; script: string; looksLike: string }>;
  };
  reference: {
    status: 'available' | 'unavailable';
    reason: 'not_configured' | 'load_error' | 'empty_collection' | 'no_registered_domain' | null;
    collectionVersion: string | null;
    collectionSize: number;
    match: {
      reference: string;
      exactMatch: boolean;
      levenshteinSimilarity: number;
      jaroWinklerSimilarity: number;
    } | null;
  };
}

export interface VisualModuleData {
  embedding?: {
    modelId: string;
    modelRevision: string;
    preprocessingVersion: string;
    dimensions: number;
    normalized: boolean;
    imageWidth: number;
    imageHeight: number;
  };
  reference?: { status: 'available' | 'unavailable'; reason: string | null; collectionSize: number };
  /** Ekran görüntüsü yoksa null. */
  screenshotUrl: string | null;
  screenshotAlt: string;
  viewport: string;
  closestMatch: SimilarityMatch | null;
}

export interface KeyPhrase {
  phrase: string;
  category: 'urgency' | 'credentials' | 'payment' | 'reward' | 'neutral';
}

export interface TextModuleData {
  language: string;
  wordCount: number;
  /** Sayfadan alınan görünür metin özeti. Metin yoksa null. */
  excerpt: string | null;
  keyPhrases: KeyPhrase[];
  closestMatch: SimilarityMatch | null;
}

export interface HtmlSignal {
  label: string;
  value: string;
  flagged: boolean;
}

export interface HtmlModuleData {
  title: string | null;
  signals: HtmlSignal[];
  closestMatch: SimilarityMatch | null;
}

/** UrlModuleData örnek veride kullanılır; canlı kayıtlar UrlInspectionData taşır. */
export type UrlModuleResult = ModuleBase<'url', UrlModuleData | UrlInspectionData>;
export type VisualModuleResult = ModuleBase<'visual', VisualModuleData>;
export type TextModuleResult = ModuleBase<'text', TextModuleData>;
export type HtmlModuleResult = ModuleBase<'html', HtmlModuleData>;

export type ModuleResult = UrlModuleResult | VisualModuleResult | TextModuleResult | HtmlModuleResult;

export interface AnalysisModules {
  url: UrlModuleResult;
  visual: VisualModuleResult;
  text: TextModuleResult;
  html: HtmlModuleResult;
}

export interface RiskAssessment {
  level: RiskLevel;
  /** Modelin birleşik risk puanı (0–100). Bilinmiyorsa null. */
  score: number | null;
  summary: string | null;
  /** Kullanıcıya önerilen davranış. null ise arayüz düzeye göre genel öneriyi gösterir. */
  recommendation: string | null;
}

export interface AnalysisFailure {
  code: FailureCode;
  message: string;
  stage: AnalysisStage;
}

/**
 * Sayfa yakalama kaydı. Gözlemdir, değerlendirme değildir: görsel ve metin analizi
 * ayrıca yapılır. Ham HTML hiçbir zaman arayüze gönderilmez.
 */
export interface PageCapture {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'partial' | 'failed';
  requestedUrl: string;
  finalUrl: string | null;
  httpStatus: number | null;
  requestedAt: string;
  completedAt: string | null;
  durationMs: number | null;
  viewportWidth: number;
  viewportHeight: number;
  artifacts: { screenshot: boolean; html: boolean; text: boolean };
  /** Arka uç üzerindeki yol */
  screenshotUrl: string | null;
  /** Düz metin, ilk 2000 karakter */
  textPreview: string | null;
  textLength: number | null;
  redirected: boolean;
  /** false: parçalar alınırken sayfa adres değiştirdi */
  consistent: boolean | null;
  pageTitle: string | null;
  signals: { httpError?: boolean; blank?: boolean; captcha?: boolean } | null;
  error: { code: string; message: string } | null;
  captureVersion: string;
}

export interface AnalysisResult {
  id: string;
  submittedUrl: string;
  finalUrl: string | null;
  /** ISO 8601 */
  requestedAt: string;
  /** ISO 8601; bitmemiş analizlerde null. */
  completedAt: string | null;
  durationMs: number | null;
  status: AnalysisStatus;
  risk: RiskAssessment | null;
  failure: AnalysisFailure | null;
  modules: AnalysisModules;
  analysisMode: AnalysisMode | null;
  modelVersion: string | null;
  /** Sonuç örnek veriden mi üretildi? */
  isDemo: boolean;
  /** Eski kayıtlarda ve demo verisinde yoktur. */
  capture?: PageCapture | null;
}

export type AnalysisJob =
  | { id: string; state: 'queued' | 'running'; stage: AnalysisStage; submittedUrl: string }
  | { id: string; state: 'done'; result: AnalysisResult };

export interface HistoryEntry {
  id: string;
  submittedUrl: string;
  finalUrl: string | null;
  analyzedAt: string;
  status: AnalysisStatus | 'pending' | 'running';
  riskLevel: RiskLevel | null;
}

/** Geçmiş filtresinde kullanılan sonuç grupları. */
export type ResultFilter = 'all' | RiskLevel | 'failed';

/** GET /api/history sorgusu */
export interface HistoryQuery {
  search: string;
  result: ResultFilter;
  limit?: number;
}

/** GET /api/history yanıtı */
export interface HistoryPage {
  items: HistoryEntry[];
  /** Arama ve seçili filtreyle eşleşen kayıt sayısı. */
  total: number;
  /** Mevcut arama için filtre başına kayıt sayıları. */
  counts: Record<ResultFilter, number>;
}
