import {
  useId,
  useState,
  type ChangeEvent,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

import { Button } from "./Button";
import { useUi } from "./context";
import { Icon } from "./Icon";

interface FieldShellProps {
  id: string;
  label: string;
  hint?: string | undefined;
  error?: string | undefined;
  required?: boolean | undefined;
  children: ReactNode;
}

/** Label above, hint under it, the control, then the error beside the field in words. */
function FieldShell({ id, label, hint, error, required, children }: FieldShellProps) {
  const { t } = useUi();
  return (
    <div className="tx-field" data-invalid={error ? "true" : undefined}>
      <label className="tx-field__label" htmlFor={id}>
        {label}
        {required ? <span className="tx-field__mark"> {t("field.requiredMark")}</span> : null}
      </label>
      {hint ? (
        <p className="tx-field__hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      {children}
      {error ? (
        <p className="tx-field__error" id={`${id}-error`}>
          <Icon name="problem" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}

function describedBy(id: string, hint?: string, error?: string) {
  const ids = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean);
  return ids.length > 0 ? ids.join(" ") : undefined;
}

export interface TextFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "id" | "size" | "onChange"> {
  label: string;
  hint?: string;
  /** Full sentence in words, e.g. "Please fill in: Reason." */
  error?: string;
  /** Use for the access reason field only (a single, longer text). */
  multiline?: boolean;
  onChange?: (value: string) => void;
}

export function TextField({
  label,
  hint,
  error,
  required,
  multiline = false,
  onChange,
  ...rest
}: TextFieldProps) {
  const id = useId();
  const common = {
    id,
    className: "tx-input",
    required,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": describedBy(id, hint, error),
  } as const;
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} required={required}>
      {multiline ? (
        <textarea
          {...common}
          rows={4}
          maxLength={rest.maxLength}
          minLength={rest.minLength}
          name={rest.name}
          value={rest.value as string | undefined}
          defaultValue={rest.defaultValue as string | undefined}
          onChange={(event) => onChange?.(event.target.value)}
        />
      ) : (
        <input
          {...rest}
          {...common}
          onChange={(event: ChangeEvent<HTMLInputElement>) => onChange?.(event.target.value)}
        />
      )}
    </FieldShell>
  );
}

export interface SearchFieldProps {
  label: string;
  onSearch: (query: string) => void;
  defaultValue?: string;
}

/** A labelled field with its own Search button, so the action is visible and not only Enter. */
export function SearchField({ label, onSearch, defaultValue = "" }: SearchFieldProps) {
  const { t } = useUi();
  const id = useId();
  const [query, setQuery] = useState(defaultValue);
  return (
    <form
      className="tx-search"
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        onSearch(query);
      }}
    >
      <div className="tx-field">
        <label className="tx-field__label" htmlFor={id}>
          {label}
        </label>
        <input
          id={id}
          className="tx-input"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <Button type="submit" variant="secondary" icon="search">
        {t("search.button")}
      </Button>
    </form>
  );
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  label: string;
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  error?: string;
}

/** Admin only: the officer app has no dropdowns (DESIGN_RULES section 4), so it renders nothing there. */
export function Select({ label, options, value, onChange, hint, error }: SelectProps) {
  const { app } = useUi();
  const id = useId();
  if (app !== "admin") return null;
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <select
        id={id}
        className="tx-input tx-select"
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

export interface CheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/** The whole row is the target, so the box is never the only thing to hit. */
export function Checkbox({ label, checked, onChange }: CheckboxProps) {
  const id = useId();
  return (
    <label className="tx-check" htmlFor={id}>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="tx-check__box" aria-hidden="true">
        {checked ? <Icon name="confirm" /> : null}
      </span>
      <span>{label}</span>
    </label>
  );
}

export interface FileDropProps {
  label: string;
  accept?: string;
  fileName?: string | undefined;
  onFile: (file: File) => void;
}

/**
 * Admin only. A real "Choose a file" button always works; dropping is an extra,
 * never the only way (DESIGN_RULES section 14).
 */
export function FileDrop({ label, accept, fileName, onFile }: FileDropProps) {
  const { app, t } = useUi();
  const id = useId();
  const [over, setOver] = useState(false);
  if (app !== "admin") return null;
  return (
    <div
      className="tx-filedrop"
      data-over={over ? "true" : undefined}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        const file = event.dataTransfer.files[0];
        if (file) onFile(file);
      }}
    >
      <p className="tx-field__label">{label}</p>
      <input
        id={id}
        className="tx-filedrop__input"
        type="file"
        accept={accept}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
        }}
      />
      <label className="tx-button" data-variant="secondary" htmlFor={id}>
        <Icon name="upload" />
        <span>{t("filedrop.choose")}</span>
      </label>
      <p className="tx-field__hint">{t("filedrop.drop")}</p>
      {fileName ? <p className="tx-filedrop__chosen">{t("filedrop.chosen", { name: fileName })}</p> : null}
    </div>
  );
}
