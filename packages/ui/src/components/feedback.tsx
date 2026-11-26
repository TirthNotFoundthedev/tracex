import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { Button } from "./Button";
import { useUi } from "./context";
import { TextField } from "./fields";
import { Icon, type IconName } from "./Icon";

export type MessageKind = "info" | "success" | "error";

const MESSAGE_ICON: Record<MessageKind, IconName> = {
  info: "info",
  success: "confirm",
  error: "problem",
};

export interface MessageProps {
  kind: MessageKind;
  /** What happened, what is safe, what to do. Never codes, never blame. */
  children: ReactNode;
  /** Present only when the message offers a way forward, for example "Try again". */
  action?: ReactNode;
  /** Messages stay until dismissed. Omit to keep the message until the next action. */
  onDismiss?: () => void;
}

/** In-page message. It never vanishes by itself and is never a toast (DESIGN_RULES section 11). */
export function Message({ kind, children, action, onDismiss }: MessageProps) {
  const { t } = useUi();
  return (
    <div className="tx-message" data-kind={kind} role={kind === "error" ? "alert" : "status"}>
      <Icon name={MESSAGE_ICON[kind]} />
      <div className="tx-message__body">
        <p>
          <span className="tx-sr-only">{t(`message.${kind}`)} </span>
          {children}
        </p>
        {action ? <div className="tx-actions">{action}</div> : null}
      </div>
      {onDismiss ? (
        <Button
          variant="secondary"
          icon="reject"
          onClick={onDismiss}
          aria-label={t("message.dismiss")}
        >
          {t("message.dismiss")}
        </Button>
      ) : null}
    </div>
  );
}

export interface ConfirmStepProps {
  /** For example "Reject this link?". */
  title: string;
  /** What will happen. */
  body?: string;
  /** For example "Yes, reject". */
  confirmLabel: string;
  confirmIcon?: IconName;
  /** "danger" only on the Reject step; otherwise primary. */
  confirmVariant?: "primary" | "danger";
  /** Admin steps that need a written reason (Reject, Undo, Reopen, Delete). */
  reason?: { label: string; min: number; max: number };
  onConfirm: (reason?: string) => void;
  onCancel: () => void;
}

/**
 * The only modal-like element (DESIGN_RULES section 14). It sits in the page, takes
 * focus when it appears, and Escape or "No, go back" leaves with nothing changed.
 */
export function ConfirmStep({
  title,
  body,
  confirmLabel,
  confirmIcon,
  confirmVariant = "primary",
  reason,
  onConfirm,
  onCancel,
}: ConfirmStepProps) {
  const { t } = useUi();
  const heading = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const bodyId = useId();
  const [text, setText] = useState("");
  const [error, setError] = useState<string>();

  useEffect(() => {
    heading.current?.focus();
  }, []);

  const submit = () => {
    if (!reason) {
      onConfirm();
      return;
    }
    const length = text.trim().length;
    if (length === 0) {
      setError(t("field.required", { field: reason.label }));
    } else if (length < reason.min) {
      setError(t("field.tooShort", { min: reason.min, field: reason.label }));
    } else {
      onConfirm(text.trim());
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") onCancel();
  };

  return (
    <section
      className="tx-confirm"
      role="alertdialog"
      aria-labelledby={titleId}
      aria-describedby={body ? bodyId : undefined}
      onKeyDown={onKeyDown}
    >
      <h2 className="tx-confirm__title" id={titleId} tabIndex={-1} ref={heading}>
        {title}
      </h2>
      {body ? (
        <p className="tx-body" id={bodyId}>
          {body}
        </p>
      ) : null}
      {reason ? (
        <TextField
          label={reason.label}
          hint={t("confirm.reasonHint", { min: reason.min, max: reason.max })}
          multiline
          required
          maxLength={reason.max}
          error={error}
          value={text}
          onChange={(value) => {
            setText(value);
            setError(undefined);
          }}
        />
      ) : null}
      <div className="tx-actions">
        <Button variant={confirmVariant} icon={confirmIcon} onClick={submit}>
          {confirmLabel}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {t("confirm.no")}
        </Button>
      </div>
    </section>
  );
}

export interface EmptyStateProps {
  /** Why it is empty: "No cases yet." */
  title: string;
  /** What next: "Ask your supervisor to add your cases." Defaults to a plain line. */
  hint?: string;
  action?: ReactNode;
}

export function EmptyState({ title, hint, action }: EmptyStateProps) {
  const { t } = useUi();
  return (
    <div className="tx-empty">
      <p className="tx-empty__title">
        <Icon name="info" />
        <span>{title}</span>
      </p>
      <p className="tx-body">{hint ?? t("empty.hint")}</p>
      {action ? <div className="tx-actions">{action}</div> : null}
    </div>
  );
}

export interface LoadingProps {
  /** For example "Loading your cases...". */
  label?: string;
  /** After this wait the slow line is added. DESIGN_RULES section 11 says 10 seconds. */
  slowAfterMs?: number;
}

/**
 * A text line with a still spinner icon: no skeleton and no spinning (section 0 bans
 * auto-playing motion). After 10 seconds it adds the slow line.
 */
export function Loading({ label, slowAfterMs = 10_000 }: LoadingProps) {
  const { t } = useUi();
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), slowAfterMs);
    return () => clearTimeout(timer);
  }, [slowAfterMs]);
  return (
    <div className="tx-loading" role="status">
      <p className="tx-loading__line">
        <Icon name="loading" />
        <span>{label ?? t("loading.default")}</span>
      </p>
      {slow ? <p className="tx-body">{t("loading.slow")}</p> : null}
    </div>
  );
}
