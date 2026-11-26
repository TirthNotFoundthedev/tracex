import type { ReactNode } from "react";

import { useUi } from "./context";
import { Icon, type IconName } from "./Icon";

/** Only two strengths exist. A weak pair is not a link and has no badge (DESIGN_RULES section 8). */
export type Strength = "strong" | "possible";

export interface StrengthBadgeProps {
  strength: Strength;
  /**
   * Admin review queue and graph only. The officer app ignores it:
   * no number appears on the first view there.
   */
  adminScore?: number;
}

/** Colour + icon + words + border style + 3-step bar, so one failing channel leaves four. */
export function StrengthBadge({ strength, adminScore }: StrengthBadgeProps) {
  const { app, t } = useUi();
  const filled = strength === "strong" ? 3 : 2;
  return (
    <span className="tx-strength" data-strength={strength}>
      <span className="tx-strength__head">
        <Icon name={strength} />
        <span className="tx-strength__words">
          {t(strength === "strong" ? "strength.strong" : "strength.possible")}
        </span>
        {app === "admin" && adminScore !== undefined ? (
          <span className="tx-strength__score">{t("strength.score", { score: adminScore })}</span>
        ) : null}
      </span>
      <span
        className="tx-strength__bar"
        role="img"
        aria-label={t(strength === "strong" ? "strength.bar3" : "strength.bar2")}
      >
        {[1, 2, 3].map((step) => (
          <span key={step} className="tx-strength__step" data-filled={step <= filled} />
        ))}
      </span>
    </span>
  );
}

export interface BadgeProps {
  icon: IconName;
  /** Words are required: a badge is never a coloured dot. */
  children: ReactNode;
  kind?: "neutral" | "danger";
}

/** Small tag with icon + words, for example "Sent for approval" (DESIGN_RULES section 11). */
export function Badge({ icon, children, kind = "neutral" }: BadgeProps) {
  return (
    <span className="tx-badge" data-kind={kind}>
      <Icon name={icon} />
      <span>{children}</span>
    </span>
  );
}
