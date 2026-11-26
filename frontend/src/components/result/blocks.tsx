import type { ReactNode } from 'react';

export function Block({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="border-t border-line pt-6 first:border-t-0 first:pt-0">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[16px] font-bold text-ink">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function Facts({ items }: { items: Array<{ label: string; value: ReactNode }> }) {
  return (
    <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="min-w-0">
          <dt className="text-[13px] font-bold text-ink-muted">{item.label}</dt>
          <dd className="mt-0.5 text-[15px] text-ink break-words">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
