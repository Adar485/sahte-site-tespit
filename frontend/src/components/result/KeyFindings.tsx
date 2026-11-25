import { MODULE_LABELS, MODULE_ORDER } from '../../lib/labels';
import type { AnalysisResult, Finding, ModuleKey } from '../../types/analysis';
import { FindingItem, SEVERITY_RANK } from './FindingList';

const LIMIT = 4;

/** Tüm bölümlerdeki en önemli bulguları genel sonucun hemen altında özetler. */
export function KeyFindings({ result }: { result: AnalysisResult }) {
  const all: Array<{ finding: Finding; module: ModuleKey }> = MODULE_ORDER.flatMap((key) =>
    result.modules[key].findings.map((finding) => ({ finding, module: key })),
  );
  const notable = all.filter(({ finding }) => finding.severity !== 'info');
  const items = (notable.length ? notable : all)
    .sort((a, b) => SEVERITY_RANK[b.finding.severity] - SEVERITY_RANK[a.finding.severity])
    .slice(0, LIMIT);

  if (items.length === 0) return null;

  return (
    <section aria-labelledby="one-cikan-bulgular" className="rounded-2xl border border-line bg-card p-5 sm:p-7">
      <h2 id="one-cikan-bulgular" className="text-lg font-bold text-ink">
        {notable.length ? 'Öne çıkan bulgular' : 'İnceleme notları'}
      </h2>
      <ul className="mt-5 divide-y divide-line">
        {items.map(({ finding, module }) => (
          <FindingItem key={finding.id} finding={finding} context={MODULE_LABELS[module]} />
        ))}
      </ul>
    </section>
  );
}
