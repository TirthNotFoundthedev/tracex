import { Badge, Button, ListRow } from "@tracex/ui";
import { useState } from "react";

import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { useApp } from "../app-context";
import { FailureView } from "../components/FailureView";
import { Await, Screen, titleFor } from "../components/Screen";
import { entityIcon, type EntityType } from "../lib/entity";
import { useLoad } from "../lib/useLoad";
import type { MessageKey } from "../i18n";
import { paths, useNav } from "../router";

type EntitySummary = components["schemas"]["EntitySummary"];

const GROUPS: { id: string; types: EntityType[]; key: MessageKey }[] = [
  { id: "person", types: ["PERSON", "ORG"], key: "case.group.person" },
  { id: "phone", types: ["PHONE"], key: "case.group.phone" },
  { id: "account", types: ["ACCOUNT"], key: "case.group.account" },
  { id: "vehicle", types: ["VEHICLE"], key: "case.group.vehicle" },
];

/** O3: the four groups of items in one case. The rows are the actions, so there is no primary button. */
export function Case({ caseId }: { caseId: string }) {
  const { client, tt } = useApp();
  const nav = useNav();
  const [epoch, setEpoch] = useState(0);
  const key = `${caseId}|${epoch}`;
  const [loaded] = useLoad(() => client.listCaseEntities(caseId), key);
  const [tail, setTail] = useState<{
    key: string;
    items: EntitySummary[];
    cursor: string | null;
  }>();
  const [moreFailure, setMoreFailure] = useState<FailureResult>();

  /** Second line of a row. An organisation says so, so the row is not taken for a person. */
  function rowSecondary(item: EntitySummary): string {
    const note =
      item.link_count > 0
        ? tt(item.link_count === 1 ? "case.alsoIn.one" : "case.alsoIn.other", {
            n: item.link_count,
          })
        : item.has_hidden_connection
          ? tt("case.hiddenConnection")
          : tt("case.onlyHere");
    return item.type === "ORG" ? `${tt("case.org")}. ${note}` : note;
  }

  const title = titleFor(loaded, tt, (page) => tt("case.title", { number: page.case.case_number }));

  async function showMore(cursor: string, shown: EntitySummary[]) {
    const result = await client.listCaseEntities(caseId, { cursor });
    if (result.kind !== "ok") {
      setMoreFailure(result);
      return;
    }
    setMoreFailure(undefined);
    setTail({ key, items: [...shown, ...result.data.items], cursor: result.data.next_cursor });
  }

  return (
    <Screen title={title}>
      <Await loaded={loaded} onRetry={() => setEpoch((n) => n + 1)}>
        {(page) => {
          const useTail = tail?.key === key;
          const items = useTail ? tail.items : page.items;
          const cursor = useTail ? tail.cursor : page.next_cursor;
          return (
            <>
              <p className="tx-body">{tt("case.subtitle")}</p>
              {GROUPS.map((group) => {
                const rows = items.filter((item) => group.types.includes(item.type));
                const counted = group.types.reduce(
                  (sum, type) => sum + (page.counts_by_type?.[type] ?? 0),
                  0,
                );
                return (
                  <section key={group.id} className="tx-section">
                    <h2 className="tx-section__title">
                      {tt(group.key, { n: page.counts_by_type ? counted : rows.length })}
                    </h2>
                    {rows.length === 0 ? (
                      <p className="tx-body">{tt("case.groupEmpty")}</p>
                    ) : (
                      <ul className="officer-list">
                        {rows.map((item) => (
                          <li key={item.entity_id}>
                            <ListRow
                              icon={entityIcon[item.type]}
                              title={item.display_value}
                              secondary={rowSecondary(item)}
                              badge={
                                item.needs_review ? (
                                  <Badge icon="possible">{tt("case.pleaseCheck")}</Badge>
                                ) : undefined
                              }
                              onOpen={() => nav.go(paths.item(item.entity_id))}
                            />
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                );
              })}
              {moreFailure ? <FailureView result={moreFailure} /> : null}
              {cursor ? (
                <Button variant="secondary" onClick={() => void showMore(cursor, items)}>
                  {tt("cases.showMore")}
                </Button>
              ) : null}
            </>
          );
        }}
      </Await>
    </Screen>
  );
}
