/**
 * Arka uç yanıtlarının arayüzde güvenle gösterilebilmesi için yapılan
 * açık eşleme. Değer uydurulmaz: eksik bir modül "çalıştırılmadı" olarak,
 * bilinmeyen bir bulgu önemi "Bilgi" olarak gösterilir. Modüle özgü `data`
 * olduğu gibi bırakılır; beklenmeyen biçimler bölüm düzeyindeki hata
 * sınırında (ModuleTabs) ele alınır.
 */
import { MODULE_ORDER } from '../lib/labels';
import type { AnalysisJob, AnalysisResult, Finding, FindingSeverity, ModuleKey, ModuleResult } from '../types/analysis';

const SEVERITIES: FindingSeverity[] = ['info', 'low', 'medium', 'high'];

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function normalizeFindings(value: unknown, moduleKey: ModuleKey): Finding[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .filter((item) => text(item.title) || text(item.description))
    .map((item, index) => ({
      id: text(item.id) || `${moduleKey}-${index}`,
      severity: SEVERITIES.includes(item.severity as FindingSeverity) ? (item.severity as FindingSeverity) : 'info',
      title: text(item.title),
      description: text(item.description),
    }));
}

function normalizeModule(key: ModuleKey, raw: unknown): ModuleResult {
  if (typeof raw !== 'object' || raw === null) {
    return {
      key,
      status: 'skipped',
      summary: 'Sonuç yok.',
      unavailableReason: 'Bu bölüm için kayıtlı bir sonuç yok.',
      findings: [],
      data: null,
    } as ModuleResult;
  }
  const module = raw as Record<string, unknown>;
  return {
    ...(module as object),
    key,
    summary: text(module.summary),
    findings: normalizeFindings(module.findings, key),
    data: typeof module.data === 'object' && module.data !== null && !Array.isArray(module.data) ? module.data : null,
  } as ModuleResult;
}

export function normalizeResult(result: AnalysisResult): AnalysisResult {
  const rawModules = result.modules as unknown as Record<string, unknown> | undefined;
  const modules = Object.fromEntries(
    MODULE_ORDER.map((key) => [key, normalizeModule(key, rawModules?.[key])]),
  ) as unknown as AnalysisResult['modules'];
  return { ...result, modules };
}

export function normalizeJob(job: AnalysisJob): AnalysisJob {
  return job.state === 'done' ? { ...job, result: normalizeResult(job.result) } : job;
}
