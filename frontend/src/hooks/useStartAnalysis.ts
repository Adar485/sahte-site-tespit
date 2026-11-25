import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { analysisService, toServiceError, type ServiceError } from '../services';

/** POST /api/analyze çağrısını yapar ve başarıda dönen kimliğin analiz sayfasına geçer. */
export function useStartAnalysis() {
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ServiceError | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  // Aynı anda yalnızca bir gönderim: çift tıklama ya da Enter tekrarı yeni kayıt oluşturmaz.
  const inFlightRef = useRef(false);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const start = useCallback(
    async (url: string) => {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      setPending(true);
      setError(null);
      try {
        const response = await analysisService.analyze({ url }, { signal: controller.signal });
        navigate(`/analiz/${encodeURIComponent(response.id)}`);
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(toServiceError(caught));
      } finally {
        inFlightRef.current = false;
        if (!controller.signal.aborted) setPending(false);
      }
    },
    [navigate],
  );

  const reset = useCallback(() => setError(null), []);

  return { start, pending, error, reset };
}
