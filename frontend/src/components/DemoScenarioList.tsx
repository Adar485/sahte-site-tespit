import { CircleDashed, CornerDownLeft, FileQuestion, Timer, Unplug, type LucideIcon } from 'lucide-react';
import { DEMO_SCENARIOS, type ScenarioKey } from '../demo/fixtures';
import { displayUrl } from '../lib/url';
import { TONE_STYLES, type Tone } from './risk';
import { Eyebrow } from './ui';

const SCENARIO_TONES: Record<ScenarioKey, { tone: Tone; icon?: LucideIcon }> = {
  low: { tone: 'low' },
  suspicious: { tone: 'suspicious' },
  high: { tone: 'high' },
  partial_url_only: { tone: 'suspicious', icon: CircleDashed },
  missing_content: { tone: 'low', icon: FileQuestion },
  unreachable: { tone: 'failed', icon: Unplug },
  timeout: { tone: 'failed', icon: Timer },
};

export function DemoScenarioList({ onPick }: { onPick(url: string): void }) {
  return (
    <section aria-labelledby="demo-adresleri" className="rounded-2xl border border-line bg-card p-5 sm:p-6">
      <Eyebrow>Demo</Eyebrow>
      <h2 id="demo-adresleri" className="mt-1 text-lg font-bold text-ink">
        Örnek adreslerle deneyin
      </h2>
      <p className="mt-1 text-[14px] leading-6 text-ink-muted">
        Seçtiğiniz adres kutuya yazılır; incelemeyi “Analiz et” ile başlatırsınız.
      </p>

      <ul className="mt-4 divide-y divide-line border-y border-line">
        {DEMO_SCENARIOS.map((scenario) => {
          const { tone, icon } = SCENARIO_TONES[scenario.key];
          const style = TONE_STYLES[tone];
          const Icon = icon ?? style.icon;
          return (
            <li key={scenario.key}>
              <button
                type="button"
                onClick={() => onPick(scenario.sampleUrl)}
                className="group flex min-h-14 w-full items-center gap-3 rounded-md py-2.5 text-left hover:bg-paper sm:px-2"
              >
                <span className={`inline-flex size-9 shrink-0 items-center justify-center rounded-lg ${style.soft} ${style.text}`}>
                  <Icon aria-hidden className="size-[18px]" strokeWidth={2.25} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[14px] font-bold text-ink">{scenario.label}</span>
                  <span className="block truncate font-mono text-[13px] text-ink-muted">{displayUrl(scenario.sampleUrl)}</span>
                  <span className="sr-only">. {scenario.description} Adresi kutuya yazar.</span>
                </span>
                <CornerDownLeft
                  aria-hidden
                  className="size-4 shrink-0 text-ink-muted opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                />
              </button>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 text-[13px] leading-5 text-ink-muted">
        Listede olmayan bir adres girerseniz, gerçek analiz servisi henüz bağlı olmadığı için servis hatası ekranını görürsünüz.
      </p>
    </section>
  );
}
