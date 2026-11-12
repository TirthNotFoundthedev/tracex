# Engine spec: case graphs

Owner: Bose (Graph) · Task P2.3 · Reviewer: Iyer (Engine Lead) · Readers: Tier 1 matcher (task 2.4), Backend (entity mirror), QA.

**Purpose.** Turn the extractor's `CaseRecords` for one case into that case's graph (entity nodes, mentions, case-graph edges), dedupe the writings of the same entity inside the case, and store it in Neo4j so the matcher can read entities per case and later write SAME_AS edges between them. Every node, mention and edge traces to a source line. Nothing is merged across cases here and no entity is ever overwritten (CODEBASE_RULES, non-negotiable behaviours).

The code is `backend/tracex_engine/graph/`. The builder is pure (no database); the store sits behind a small interface with a Neo4j adapter and an in-memory adapter.

## 1. Model

**Entity** (one real thing inside one case). Neo4j labels `:Entity` plus one of `:Person :Org :Phone :Account :Vehicle`.

| Property | Meaning |
|---|---|
| `entity_id` | `<case_id>:<ordinal, 5 digits>`, see section 4 |
| `case_id`, `type` | `PERSON ORG PHONE ACCOUNT VEHICLE` |
| `normalized` | the extractor's normalized form of the first mention (person and org: the name; account: digits) |
| `display_value` | `raw_text` of the first mention, as written |
| `confidence` | highest mention confidence |
| `aliases` | PERSON: normalized aliases stated on any mention, first-seen order |
| `ifsc` | ACCOUNT: the IFSC of the first mention that has one |
| `shared_wording` | identifiers: true if any mention says shop, PCO, office, family or landline (feeds the SHARED flag later) |
| `ordinal`, `file`, `line` | first mention's position (provenance of the entity itself) |

**Mention** (one writing; `:Mention`, linked `(:Entity)-[:HAS_MENTION]->(:Mention)`). `mention_id` = `<case_id>:<file>:<line>:<n>` where `n` counts mentions on that physical line in build order; `entity_id`, `raw_text` (as written), `normalized`, `file`, `line`, `confidence`, and the attributes the extractor read for that writing (`role`, `age`, `dob`, `gender`, `locality`, `district`, `relative_relation`, `relative_name`, `aliases`, `ifsc`, `shared_wording`; each value also with its `_raw` text). One mention per extractor mention, none dropped.

**Place** (`:Place`, per case, not an `:Entity`, never linked): `place_id` = `<case_id>:place:<normalized>`, `normalized`, `display_value`. Dates are properties on edges, not nodes.

**Edges** (one relationship per source statement or row, so each keeps its own line). Common properties: `edge_id` (`<case_id>|<TYPE>|<file>|<line>|<n>`), `case_id`, `file`, `line`, `confidence`, `raw_text` (the statement or row as written).

| Type | From, to | From | Extra properties |
|---|---|---|---|
| `OWNS`, `REGISTERED_TO`, `MENTIONED_WITH` | person or org, identifier | each `Attribution` | `hedged` |
| `CALLED` | phone, phone | each CDR row (calling to called) | `call_id`, `start_time`, `duration_sec`, `call_type`, `cell_id` |
| `TRANSFERRED_TO` | account, phone or account | each bank row with a number as counterparty; DR: own account to counterparty, CR: counterparty to own account | `txn_id`, `txn_date`, `amount_inr` (string), `direction` |
| `SEEN_AT` | phone, place | each CDR row with a tower place: the calling number | `on` (call date), `at` (timestamp), `call_id`, `cell_id` |

Edge confidence: attributions carry the lower of the holder and identifier mention confidence; structured rows carry `CONFIDENCE_CLEAR`. SAME_AS edges (written later by the matcher) connect two `:Entity` nodes and are not part of a case graph: reading a case never returns them.

## 2. Within-case dedupe

Entities are built by walking all mentions in load order. A mention joins an existing entity only when a rule below holds, no veto applies against any mention already in that entity, and exactly one entity qualifies. If more than one qualifies, or none, the mention starts its own entity (no guessing). A mention equal in every field to one already placed goes to the same entity. Every merged writing stays its own `Mention`.

