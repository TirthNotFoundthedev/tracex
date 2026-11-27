import { Button, Message } from "@tracex/ui";
import { useState } from "react";

import { useApp } from "../app-context";
import { Await, Screen, titleFor } from "../components/Screen";
import { typeInCaseKey } from "../lib/entity";
import { useLoad } from "../lib/useLoad";
import { isMessageKey } from "../i18n";
import { paths, useNav } from "../router";

/** O4: one item with its plain facts. The one button leads to the cases it also appears in. */
export function Item({ entityId }: { entityId: string }) {
  const { client, tt } = useApp();
  const nav = useNav();
  const [epoch, setEpoch] = useState(0);
  const [loaded] = useLoad(() => client.getEntity(entityId), `${entityId}|${epoch}`);
  const detail = loaded.status === "ok" ? loaded.data : undefined;

  return (
    <Screen
      title={titleFor(loaded, tt, (entity) => entity.display_value)}
      trail={
        detail
          ? [
              {
                label: tt("case.title", { number: detail.case.case_number }),
                onClick: () => nav.go(paths.case(detail.case.case_id)),
              },
            ]
          : []
      }
    >
      <Await loaded={loaded} onRetry={() => setEpoch((n) => n + 1)}>
        {(entity) => (
          <>
            <p className="tx-body">
              {tt(typeInCaseKey[entity.type], { number: entity.case.case_number })}
            </p>
            {entity.facts.length > 0 ? (
              <dl className="officer-facts">
                {entity.facts.map((fact, index) => {
                  const labelKey = `item.fact.${fact.key}`;
                  return (
                    <div key={`${index}-${fact.key}`} className="officer-fact">
                      {isMessageKey(labelKey) ? <dt>{tt(labelKey)}</dt> : null}
                      <dd>{fact.value}</dd>
                    </div>
                  );
                })}
              </dl>
            ) : null}
            {entity.links.length > 0 || entity.stubs.length > 0 ? (
              <Button
                variant="primary"
                icon="alsoAppearsIn"
                onClick={() => nav.go(paths.also(entity.entity_id))}
              >
                {tt("item.showOther")}
              </Button>
            ) : (
              <Message kind="info">{tt("item.onlyHere")}</Message>
            )}
          </>
        )}
      </Await>
    </Screen>
  );
}
