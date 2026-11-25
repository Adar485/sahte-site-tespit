import { useCallback, useEffect, useState } from 'react';
import { analysisService, isAbortError, toServiceError, type ServiceError } from '../services';
import type { HistoryPage, ResultFilter } from '../types/analysis';

const SEARCH_DEBOUNCE_MS = 250;

export type HistoryView =
  | { phase: 'loading'; previous: HistoryPage | null }
  | { phase: 'ready'; page: HistoryPage }
  | { phase: 'error'; error: ServiceError };

/**
 * GET /api/history. Each new search/filter cancels the previous request, so a
 * slower, older response can never replace the results of a newer selection.
 */
export function useHistoryQuery(search: string, result: ResultFilter) {
  const [view, setView] = useState<HistoryView>({ phase: 'loading', previous: null });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setView((current) => ({ phase: 'loading', previous: current.phase === 'ready' ? current.page : current.phase === 'loading' ? current.previous : null }));

    const timer = window.setTimeout(
      async () => {
        try {
          const page = await analysisService.listHistory({ search, result }, { signal: controller.signal });
          if (!controller.signal.aborted) setView({ phase: 'ready', page });
        } catch (error) {
          if (controller.signal.aborted || isAbortError(error)) return;
          setView({ phase: 'error', error: toServiceError(error) });
        }
      },
      search ? SEARCH_DEBOUNCE_MS : 0,
    );

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [search, result, version]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  return { view, reload };
}
