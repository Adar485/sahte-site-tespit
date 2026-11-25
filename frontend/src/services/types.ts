import type { AnalysisJob, AnalyzeRequest, AnalyzeResponse, HistoryPage, HistoryQuery } from '../types/analysis';

/**
 * - service_unavailable: sunucuya ulaşılamadı ya da sunucu hata verdi
 * - request_timeout:     tek bir HTTP isteği zamanında yanıtlanmadı
 * - client_timeout:      arayüz, sonucu beklerken belirlenen süreyi aştı (analizin kendisi başarısız sayılmaz)
 * - not_found:           bilinmeyen analiz kimliği
 * - bad_request:         sunucu isteği kabul etmedi (ör. geçersiz adres)
 * - invalid_response:    sunucudan beklenmeyen yanıt
 */
export type ServiceErrorCode =
  | 'service_unavailable'
  | 'request_timeout'
  | 'client_timeout'
  | 'not_found'
  | 'bad_request'
  | 'invalid_response';

export class ServiceError extends Error {
  readonly code: ServiceErrorCode;

  constructor(code: ServiceErrorCode, message: string) {
    super(message);
    this.name = 'ServiceError';
    this.code = code;
  }
}

export interface RequestOptions {
  signal?: AbortSignal;
}

/**
 * Arayüzün veri kaynağına dair bildiği tek sözleşme.
 * Canlı API istemcisi ve açıkça seçilen demo sağlayıcısı bu arayüzü uygular.
 */
export interface AnalysisService {
  /** POST /api/analyze */
  analyze(request: AnalyzeRequest, options?: RequestOptions): Promise<AnalyzeResponse>;
  /** GET /api/result/{id} */
  getResult(id: string, options?: RequestOptions): Promise<AnalysisJob>;
  /** GET /api/history */
  listHistory(query: HistoryQuery, options?: RequestOptions): Promise<HistoryPage>;
  /** DELETE /api/analyses/{id} */
  deleteAnalysis(id: string, options?: RequestOptions): Promise<void>;
  /** Yalnızca demo: tüm yerel geçmişi siler. Canlı modda tanımlı değildir. */
  clearHistory?(): Promise<void>;
  /** Yalnızca demo: boş geçmişe örnek kayıt ekler. */
  loadSamples?(): Promise<void>;
  /** Sonuç hazır değilken tekrar sorgulama aralığı (ms). */
  readonly pollIntervalMs: number;
}

export function toServiceError(error: unknown): ServiceError {
  if (error instanceof ServiceError) return error;
  return new ServiceError(
    'service_unavailable',
    'Analiz servisine şu anda ulaşılamıyor. Bağlantınızı kontrol edip birkaç dakika sonra yeniden deneyin.',
  );
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}
