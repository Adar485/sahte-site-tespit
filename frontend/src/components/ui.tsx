import { Loader2, type LucideIcon } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link, type LinkProps } from 'react-router-dom';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'md' | 'lg';

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-teal text-white hover:bg-teal-strong active:bg-teal-strong disabled:bg-ink-muted/40 disabled:text-white/90 shadow-[0_1px_0_rgb(15_30_61/0.12)]',
  secondary: 'bg-card text-ink border border-line-strong hover:border-ink/50 hover:bg-white disabled:text-ink-muted',
  ghost: 'text-ink-soft hover:bg-paper-deep hover:text-ink disabled:text-ink-muted',
  danger: 'bg-coral text-white hover:bg-[#a22d22] disabled:opacity-60',
};

const SIZES: Record<Size, string> = {
  md: 'min-h-11 px-4 text-[15px] gap-2 rounded-lg',
  lg: 'min-h-14 px-6 text-base gap-2.5 rounded-xl',
};

export function buttonClasses(variant: Variant = 'primary', size: Size = 'md', extra = '') {
  return [
    'inline-flex items-center justify-center font-semibold transition-colors duration-150 select-none',
    'disabled:cursor-not-allowed',
    VARIANTS[variant],
    SIZES[size],
    extra,
  ].join(' ');
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: LucideIcon;
  loading?: boolean;
}

export function Button({ variant, size, icon: Icon, loading, children, className = '', disabled, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClasses(variant, size, className)}
    >
      {loading ? (
        <Loader2 aria-hidden className="size-[1.1em] motion-safe:animate-spin" />
      ) : (
        Icon && <Icon aria-hidden className="size-[1.1em]" strokeWidth={2.25} />
      )}
      {children}
    </button>
  );
}

interface ButtonLinkProps extends LinkProps {
  variant?: Variant;
  size?: Size;
  icon?: LucideIcon;
}

export function ButtonLink({ variant, size, icon: Icon, children, className = '', ...rest }: ButtonLinkProps) {
  return (
    <Link {...rest} className={buttonClasses(variant, size, className)}>
      {Icon && <Icon aria-hidden className="size-[1.1em]" strokeWidth={2.25} />}
      {children}
    </Link>
  );
}

/** Bölüm başlıklarının üstündeki küçük etiket. */
export function Eyebrow({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <p className={`text-[12px] font-bold uppercase tracking-[0.14em] ${/\btext-(?!\[)/.test(className) ? '' : 'text-ink-muted'} ${className}`}>
      {children}
    </p>
  );
}

export function Panel({ children, className = '', as: Tag = 'section' }: { children: ReactNode; className?: string; as?: 'section' | 'div' | 'article' }) {
  return <Tag className={`rounded-2xl border border-line bg-card ${className}`}>{children}</Tag>;
}

/** Adresleri tek satırda, eşit aralıklı yazı tipiyle gösterir; uzun adresler kırılır. */
export function UrlText({ url, className = '' }: { url: string; className?: string }) {
  return <span className={`font-mono text-[0.92em] break-all ${className}`}>{url}</span>;
}
