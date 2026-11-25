import { useSyncExternalStore } from 'react';
import { historyStore } from '../services/historyStore';

export function useHistory() {
  return useSyncExternalStore(historyStore.subscribe, historyStore.getSnapshot, historyStore.getSnapshot);
}
