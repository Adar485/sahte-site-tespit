/**
 * Yalnızca demo modunun yerel geçmişi. Canlı modda hiç okunmaz; gerçek geçmiş
 * arka uçtaki MySQL veritabanından gelir.
 */
import { readJson, writeJson } from '../lib/storage';
import type { AnalysisResult, HistoryEntry } from '../types/analysis';

const KEY = 'ssa.demo.history.v2';
const MAX_ENTRIES = 200;

function sorted(entries: HistoryEntry[]) {
  return [...entries].sort((a, b) => b.analyzedAt.localeCompare(a.analyzedAt));
}

export function toHistoryEntry(result: AnalysisResult): HistoryEntry {
  return {
    id: result.id,
    submittedUrl: result.submittedUrl,
    finalUrl: result.finalUrl,
    analyzedAt: result.completedAt ?? result.requestedAt,
    status: result.status,
    riskLevel: result.risk?.level ?? null,
  };
}

export const demoHistoryStore = {
  list(): HistoryEntry[] {
    return sorted(readJson<HistoryEntry[]>(KEY, []));
  },
  upsert(entries: HistoryEntry[]) {
    const ids = new Set(entries.map((entry) => entry.id));
    writeJson(KEY, sorted([...entries, ...this.list().filter((item) => !ids.has(item.id))]).slice(0, MAX_ENTRIES));
  },
  remove(id: string) {
    writeJson(KEY, this.list().filter((item) => item.id !== id));
  },
  clear() {
    writeJson(KEY, []);
  },
};
