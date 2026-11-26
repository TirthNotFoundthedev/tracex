import type { ReactNode } from "react";

import { Button } from "./Button";
import { useUi } from "./context";
import { Icon, type IconName } from "./Icon";

export interface ListRowProps {
  icon?: IconName;
  title: string;
  /** Second line, 16px ink-2. */
  secondary?: string;
  /** Extra mark on the row, for example a StrengthBadge. */
  badge?: ReactNode;
  onOpen: () => void;
}

/** One full-width row, one target, ends in a chevron (DESIGN_RULES section 4). */
export function ListRow({ icon, title, secondary, badge, onOpen }: ListRowProps) {
  return (
    <button type="button" className="tx-listrow" onClick={onOpen}>
      {icon ? <Icon name={icon} /> : null}
      <span className="tx-listrow__text">
        <span className="tx-listrow__title">{title}</span>
        {secondary ? <span className="tx-listrow__secondary">{secondary}</span> : null}
        {badge ? <span className="tx-listrow__badge">{badge}</span> : null}
      </span>
      <Icon name="next" />
    </button>
  );
}

export interface PagerProps {
  shown: number;
  total: number;
  onMore: () => void;
}

/** "Show more" with a count. Renders nothing when everything is already shown. */
export function Pager({ shown, total, onMore }: PagerProps) {
  const { t } = useUi();
  if (shown >= total) return null;
  return (
    <div className="tx-pager">
      <p className="tx-pager__count">{t("pager.count", { shown, total })}</p>
      <Button variant="secondary" onClick={onMore}>
        {t("pager.more")}
      </Button>
    </div>
  );
}

export interface TableColumn<Row> {
  id: string;
  header: string;
  /** Numbers, IDs and dates: right aligned, mono. */
  numeric?: boolean;
  sortable?: boolean;
  cell: (row: Row) => ReactNode;
}

export type SortDirection = "up" | "down";

export interface TableProps<Row> {
  caption: string;
  columns: TableColumn<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  /** One "Open" button per row, never an icon cluster. */
  onOpenRow?: (row: Row) => void;
  sort?: { columnId: string; direction: SortDirection };
  onSort?: (columnId: string) => void;
}

/**
 * Admin only. Below 40rem each row becomes a stacked block of label and value
 * lines (DESIGN_RULES section 11), so no column is hidden and nothing scrolls sideways.
 */
export function Table<Row>({
  caption,
  columns,
  rows,
  rowKey,
  onOpenRow,
  sort,
  onSort,
}: TableProps<Row>) {
  const { app, t } = useUi();
  if (app !== "admin") return null;
  return (
    <table className="tx-table">
      <caption className="tx-table__caption">{caption}</caption>
      <thead>
        <tr>
          {columns.map((column) => {
            const active = sort?.columnId === column.id;
            const ariaSort = active ? (sort.direction === "up" ? "ascending" : "descending") : "none";
            return (
              <th
                key={column.id}
                scope="col"
                data-numeric={column.numeric ? "true" : undefined}
                aria-sort={column.sortable ? ariaSort : undefined}
              >
                {column.sortable && onSort ? (
                  <button
                    type="button"
                    className="tx-table__sort"
                    aria-label={t("table.sortBy", { column: column.header })}
                    onClick={() => onSort(column.id)}
                  >
                    <span>{column.header}</span>
                    <Icon name={active ? (sort.direction === "up" ? "sortUp" : "sortDown") : "sortNone"} />
                  </button>
                ) : (
                  column.header
                )}
              </th>
            );
          })}
          {onOpenRow ? (
            <th scope="col">
              <span className="tx-sr-only">{t("nav.openRow")}</span>
            </th>
          ) : null}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={rowKey(row)}>
            {columns.map((column) => (
              <td
                key={column.id}
                data-label={column.header}
                data-numeric={column.numeric ? "true" : undefined}
              >
                {column.cell(row)}
              </td>
            ))}
            {onOpenRow ? (
              <td>
                <Button variant="secondary" onClick={() => onOpenRow(row)}>
                  {t("nav.openRow")}
                </Button>
              </td>
            ) : null}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
