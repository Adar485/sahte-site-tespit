/**
 * Örnek veri sağlayıcısı.
 *
 * Gerçek API ile aynı sözleşmeyi (AnalysisService) uygular; analiz sürecini
 * zamanlayıcılarla taklit eder ve sonuçları tarayıcının yerel deposunda tutar.
 * Hiçbir web sitesine istek göndermez.
 */
import { readJson, writeJson } from '../lib/storage';
import { STAGE_ORDER } from '../lib/labels';
import { ServiceError, type AnalysisService, type RequestOptions } from '../services/types';
import type { AnalysisJob, AnalysisResult, AnalyzeRequest, AnalyzeResponse } from '../types/analysis';
import { findScenario, scenarioByKey, type ScenarioKey } from './fixtures';

const JOBS_KEY = 'ssa.demo.jobs.v1';
const RESULTS_KEY = 'ssa.demo.results.v1';

interface DemoJob {
  id: string;
  url: string;
  scenario: ScenarioKey;
  startedAt: number;
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const timer = window.setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer);
        reject(signal.reason);
      },
      { once: true },
    );
  });
}

function createId(): string {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}${Math.random()}`;
  return `demo-${random.replace(/[^a-z0-9]/gi, '').slice(0, 12).toLowerCase()}`;
}

const jobs = () => readJson<Record<string, DemoJob>>(JOBS_KEY, {});
const results = () => readJson<Record<string, AnalysisResult>>(RESULTS_KEY, {});

function saveResult(result: AnalysisResult) {
  writeJson(RESULTS_KEY, { ...results(), [result.id]: result });
}

function buildResult(scenarioKey: ScenarioKey, id: string, url: string, startedAt: number, finishedAt: number) {
  return scenarioByKey(scenarioKey).build({
    id,
    submittedUrl: url,
    requestedAt: new Date(startedAt).toISOString(),
    completedAt: new Date(finishedAt).toISOString(),
    durationMs: finishedAt - startedAt,
  });
}

export const demoAnalysisService: AnalysisService = {
  pollIntervalMs: 400,

  async analyze(request: AnalyzeRequest, options?: RequestOptions): Promise<AnalyzeResponse> {
    await wait(500, options?.signal);

    const scenario = findScenario(request.url);
    if (!scenario) {
      throw new ServiceError(
        'service_unavailable',
        'Analiz servisi henüz bağlı değil. Bu demo sürümünde yalnızca örnek adresler incelenebilir.',
      );
    }

    const job: DemoJob = { id: createId(), url: request.url, scenario: scenario.key, startedAt: Date.now() };
    writeJson(JOBS_KEY, { ...jobs(), [job.id]: job });
    return { id: job.id, state: 'queued' };
  },

  async getResult(id: string, options?: RequestOptions): Promise<AnalysisJob> {
    await wait(120, options?.signal);

    const stored = results()[id];
    if (stored) return { id, state: 'done', result: stored };

    const allJobs = jobs();
    const job = allJobs[id];
    if (!job) {
      throw new ServiceError('not_found', 'Bu analiz sonucu bulunamadı. Silinmiş ya da başka bir tarayıcıda yapılmış olabilir.');
    }

    const scenario = scenarioByKey(job.scenario);
    const elapsed = Date.now() - job.startedAt;
    let cumulative = 0;
    for (let index = 0; index < scenario.timeline.length; index += 1) {
      cumulative += scenario.timeline[index];
      if (elapsed < cumulative) {
        return { id, state: 'running', stage: STAGE_ORDER[index], submittedUrl: job.url };
      }
    }

    const result = buildResult(job.scenario, id, job.url, job.startedAt, job.startedAt + cumulative);
    saveResult(result);
    delete allJobs[id];
    writeJson(JOBS_KEY, allJobs);
    return { id, state: 'done', result };
  },
};

/** Boş geçmiş ekranından yüklenebilen örnek geçmiş kayıtları. */
export function createSampleResults(): AnalysisResult[] {
  const now = Date.now();
  const hour = 60 * 60 * 1000;
  const samples: Array<{ scenario: ScenarioKey; url: string; ago: number }> = [
    { scenario: 'high', url: 'http://examp1e.test/giris', ago: 2 * hour },
    { scenario: 'low', url: 'https://www.example.com/', ago: 5 * hour },
    { scenario: 'suspicious', url: 'https://example-destek.test/hesap/guncelle', ago: 26 * hour },
    { scenario: 'partial_url_only', url: 'https://kampanya.example.net/odul-kazandiniz', ago: 50 * hour },
    { scenario: 'unreachable', url: 'https://ulasilamayan.invalid/', ago: 75 * hour },
    { scenario: 'missing_content', url: 'https://bos-sayfa.example.org/', ago: 8 * 24 * hour },
    { scenario: 'timeout', url: 'https://yavas.example.net/', ago: 12 * 24 * hour },
  ];

  const created = samples.map((sample) => {
    const finishedAt = now - sample.ago;
    const startedAt = finishedAt - 4200 - Math.round(Math.random() * 2400);
    return buildResult(sample.scenario, createId(), sample.url, startedAt, finishedAt);
  });
  writeJson(RESULTS_KEY, { ...results(), ...Object.fromEntries(created.map((result) => [result.id, result])) });
  return created;
}