| Type | Joins when | Veto (stays separate) |
|---|---|---|
| PHONE, VEHICLE | equal normalized value | none |
| ACCOUNT | equal normalized digits | both IFSCs known and different (matching spec, `ACCT_BANK_CONFLICT`) |
| PERSON | equal normalized name with two or more tokens; or a single-token name only when the raw text is equal ignoring case and spacing; or the normalized name equals an alias stated on a mention already in the entity (`Kalu` and `Ramesh Kasana urf Kalu`), either direction | same relation and different relative names; different gender; different DOB; ages more than 2 apart; different locality or district (all compared as normalized text, only when both are stated) |
| ORG | equal normalized name and equal raw text ignoring case, spacing, punctuation and a leading `M/s` (so `Traders` and `Enterprises` writings never join) | different locality |

This matches the data-kit `within_case` groups (data-kit §8.1): the planted groups for `MOHD IRFAN`, `KAMLA DEVI`, the two Balaji organisations (not joined to each other: `shree` is not `shri`), the three phone writings and the two plate writings join; no entity spans two ground-truth entities outside one group.

## 3. Provenance

Every mention, edge and entity carries `file` and `line` (physical line, as `SourceRef`). An edge or mention never points outside its case. The graph holds only what the extractor emitted; unreadable rows stay in `CaseRecords.errors`, outside the graph. Bank rows whose counterparty is a name or empty, and CDR rows without a tower place, give no counterparty edge or no `SEEN_AT` edge; the row is still cited by the account and phone mentions it produced.

## 4. Entity ids, ordering and idempotency

`entity_id` = `<case_id>:<ordinal>` with `ordinal` a 5-digit count of entities in the case in order of first mention: load order of the file (`fir`, `notes`, `sdr`, `cdr`, `bank`; later batches after, by number), then line, then persons, orgs, identifiers, then extractor order. `entity_sort_key(id)` returns `(district digit, sequence, ordinal)` so ids compare in matching spec C5 order (case id numerically, then load order); plain string order is wrong across cases (`C-1100` < `C-150`). Same `CaseRecords` always gives the same ids, mention ids and edge ids. Adding a later batch file only appends: earlier ids do not move.

`write_case` is an upsert keyed by `entity_id`, `mention_id`, `place_id` and `edge_id`: nodes and edges are merged and properties set to the same values, so loading a case twice changes nothing and keeps any SAME_AS edge already on its entities. It never deletes. Constraints and indexes (`ensure_schema`, idempotent): unique `Entity.entity_id`, `Mention.mention_id`, `Place.place_id`; index on `Entity(type, normalized)` (the matcher's exact-value lookup, key B1) and `Entity.case_id`.

## 5. Interface the matcher imports

`build_case_graph(records) -> CaseGraph`; `CaseGraphStore` with `ensure_schema()`, `write_case(graph)`, `read_case(case_id) -> CaseGraph | None`, `case_ids()`, `find_entities(type, normalized) -> tuple[Entity, ...]` (all cases, sort-key order); `Neo4jCaseGraphStore.connect(uri, user, password)`, `InMemoryCaseGraphStore`; the model types; `entity_sort_key`.

## 6. Acceptance criteria

1. Same `CaseRecords` twice gives equal graphs (ids, mentions, edges); ordinals follow load order.
2. Section 2 table, one test per row and per veto; an ambiguous mention starts its own entity.
3. Every mention and edge carries its extractor source; mention counts equal extractor mention counts per type.
4. Edges per section 1 on hand-written cases, incl. hedged flag, SDR REGISTERED_TO, DR and CR direction, name counterparties giving no edge.
5. On kit data (small tier, all cases): every engine entity maps onto at most one ground-truth `within_case` group or ungrouped entity, and every planted within-case group maps onto exactly one engine entity. Noise groups do too, except where a Devanagari writing and its Roman writing transliterate differently (`shrivastav` / `srivastava`): joining those needs fuzzy matching, so at most 5% may stay split, each containing a non-ASCII writing.
6. Both stores: writing a case twice leaves counts and read-back equal; read-back equals the built graph; `find_entities` returns every case's entity for a value; SAME_AS edges survive a rewrite. Neo4j tests run when `NEO4J_URI` is set and are skipped, with a visible reason, otherwise.

## 7. Out of scope

Cross-case matching, SAME_AS writing, flags (SHARED, HUB, MULTI_USER) and Tier 3 signals (next slices); deleting or replacing a case's stored graph; fuzzy name merging; Postgres mirror; access control.
