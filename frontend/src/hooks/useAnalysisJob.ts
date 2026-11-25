import { useCallback, useEffect, useState } from 'react';
import { analysisService, ServiceError, toServiceError } from '../services';
import { historyStore, toHistoryEntry } from '../services/historyStore';
import type { AnalysisResult, AnalysisStage } from '../types/analysis';

/** Sonuç bu süre içinde hazır olmazsa istemci beklemeyi bırakır. */
const CLIENT_TIMEOUT_MS = 3 * 60 * 1000;
/** Tüm aşamalar bittiğinde ilerleme listesinin tamamlanmış hâliyle görünme süresi. */
const COMPLETION_HOLD_MS = 900;

export type JobView =
  | { phase: 'loading' }
  | { phase: 'running'; stage: AnalysisStage; submittedUrl: string }
  | { phase: 'finishing'; result: AnalysisResult }
  | { phase: 'done'; result: AnalysisResult }
  | { phase: 'error'; error: ServiceError };

/**
 * Bir analizi kimliğine göre izler: sonuç hazır değilse düzenli aralıklarla
 * GET /api/result/{id} sorgular, hazır olduğunda geçmişe kaydeder.
 */
export function useAnalysisJob(id: string) {
  const [view, setView] = useState<JobView>({ phase: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    const startedAt = Date.now();
    let sawRunning = false;
    let timer: number | undefined;

    setView({ phase: 'loading' });

    const poll = async () => {
      try {
        const job = await analysisService.getResult(id, { signal });
        if (signal.aborted) return;

        if (job.state === 'done') {
          historyStore.upsert(toHistoryEntry(job.result));
          if (sawRunning && job.result.status !== 'failed') {
            setView({ phase: 'finishing', result: job.result });
            timer = window.setTimeout(() => setView({ phase: 'done', result: job.result }), COMPLETION_HOLD_MS);
          } else {
            setView({ phase: 'done', result: job.result });
          }
          return;
        }

        sawRunning = true;
        setView({ phase: 'running', stage: job.stage, submittedUrl: job.submittedUrl });

        if (Date.now() - startedAt > CLIENT_TIMEOUT_MS) {
          setView({
            phase: 'error',
            error: new ServiceError('service_unavailable', 'Analiz beklenenden uzun sürdü. Biraz sonra sonucu yeniden açmayı deneyin.'),
          });
          return;
        }
        timer = window.setTimeout(poll, analysisService.pollIntervalMs);
      } catch (error) {
        if (signal.aborted) return;
        setView({ phase: 'error', error: toServiceError(error) });
      }
    };

    poll();

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [id, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  return { view, retry };
}
