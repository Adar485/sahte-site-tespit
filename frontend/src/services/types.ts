import type { AnalysisJob, AnalyzeRequest, AnalyzeResponse } from '../types/analysis';

export type ServiceErrorCode = 'service_unavailable' | 'not_found' | 'bad_request' | 'invalid_response';

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
 * Arayüzün analiz servisine dair bildiği tek sözleşme.
 * Demo sağlayıcısı ve gerçek API istemcisi bu arayüzü uygular.
 */
export interface AnalysisService {
  /** POST /api/analyze */
  analyze(request: AnalyzeRequest, options?: RequestOptions): Promise<AnalyzeResponse>;
  /** GET /api/result/{id} */
  getResult(id: string, options?: RequestOptions): Promise<AnalysisJob>;
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
