import { Button } from "./Button";
import { useUi } from "./context";
import { Icon, type IconName } from "./Icon";

export type RestrictedItemType = "person" | "phone" | "bank" | "vehicle";

const ITEM_ICON: Record<RestrictedItemType, IconName> = {
  person: "person",
  phone: "phone",
  bank: "bank",
  vehicle: "vehicle",
};

/**
 * The props are the whole contract: the officer's OWN item (type and value) and the
 * request state. There is deliberately no children, no case number, name, place, date,
 * count or strength prop, so no caller can put another area's data into the card
 * (DESIGN_RULES section 10). Access is enforced by the API; the UI holds nothing to hide.
 */
export interface RestrictedCardProps {
  itemType: RestrictedItemType;
  /** The officer's own item, for example the phone number, as stored. */
  itemValue: string;
  /** Set after the request: the date as the app formats it, for example "12 Mar 2026". */
  requestedOn?: string;
  /** Opens the access request form. Not shown once a request was sent. */
  onAskForAccess?: () => void;
}

export function RestrictedCard({
  itemType,
  itemValue,
  requestedOn,
  onAskForAccess,
}: RestrictedCardProps) {
  const { t } = useUi();
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
      <p className="tx-body">{t("restricted.body")}</p>
      {requestedOn ? (
        <p className="tx-body">{t("restricted.sent", { date: requestedOn })}</p>
      ) : onAskForAccess ? (
        <Button variant="secondary" onClick={onAskForAccess}>
          {t("restricted.ask")}
        </Button>
      ) : null}
    </section>
  );
}
