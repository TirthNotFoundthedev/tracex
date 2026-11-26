import type { ButtonHTMLAttributes, ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

export type ButtonVariant = "primary" | "secondary" | "danger";

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> {
  /** Exactly one primary per screen (DESIGN_RULES section 5). */
  variant?: ButtonVariant;
  /** Optional icon from the fixed vocabulary; it always sits beside the label. */
  icon?: IconName;
  /** Verb + object, from i18n. */
  children: ReactNode;
}

export function Button({ variant = "secondary", icon, children, type = "button", ...rest }: ButtonProps) {
  return (
    <button type={type} className="tx-button" data-variant={variant} {...rest}>
      {icon ? <Icon name={icon} /> : null}
      <span>{children}</span>
    </button>
  );
}
