import { useRef, type KeyboardEvent, type ReactNode } from "react";

import { Button } from "./Button";
import { useUi } from "./context";
import { Icon, type IconName } from "./Icon";
import type { Language } from "../i18n";

export interface LanguageSwitchProps {
  onChange: (lang: Language) => void;
}

/**
 * Shows the OTHER language, written in that language, so someone who cannot read
 * the current one can still find it (DESIGN_RULES section 13).
 */
export function LanguageSwitch({ onChange }: LanguageSwitchProps) {
  const { lang, t } = useUi();
  const target: Language = lang === "en" ? "hi" : "en";
  return (
    <button
      type="button"
      className="tx-button tx-langswitch"
      data-variant="secondary"
      onClick={() => onChange(target)}
    >
      <Icon name="language" />
      <span lang={target}>{t(target === "hi" ? "language.hi" : "language.en")}</span>
    </button>
  );
}

export interface TopBarProps {
  /** One title per screen. */
  title: string;
  onBack?: () => void;
  onLanguageChange: (lang: Language) => void;
  /** Admin header: who is signed in and for which police area. */
  userName?: string;
  jurisdiction?: string;
  onSignOut?: () => void;
}

/** Fixed 64px header: Back, title, language (DESIGN_RULES section 4). Never hidden. */
export function TopBar({
  title,
  onBack,
  onLanguageChange,
  userName,
  jurisdiction,
  onSignOut,
}: TopBarProps) {
  const { app, t } = useUi();
  return (
    <header className="tx-topbar on-dark">
      {onBack ? (
        <Button variant="secondary" icon="back" onClick={onBack}>
          {t("nav.back")}
        </Button>
      ) : null}
      <h1 className="tx-topbar__title">{title}</h1>
      {app === "admin" && (userName || jurisdiction) ? (
        <p className="tx-topbar__who">
          {userName ? <span>{userName}</span> : null}
          {jurisdiction ? <span>{jurisdiction}</span> : null}
        </p>
      ) : null}
      <LanguageSwitch onChange={onLanguageChange} />
      {app === "admin" && onSignOut ? (
        <Button variant="secondary" icon="signOut" onClick={onSignOut}>
          {t("nav.signOut")}
        </Button>
      ) : null}
    </header>
  );
}

export interface SideNavItem {
  id: string;
  label: string;
  icon: IconName;
}

export interface SideNavProps {
  items: SideNavItem[];
  currentId: string;
  onSelect: (id: string) => void;
}

/** Admin only: 240px left navigation, icon + label for every section. */
export function SideNav({ items, currentId, onSelect }: SideNavProps) {
  const { app, t } = useUi();
  if (app !== "admin") return null;
  return (
    <nav className="tx-sidenav" aria-label={t("nav.mainLabel")}>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className="tx-sidenav__item"
              aria-current={item.id === currentId ? "page" : undefined}
              onClick={() => onSelect(item.id)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export interface BreadcrumbItem {
  label: string;
  onClick?: () => void;
}

/** Plain text trail "My cases > Case 24/118"; the last item is the current screen. */
export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  const { t } = useUi();
  return (
    <nav className="tx-breadcrumb" aria-label={t("nav.breadcrumbLabel")}>
      <ol>
        {items.map((item, index) => {
          const last = index === items.length - 1;
          return (
            <li key={`${index}-${item.label}`}>
              {item.onClick && !last ? (
                <button type="button" className="tx-breadcrumb__link" onClick={item.onClick}>
                  {item.label}
                </button>
              ) : (
                <span aria-current={last ? "page" : undefined}>{item.label}</span>
              )}
              {last ? null : <span aria-hidden="true"> &gt; </span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export interface TabItem {
  id: string;
  label: string;
  /** Count shown beside the label (status filters show every count). */
  count?: number;
  panel: ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  selectedId: string;
  onSelect: (id: string) => void;
  label: string;
}

/**
 * Admin only. The chosen tab is marked by border weight, bold text and a check
 * icon, never by colour alone (DESIGN_RULES section 11).
 */
export function Tabs({ items, selectedId, onSelect, label }: TabsProps) {
  const { app } = useUi();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  if (app !== "admin") return null;

  const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = items.length - 1;
    let next = index;
    if (event.key === "ArrowRight") next = index === last ? 0 : index + 1;
    else if (event.key === "ArrowLeft") next = index === 0 ? last : index - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else return;
    event.preventDefault();
    const target = items[next];
    if (target) {
      onSelect(target.id);
      refs.current[next]?.focus();
    }
  };

  const selected = items.find((item) => item.id === selectedId);
  return (
    <div className="tx-tabs">
      <div role="tablist" aria-label={label} className="tx-tabs__list">
        {items.map((item, index) => {
          const isSelected = item.id === selectedId;
          return (
            <button
              key={item.id}
              ref={(node) => {
                refs.current[index] = node;
              }}
              type="button"
              role="tab"
              id={`tab-${item.id}`}
              aria-selected={isSelected}
              aria-controls={`panel-${item.id}`}
              tabIndex={isSelected ? 0 : -1}
              className="tx-tab"
              onClick={() => onSelect(item.id)}
              onKeyDown={(event) => move(event, index)}
            >
              {isSelected ? <Icon name="confirm" /> : null}
              <span>
                {item.label}
                {item.count === undefined ? "" : ` (${item.count})`}
              </span>
            </button>
          );
        })}
      </div>
      {selected ? (
        <div
          role="tabpanel"
          id={`panel-${selected.id}`}
          aria-labelledby={`tab-${selected.id}`}
          className="tx-tabs__panel"
        >
          {selected.panel}
        </div>
      ) : null}
    </div>
  );
}
