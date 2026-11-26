import { Button, EmptyState, RestrictedCard, StrengthBadge, useUi } from "@tracex/ui";
import { useEffect, useState } from "react";

import type { components } from "../api/schema";
import { useApp } from "../app-context";
import { Await, Screen } from "../components/Screen";
import { restrictedType } from "../lib/entity";
import { formatDate } from "../lib/format";
import { renderTemplate } from "../lib/explain";
import { useLoad } from "../lib/useLoad";
import { paths, useNav } from "../router";

type LinkSummary = components["schemas"]["LinkSummary"];
type Stub = components["schemas"]["Stub"];

/** Possible matches first, then strong ones. Rejected and undone links are not connections. */
function visibleLinks(links: LinkSummary[]): LinkSummary[] {
  const shown = links.filter(
    (link) => link.state === "SUGGESTED" || link.state === "AUTO" || link.state === "CONFIRMED",
  );
  return [
    ...shown.filter((link) => link.state === "SUGGESTED"),
    ...shown.filter((link) => link.state !== "SUGGESTED"),
  ];
}

function CaseCard({ link, entityId }: { link: LinkSummary; entityId: string }) {
  const { tt, lang } = useApp();
  const { t: shared } = useUi();
  const nav = useNav();
  const other = link.ends.find((end) => end.entity.entity_id !== entityId) ?? link.ends[0];
  const possible = link.state === "SUGGESTED";
  const reason = renderTemplate(link.main_reason.template_key, link.main_reason.params, lang);
  const caseNumber = other?.case.case_number ?? "";
  const line = other?.case.title
    ? tt("also.caseLine", { number: caseNumber, place: other.case.title })
    : shared("evidence.case", { case: caseNumber });
  return (
    <section className="officer-card" data-kind={possible ? "possible" : "strong"}>
      <StrengthBadge strength={possible ? "possible" : "strong"} />
      <p className="officer-card__title">{line}</p>
      {reason ? <p className="tx-body">{reason}</p> : null}
      <Button
        variant={possible ? "primary" : "secondary"}
        onClick={() => nav.go(paths.link(link.link_id, entityId))}
      >
        {tt(possible ? "also.checkThis" : "also.whyLinked")}
      </Button>
    </section>
  );
}

function StubCard({
  stub,
  entity,
  note,
}: {
  stub: Stub;
  entity: { type: components["schemas"]["EntityType"]; value: string; id: string };
  note: string | undefined;
}) {
  const { tt, lang } = useApp();
  const nav = useNav();
  const status = stub.access_request.status;
  const ask = () => nav.go(paths.ask(stub.stub_id, entity.id));
  return (
    <>
      <RestrictedCard
        itemType={restrictedType[entity.type]}
        itemValue={entity.value}
        {...(status === "PENDING" && stub.access_request.requested_at
          ? { requestedOn: formatDate(stub.access_request.requested_at, lang) }
          : {})}
        {...(status === "DENIED" ? { refused: note ? { note } : {}, onAskAgain: ask } : {})}
        {...(status === "NONE" || status === "EXPIRED" ? { onAskForAccess: ask } : {})}
      />
      {status === "DENIED" ? <p className="tx-body">{tt("restricted.cooldown")}</p> : null}
    </>
  );
}

/** O5, with the O9 card for every hidden connection (stubs come from the API; nothing else makes the card). */
export function AlsoAppears({ entityId }: { entityId: string }) {
  const { client, tt } = useApp();
  const nav = useNav();
  const [epoch, setEpoch] = useState(0);
  const [loaded] = useLoad(() => client.getEntity(entityId), `${entityId}|${epoch}`);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const detail = loaded.status === "ok" ? loaded.data : undefined;
  const hasDenied = detail?.stubs.some((stub) => stub.access_request.status === "DENIED") ?? false;

  useEffect(() => {
    if (!hasDenied) return;
    let current = true;
    void client.listAccessRequests({ scope: "mine", status: "DENIED" }).then((result) => {
      if (!current || result.kind !== "ok") return;
      const found: Record<string, string> = {};
      for (const item of result.data.items) {
        if (item.view === "MINE" && item.decision_note)
          found[item.stub.stub_id] = item.decision_note;
      }
      setNotes(found);
    });
    return () => {
      current = false;
    };
  }, [client, hasDenied]);

  return (
    <Screen
      title={tt("also.title")}
      trail={
        detail
          ? [
              {
                label: tt("case.title", { number: detail.case.case_number }),
                onClick: () => nav.go(paths.case(detail.case.case_id)),
              },
              { label: detail.display_value, onClick: () => nav.go(paths.item(detail.entity_id)) },
            ]
          : []
      }
    >
      <Await loaded={loaded} onRetry={() => setEpoch((n) => n + 1)}>
        {(entity) => {
          const links = visibleLinks(entity.links);
          return (
            <>
              <p className="tx-body">{tt("also.intro", { value: entity.display_value })}</p>
              {links.length === 0 && entity.stubs.length === 0 ? (
                <EmptyState title={tt("also.empty")} hint="" />
              ) : null}
              {links.map((link) => (
                <CaseCard key={link.link_id} link={link} entityId={entity.entity_id} />
              ))}
              {entity.stubs.map((stub) => (
                <StubCard
                  key={stub.stub_id}
                  stub={stub}
                  entity={{ type: entity.type, value: entity.display_value, id: entity.entity_id }}
                  note={notes[stub.stub_id]}
                />
              ))}
            </>
          );
        }}
      </Await>
    </Screen>
  );
}
