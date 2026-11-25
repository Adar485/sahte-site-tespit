import { AlertTriangle } from 'lucide-react';
import { useEffect, useId, useRef } from 'react';
import { Button } from './ui';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm(): void;
  onCancel(): void;
}

/** Yerel <dialog> öğesiyle onay penceresi: odak hapsi ve Esc ile kapanma tarayıcıdan gelir. */
export function ConfirmDialog({ open, title, description, confirmLabel, onConfirm, onCancel }: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      onClick={(event) => {
        if (event.target === ref.current) onCancel();
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl border border-line bg-card p-0 text-ink shadow-[0_24px_64px_-24px_rgb(15_30_61/0.45)]"
    >
      <div className="p-6">
        <div className="flex items-start gap-4">
          <span className="inline-flex size-11 shrink-0 items-center justify-center rounded-xl bg-coral-soft text-coral">
            <AlertTriangle aria-hidden className="size-5" />
          </span>
          <div>
            <h2 id={titleId} className="text-lg font-bold text-ink">
              {title}
            </h2>
            <p id={descriptionId} className="mt-1.5 text-[15px] leading-6 text-ink-soft">
              {description}
            </p>
          </div>
        </div>
        <div className="mt-6 flex flex-col-reverse gap-2.5 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onCancel} autoFocus>
            Vazgeç
          </Button>
          <Button variant="danger" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
