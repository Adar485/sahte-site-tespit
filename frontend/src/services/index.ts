import { apiAnalysisService } from './apiService';
import { demoAnalysisService } from '../demo/demoService';
import type { AnalysisService } from './types';

/** "api" verilmedikçe örnek veri sağlayıcısı kullanılır. */
export const isDemoMode = import.meta.env.VITE_ANALYSIS_MODE !== 'api';

export const analysisService: AnalysisService = isDemoMode ? demoAnalysisService : apiAnalysisService;

export { ServiceError, toServiceError } from './types';
export type { AnalysisService } from './types';

/** Yalnızca demo modunda: boş geçmiş ekranından örnek kayıt yüklemek için. */
export { createSampleResults as loadDemoSamples } from '../demo/demoService';
