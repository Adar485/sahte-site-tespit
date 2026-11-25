import type { AnalysisJob, AnalyzeRequest, AnalyzeResponse, HistoryPage, HistoryQuery } from '../types/analysis';
import { ServiceError, type AnalysisService, type RequestOptions } from './types';

/** VITE_API_BASE_URL verilmezse yerel FastAPI adresi kullanılır. */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const REQUEST_TIMEOUT_MS = 15_000;

/** FastAPI hata gövdesi: { detail: { code, message } } ya da doğrulama hatalarında { detail: [...] } */
async function readErrorMessage(response: Response): Promise<string | null> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail) && typeof detail.message === 'string') {
      return detail.message;
    }
  } catch {
    // gövde JSON değil
  }
  return null;
}

async function request<T>(path: string, init: RequestInit, options?: RequestOptions): Promise<T> {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const signal = options?.signal ? AbortSignal.any([options.signal, timeout]) : timeout;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal,
      headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}) },
    });
  } catch (error) {
    // Çağıran isteği iptal ettiyse (sayfa değişti, yeni seçim yapıldı) hatayı olduğu gibi ilet.
    if (options?.signal?.aborted) throw error;
    if (timeout.aborted) {
      throw new ServiceError('request_timeout', 'Sunucu zamanında yanıt vermedi. Biraz sonra yeniden deneyin.');
    }
    throw new ServiceError(
      'service_unavailable',
      'Analiz servisine bağlanılamadı. Sunucu kapalı olabilir ya da bağlantınızda bir sorun olabilir.',
    );
  }

  if (!response.ok) {
    const message = await readErrorMessage(response);
    if (response.status === 404) {
      throw new ServiceError('not_found', message ?? 'Bu analiz sonucu bulunamadı. Silinmiş olabilir.');
    }
    if (response.status === 400 || response.status === 422) {
      throw new ServiceError('bad_request', message ?? 'Servis bu isteği kabul etmedi. Adresi kontrol edip yeniden deneyin.');
    }
    throw new ServiceError(
      'service_unavailable',
      message ?? 'Analiz servisi şu anda yanıt veremiyor. Birkaç dakika sonra yeniden deneyin.',
    );
  }

  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new ServiceError('invalid_response', 'Servisten beklenmeyen bir yanıt alındı.');
  }
}

/** Canlı mod: FastAPI arka ucu. */
export const apiAnalysisService: AnalysisService = {
  pollIntervalMs: 1500,

  analyze(body: AnalyzeRequest, options?: RequestOptions) {
    return request<AnalyzeResponse>('/api/analyze', { method: 'POST', body: JSON.stringify(body) }, options);
  },

  getResult(id: string, options?: RequestOptions) {
    return request<AnalysisJob>(`/api/result/${encodeURIComponent(id)}`, { method: 'GET' }, options);
  },

  listHistory(query: HistoryQuery, options?: RequestOptions) {
    const params = new URLSearchParams({ result: query.result, limit: String(query.limit ?? 100) });
    if (query.search.trim()) params.set('search', query.search.trim());
    return request<HistoryPage>(`/api/history?${params}`, { method: 'GET' }, options);
  },

  deleteAnalysis(id: string, options?: RequestOptions) {
    return request<void>(`/api/analyses/${encodeURIComponent(id)}`, { method: 'DELETE' }, options);
  },
};
