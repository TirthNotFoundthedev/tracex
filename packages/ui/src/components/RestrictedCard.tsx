import { Button } from "./Button";
import { useUi } from "./context";
import { Icon, type IconName } from "./Icon";

export type RestrictedItemType = "person" | "phone" | "bank" | "vehicle" | "org";

const ITEM_ICON: Record<RestrictedItemType, IconName> = {
  person: "person",
  phone: "phone",
  bank: "bank",
  vehicle: "vehicle",
  org: "org",
};

/**
 * The props are the whole contract: the officer's OWN item (type and value) and the
 * request state. There is deliberately no children, no case number, name, place, date,
 * count or strength prop, so no caller can put another area's data into the card
 * (DESIGN_RULES section 10). Access is enforced by the API; the UI holds nothing to hide.
 *
 * States, in this order: refused, request sent, no request yet.
 */
export interface RestrictedCardProps {
  itemType: RestrictedItemType;
  /** The officer's own item, for example the phone number, as stored. */
  itemValue: string;
  /** Set after the request: the date as the app formats it, for example "12 Mar 2026". */
  requestedOn?: string;
  /** The request was refused. `note` is the approver's words, shown only when given. */
  refused?: { note?: string };
  /** Opens the access request form. Shown only when no request is open. */
  onAskForAccess?: () => void;
  /** Opens the form again after a refusal. */
  onAskAgain?: () => void;
  /**
   * Weight of the button. Default "primary". A page that shows several cards, or other
   * primary buttons, gives "primary" to one and "secondary" to the rest (DESIGN_RULES section 5).
   */
  emphasis?: "primary" | "secondary";
}

export function RestrictedCard({
  itemType,
  itemValue,
  requestedOn,
  refused,
  onAskForAccess,
  onAskAgain,
  emphasis = "primary",
}: RestrictedCardProps) {
  const { t } = useUi();
  const note = refused?.note?.trim();
  return (
    <section className="tx-restricted" aria-label={t("restricted.title")}>
      <p className="tx-restricted__title">
        <Icon name="restricted" />
        <span>{t("restricted.title")}</span>
      </p>
      <p className="tx-restricted__item">
        <Icon name={ITEM_ICON[itemType]} />
        <span>
          {t(`item.${itemType}`)}: <span className="tx-mono">{itemValue}</span>
        </span>
      </p>
      <p className="tx-body">{t("access.stub.connection_exists")}</p>
      <p className="tx-body">{t("restricted.cannotSee")}</p>
      {refused ? (
        <>
          <p className="tx-body tx-restricted__state">{t("restricted.refused")}</p>
          {note ? (
            <p className="tx-body">
              {t("restricted.refusedNote")} {note}
            </p>
          ) : null}
          {onAskAgain ? (
            <Button variant={emphasis} onClick={onAskAgain}>
              {t("restricted.askAgain")}
            </Button>
          ) : null}
        </>
      ) : requestedOn ? (
        <p className="tx-body">{t("restricted.sent", { date: requestedOn })}</p>
      ) : onAskForAccess ? (
        <Button variant={emphasis} onClick={onAskForAccess}>
          {t("restricted.ask")}
        </Button>
      ) : null}
    </section>
  );
}
