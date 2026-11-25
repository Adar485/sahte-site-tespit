import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

interface StatePanelProps {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  tone?: 'neutral' | 'warning' | 'danger';
  /** Hata mesajları için role="alert" kullanılır. */
  alert?: boolean;
  headingLevel?: 'h1' | 'h2' | 'h3';
  className?: string;
}

const TONES = {
  neutral: 'bg-paper-deep text-ink-soft',
  warning: 'bg-amber-soft text-amber',
  danger: 'bg-coral-soft text-coral',
};

/** Boş durumlar, hata ve uyarı mesajları için ortak gövde. */
export function StatePanel({
  icon: Icon,
  title,
  children,
  actions,
  tone = 'neutral',
  alert,
  headingLevel: Heading = 'h2',
  className = '',
}: StatePanelProps) {
  return (
    <div role={alert ? 'alert' : undefined} className={`flex flex-col items-start gap-4 sm:flex-row sm:gap-5 ${className}`}>
      <span className={`inline-flex size-12 shrink-0 items-center justify-center rounded-xl ${TONES[tone]}`}>
        <Icon aria-hidden className="size-6" strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1">
        <Heading className="text-lg font-bold text-ink">{title}</Heading>
        {children && <div className="mt-1.5 max-w-prose text-[15px] leading-6 text-ink-soft">{children}</div>}
        {actions && <div className="mt-4 flex flex-wrap gap-2.5">{actions}</div>}
      </div>
    </div>
  );
}
