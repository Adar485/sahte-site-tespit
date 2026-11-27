import { useCallback, useEffect, useState } from 'react';
import { analysisService, ServiceError, toServiceError } from '../services';
import type { AnalysisResult, AnalysisStage } from '../types/analysis';

/**
 * Sonuç bu süre içinde hazır olmazsa arayüz beklemeyi bırakır. Bu, analizin
 * başarısız olduğu anlamına gelmez; kullanıcı "Yeniden kontrol et" ile devam edebilir.
 */
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
 * Bir analizi kimliğine göre izler. Yalnızca analiz beklemede ya da sürerken
 * GET /api/result/{id} düzenli aralıklarla sorgulanır; tamamlanma ya da hata
 * durumunda, bileşen kaldırıldığında veya başka bir analiz seçildiğinde sorgu durur.
 * Eski bir analize ait geç gelen yanıtlar iptal edilen sinyal sayesinde yok sayılır.
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

        if (job.id !== id) {
          // Yanıt istenen kayda ait değil: başka bir sonucu göstermek yerine hata ver.
          setView({ phase: 'error', error: new ServiceError('invalid_response', 'Servisten beklenmeyen bir yanıt alındı.') });
          return;
        }
        if (job.state === 'done') {
          // Tüm aşamaların tamamlandığı yalnızca gerçekten bir değerlendirme varsa gösterilir.
          if (sawRunning && job.result.risk) {
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
            error: new ServiceError(
              'client_timeout',
              'Sonuç beklenen süre içinde hazır olmadı. Analiz arka planda sürüyor olabilir; durumu yeniden kontrol edebilirsiniz.',
            ),
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
