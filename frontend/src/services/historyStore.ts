import { readJson, writeJson } from '../lib/storage';
import type { AnalysisResult, HistoryEntry } from '../types/analysis';

const KEY = 'ssa.history.v1';
const MAX_ENTRIES = 200;

type Listener = () => void;
const listeners = new Set<Listener>();

let cache: HistoryEntry[] = sort(readJson<HistoryEntry[]>(KEY, []));

function sort(entries: HistoryEntry[]): HistoryEntry[] {
  return [...entries].sort((a, b) => b.analyzedAt.localeCompare(a.analyzedAt));
}

function commit(next: HistoryEntry[]) {
  cache = sort(next).slice(0, MAX_ENTRIES);
  writeJson(KEY, cache);
  listeners.forEach((listener) => listener());
}

export function toHistoryEntry(result: AnalysisResult): HistoryEntry {
  return {
    id: result.id,
    submittedUrl: result.submittedUrl,
    finalUrl: result.finalUrl,
    analyzedAt: result.completedAt,
    status: result.status,
    riskLevel: result.risk?.level ?? null,
  };
}

/** Analiz geçmişi. Bu sürümde yalnızca tarayıcının yerel deposunda tutulur. */
export const historyStore = {
  getSnapshot(): HistoryEntry[] {
    return cache;
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    const onStorage = (event: StorageEvent) => {
      if (event.key === KEY) {
        cache = sort(readJson<HistoryEntry[]>(KEY, []));
        listener();
      }
    };
    window.addEventListener('storage', onStorage);
    return () => {
      listeners.delete(listener);
      window.removeEventListener('storage', onStorage);
    };
  },

  upsert(entry: HistoryEntry) {
    commit([entry, ...cache.filter((item) => item.id !== entry.id)]);
  },

  addMany(entries: HistoryEntry[]) {
    const ids = new Set(entries.map((entry) => entry.id));
    commit([...entries, ...cache.filter((item) => !ids.has(item.id))]);
  },

  remove(id: string) {
    commit(cache.filter((item) => item.id !== id));
  },

  clear() {
    commit([]);
  },
};
