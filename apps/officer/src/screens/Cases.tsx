import { Badge, Button, EmptyState, ListRow, Message, Pager, SearchField } from "@tracex/ui";
import { useEffect, useState } from "react";

import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { useApp } from "../app-context";
import { Await, Screen } from "../components/Screen";
import { FailureView } from "../components/FailureView";
import { formatDate } from "../lib/format";
import { useLoad } from "../lib/useLoad";
import { paths, useNav } from "../router";

type CaseSummary = components["schemas"]["CaseSummary"];
type AccessRequestMine = components["schemas"]["AccessRequestMine"];

const PAGE = 50;

/** O2: the officer's cases, a search by case number, and a note when an access request was approved. */
export function Cases() {
  const { client, tt, lang, signOut } = useApp();
  const nav = useNav();
  const [query, setQuery] = useState("");
  const [epoch, setEpoch] = useState(0);
  const key = `${query}|${epoch}`;
  const [loaded] = useLoad(
    () => client.listCases({ limit: PAGE, ...(query ? { case_number: query } : {}) }),
    key,
  );
  const [tail, setTail] = useState<{ key: string; items: CaseSummary[]; cursor: string | null }>();
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreFailure, setMoreFailure] = useState<FailureResult>();
  const [approved, setApproved] = useState<AccessRequestMine[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    let current = true;
    void client.listAccessRequests({ scope: "mine", status: "APPROVED" }).then((result) => {
      if (!current || result.kind !== "ok") return;
      setApproved(
        result.data.items.filter(
          (item): item is AccessRequestMine =>
            item.view === "MINE" && item.grant?.status === "ACTIVE",
        ),
      );
    });
    return () => {
      current = false;
    };
  }, [client]);

  const retry = () => setEpoch((n) => n + 1);

  async function showMore(cursor: string, shownItems: CaseSummary[]) {
    setLoadingMore(true);
    setMoreFailure(undefined);
    const result = await client.listCases({
      limit: PAGE,
      cursor,
      ...(query ? { case_number: query } : {}),
    });
    setLoadingMore(false);
    if (result.kind !== "ok") {
      setMoreFailure(result);
      return;
    }
    setTail({
      key,
      items: [...shownItems, ...result.data.items],
      cursor: result.data.next_cursor,
    });
  }

  return (
    <Screen title={tt("cases.title")} showTrail={false}>
      {approved
        .filter((request) => !dismissed.has(request.request_id) && request.grant)
        .map((request) => (
          <Message
            key={request.request_id}
            kind="success"
            onDismiss={() => setDismissed(new Set(dismissed).add(request.request_id))}
            action={
              <Button
                variant="secondary"
                onClick={() => nav.go(paths.item(request.grant?.far_entity_id ?? ""))}
              >
                {tt("cases.seeCase")}
              </Button>
            }
          >
            {tt("cases.accessApproved")}
          </Message>
        ))}
      <p className="tx-body">{tt("cases.intro")}</p>
      <SearchField
        label={tt("cases.searchLabel")}
        defaultValue={query}
        onSearch={(value) => {
          setQuery(value.trim());
          setTail(undefined);
        }}
      />
      <Await loaded={loaded} label={tt("cases.loading")} onRetry={retry}>
        {(page) => {
          const useTail = tail?.key === key;
          const items = useTail ? tail.items : page.items;
          const cursor = useTail ? tail.cursor : page.next_cursor;
          if (items.length === 0) {
            return (
              <EmptyState
                title={tt(query ? "cases.noResults" : "cases.empty")}
                hint={tt(query ? "cases.noResultsHint" : "cases.emptyHint")}
              />
            );
          }
          return (
            <>
              <ul className="officer-list">
                {items.map((item) => (
                  <li key={item.case_id}>
                    <ListRow
                      icon="case"
                      title={tt("case.title", { number: item.case_number })}
                      secondary={[
                        item.title,
                        tt("cases.opened", { date: formatDate(item.opened_on, lang) }),
                      ]
                        .filter(Boolean)
                        .join(". ")}
                      badge={
                        item.linked_item_count > 0 ? (
                          <Badge icon="alsoAppearsIn">
                            {tt(
                              item.linked_item_count === 1
                                ? "cases.otherCases.one"
                                : "cases.otherCases.other",
                              { n: item.linked_item_count },
                            )}
                          </Badge>
                        ) : undefined
                      }
                      onOpen={() => nav.go(paths.case(item.case_id))}
                    />
                  </li>
                ))}
              </ul>
              {moreFailure ? <FailureView result={moreFailure} /> : null}
              {cursor ? (
                page.total !== undefined ? (
                  <Pager
                    shown={items.length}
                    total={page.total}
                    onMore={() => void showMore(cursor, items)}
                  />
                ) : (
                  <Button
                    variant="secondary"
                    disabled={loadingMore}
                    onClick={() => void showMore(cursor, items)}
                  >
                    {tt("cases.showMore")}
                  </Button>
                )
              ) : null}
            </>
          );
        }}
      </Await>
      <div className="tx-actions">
        <Button variant="secondary" icon="signOut" onClick={signOut}>
          {tt("nav.signOut")}
        </Button>
      </div>
    </Screen>
  );
}
