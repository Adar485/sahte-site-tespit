/**
 * Analiz alan modeli.
 *
 * Bu tipler, ileride FastAPI arka ucunun döndüreceği JSON yapısıyla
 * birebir eşleşecek şekilde tasarlanmıştır:
 *   POST /api/analyze      -> AnalyzeResponse
 *   GET  /api/result/{id}  -> AnalysisJob
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
 * - completed:   modül çalıştı ve bulgu üretti
 * - unavailable: modül çalıştı ama incelenecek veri yoktu (ör. ekran görüntüsü alınamadı)
 * - skipped:     önceki bir adım başarısız olduğu için modül çalıştırılmadı
 * - failed:      modül hata ile sonlandı
 */
export type ModuleStatus = 'completed' | 'unavailable' | 'skipped' | 'failed';

/** İlerleme ekranında gösterilen aşamalar. */
export type AnalysisStage = 'url_check' | 'page_fetch' | 'content_inspection' | 'scoring';

export type FailureCode = 'unreachable' | 'timeout' | 'service_unavailable' | 'unknown';

export type FindingSeverity = 'info' | 'low' | 'medium' | 'high';

export interface AnalyzeRequest {
  /** Normalleştirilmiş, http(s) şemalı tam adres. */
  url: string;
}

export interface AnalyzeResponse {
  id: string;
  state: 'queued' | 'running';
}

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

export interface VisualModuleData {
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

export type UrlModuleResult = ModuleBase<'url', UrlModuleData>;
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
  /** Modelin birleşik risk puanı (0–100). */
  score: number;
  summary: string;
  /** Kullanıcıya önerilen davranış. */
  recommendation: string;
}

export interface AnalysisFailure {
  code: FailureCode;
  message: string;
  stage: AnalysisStage;
}

export interface AnalysisResult {
  id: string;
  submittedUrl: string;
  finalUrl: string | null;
  /** ISO 8601 */
  requestedAt: string;
  /** ISO 8601 */
  completedAt: string;
  durationMs: number;
  status: AnalysisStatus;
  risk: RiskAssessment | null;
  failure: AnalysisFailure | null;
  modules: AnalysisModules;
  /** Sonuç örnek veriden mi üretildi? */
  isDemo: boolean;
}

export type AnalysisJob =
  | { id: string; state: 'queued' | 'running'; stage: AnalysisStage; submittedUrl: string }
  | { id: string; state: 'done'; result: AnalysisResult };

export interface HistoryEntry {
  id: string;
  submittedUrl: string;
  finalUrl: string | null;
  analyzedAt: string;
  status: AnalysisStatus;
  riskLevel: RiskLevel | null;
}

/** Geçmiş filtresinde kullanılan sonuç grupları. */
export type ResultFilter = 'all' | RiskLevel | 'failed';
