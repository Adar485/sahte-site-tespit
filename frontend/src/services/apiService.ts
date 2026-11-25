import type { AnalysisJob, AnalyzeRequest, AnalyzeResponse } from '../types/analysis';
import { ServiceError, type AnalysisService, type RequestOptions } from './types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const REQUEST_TIMEOUT_MS = 15_000;

async function request<T>(path: string, init: RequestInit, options?: RequestOptions): Promise<T> {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const signal = options?.signal ? AbortSignal.any([options.signal, timeout]) : timeout;

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init.headers },
    });
  } catch (error) {
    if (options?.signal?.aborted) throw error;
    throw new ServiceError(
      'service_unavailable',
      'Analiz servisine bağlanılamadı. Servis kapalı olabilir ya da bağlantınızda bir sorun olabilir.',
    );
  }

  if (response.status === 404) {
    throw new ServiceError('not_found', 'Bu analiz sonucu bulunamadı. Silinmiş ya da süresi dolmuş olabilir.');
  }
  if (response.status === 400 || response.status === 422) {
    throw new ServiceError('bad_request', 'Servis bu adresi kabul etmedi. Adresi kontrol edip yeniden deneyin.');
  }
  if (!response.ok) {
    throw new ServiceError(
      'service_unavailable',
      'Analiz servisi şu anda yanıt veremiyor. Birkaç dakika sonra yeniden deneyin.',
    );
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ServiceError('invalid_response', 'Servisten beklenmeyen bir yanıt alındı.');
  }
}

/** FastAPI arka ucu hazır olduğunda VITE_ANALYSIS_MODE=api ile kullanılır. */
export const apiAnalysisService: AnalysisService = {
  pollIntervalMs: 1500,

  analyze(body: AnalyzeRequest, options?: RequestOptions) {
    return request<AnalyzeResponse>('/api/analyze', { method: 'POST', body: JSON.stringify(body) }, options);
  },

  getResult(id: string, options?: RequestOptions) {
    return request<AnalysisJob>(`/api/result/${encodeURIComponent(id)}`, { method: 'GET' }, options);
  },
};
