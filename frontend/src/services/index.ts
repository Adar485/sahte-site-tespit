import { apiAnalysisService } from './apiService';
import { demoAnalysisService } from '../demo/demoService';
import type { AnalysisService } from './types';

/**
 * Veri kaynağı seçimi. Varsayılan canlı moddur (FastAPI arka ucu).
 * Örnek veriyle çalışmak için açıkça VITE_ANALYSIS_MODE=demo verilmelidir.
 */
export const isDemoMode = import.meta.env.VITE_ANALYSIS_MODE === 'demo';

export const analysisService: AnalysisService = isDemoMode ? demoAnalysisService : apiAnalysisService;

export { ServiceError, isAbortError, toServiceError } from './types';
export type { AnalysisService } from './types';
