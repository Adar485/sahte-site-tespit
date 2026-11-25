import { AlertCircle, ArrowRight, Globe, X } from 'lucide-react';
import { forwardRef, useId, useImperativeHandle, useRef, useState, type FormEvent } from 'react';
import { normalizeUrl, validationMessage } from '../lib/url';
import { Button } from './ui';

export interface UrlFormHandle {
  fill(value: string): void;
  focus(): void;
}

interface UrlFormProps {
  initialValue?: string;
  submitting: boolean;
  onSubmit(url: string): void;
  onChange?(): void;
}

export const UrlForm = forwardRef<UrlFormHandle, UrlFormProps>(function UrlForm(
  { initialValue = '', submitting, onSubmit, onChange },
  ref,
) {
  const [value, setValue] = useState(initialValue);
  const [touched, setTouched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const helpId = useId();
  const messageId = useId();

  useImperativeHandle(ref, () => ({
    fill(next) {
      setValue(next);
      setTouched(false);
      onChange?.();
      inputRef.current?.focus();
    },
    focus() {
      inputRef.current?.focus();
    },
  }));

  const result = normalizeUrl(value);
  const showError = touched && !result.ok;
  const showNormalized = result.ok && result.wasNormalized;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!result.ok) {
      inputRef.current?.focus();
      return;
    }
    onSubmit(result.url);
  }

  const frameState = submitting
    ? 'border-line-strong bg-paper-deep'
    : showError
      ? 'border-coral bg-white focus-within:shadow-[0_0_0_4px_rgb(191_55_42/0.15)]'
      : 'border-ink/80 bg-white focus-within:border-teal focus-within:shadow-[0_0_0_4px_rgb(11_125_114/0.16)]';

  return (
    <form onSubmit={handleSubmit} noValidate aria-busy={submitting}>
      <label htmlFor={inputId} className="mb-2.5 block text-[15px] font-bold text-ink">
        İncelenecek web adresi
      </label>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch">
        <div className={`group relative flex flex-1 items-center rounded-xl border-2 transition-[border-color,box-shadow] ${frameState}`}>
          <Globe
            aria-hidden
            className={`pointer-events-none absolute left-4 size-5 ${showError ? 'text-coral' : 'text-ink-muted group-focus-within:text-teal'}`}
          />
          <input
            ref={inputRef}
            id={inputId}
            type="url"
            inputMode="url"
            autoComplete="url"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="go"
            placeholder="ornek.com/giris"
            value={value}
            disabled={submitting}
            aria-invalid={showError || undefined}
            aria-describedby={`${helpId} ${messageId}`}
            onChange={(event) => {
              setValue(event.target.value);
              onChange?.();
            }}
            className="h-16 w-full min-w-0 rounded-xl bg-transparent pl-12 pr-12 font-mono text-[16px] text-ink outline-none placeholder:font-sans placeholder:text-ink-muted/80 focus-visible:outline-none disabled:cursor-not-allowed disabled:text-ink-muted sm:text-lg"
          />
          {value && !submitting && (
            <button
              type="button"
              onClick={() => {
                setValue('');
                setTouched(false);
                onChange?.();
                inputRef.current?.focus();
              }}
              className="absolute right-2 inline-flex size-11 items-center justify-center rounded-lg text-ink-muted hover:bg-paper-deep hover:text-ink"
            >
              <X aria-hidden className="size-5" />
              <span className="sr-only">Adresi temizle</span>
            </button>
          )}
        </div>

        <Button type="submit" size="lg" loading={submitting} className="h-16 text-[17px] sm:min-w-44">
          {submitting ? 'Başlatılıyor…' : 'Analiz et'}
          {!submitting && <ArrowRight aria-hidden className="size-5" strokeWidth={2.25} />}
        </Button>
      </div>

      <p id={helpId} className="mt-3 text-[14px] leading-6 text-ink-muted">
        E-postada, mesajda ya da reklamda gördüğünüz bağlantıyı yapıştırın. Başına <span className="font-mono">https://</span>{' '}
        yazmanız gerekmez.
      </p>

      <div id={messageId} aria-live="polite" className="min-h-8">
        {showError && !result.ok && (
          <p className="mt-2 flex items-start gap-2 text-[14px] font-semibold leading-6 text-coral">
            <AlertCircle aria-hidden className="mt-1 size-4 shrink-0" />
            {validationMessage(result)}
          </p>
        )}
        {showNormalized && result.ok && !submitting && (
          <p className="mt-2 text-[14px] leading-6 text-ink-soft">
            Adres <span className="font-mono font-semibold break-all text-teal-strong">{result.url}</span> olarak incelenecek.
          </p>
        )}
      </div>
    </form>
  );
});
