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

The partition is a function of the set of the case's mentions, not of their load order. Writings that state the same about themselves (same normalized name, writing, aliases, attributes, role side, IFSC) are one node. Two nodes are linked when a join rule below holds. A connected set of nodes is one entity only if no two of its nodes are separated by a veto; if any pair is, none of the set joins and each node is its own entity (no guessing), so a silent writing that fits two conflicting ones, or a witness sharing a name with a complainant and an accused, stands alone. A link through a bare name or alias that two or more different full names claim (`Kalu urf` in two names, or `Pappu` beside `Pappu Sharma` and `Kalu urf Pappu`) is refused in both directions; plain alias chains `A urf B`, `B urf C` still join. For account digits written with two different IFSCs, IFSC-less writings fall out of the same rule: they fit both, so they join only each other. Entities are numbered afterwards by first mention in load order (section 4). Every merged writing stays its own `Mention`.

| Type | Joins when | Veto (stays separate) |
|---|---|---|
| PHONE, VEHICLE | equal normalized value | none |
| ACCOUNT | equal normalized digits | both IFSCs known and different (matching spec, `ACCT_BANK_CONFLICT`) |
| PERSON | equal normalized name with two or more tokens; or a single-token name only when the raw text is equal ignoring case and spacing; or the normalized name equals an alias stated on another writing in the case (`Kalu` and `Ramesh Kasana urf Kalu`), either direction | same relation and different relative names; different gender; different DOB; ages more than 2 apart; different locality or district (all compared as normalized text, only when both are stated); a complainant-side role (complainant, victim, informant, in English, romanised Hindi or Devanagari) against an accused-side role (accused, suspect, arrested); witnesses are neutral |
| ORG | equal normalized name and equal raw text ignoring case, spacing, punctuation and a leading `M/s` (so `Traders` and `Enterprises` writings never join) | different locality |

This matches the data-kit `within_case` groups (data-kit §8.1): the planted groups for `MOHD IRFAN`, `KAMLA DEVI`, the two Balaji organisations (not joined to each other: `shree` is not `shri`), the three phone writings and the two plate writings join; no entity spans two ground-truth entities outside one group.

## 3. Provenance

Every mention, edge and entity carries `file` and `line` (physical line, as `SourceRef`). An edge or mention never points outside its case. The graph holds only what the extractor emitted; unreadable rows stay in `CaseRecords.errors`, outside the graph. Bank rows whose counterparty is a name or empty, and CDR rows without a tower place, give no counterparty edge or no `SEEN_AT` edge; the row is still cited by the account and phone mentions it produced.

## 4. Entity ids, ordering and idempotency

`entity_id` = `<case_id>:<ordinal>` with `ordinal` a 5-digit count of entities in the case in order of first mention: load order of the file (`fir`, `notes`, `sdr`, `cdr`, `bank`; later batches after, by number), then line, then persons, orgs, identifiers, then extractor order. `entity_sort_key(id)` returns `(district digit, sequence, ordinal)` so ids compare in matching spec C5 order (case id numerically, then load order); plain string order is wrong across cases (`C-1100` < `C-150`). Same `CaseRecords` always gives the same ids, mention ids and edge ids. Adding a later batch file only appends: earlier ids do not move.

`write_case` is an upsert keyed by `entity_id`, `mention_id`, `place_id` and `edge_id`: nodes and edges are merged and properties set to the same values, so loading a case twice changes nothing and keeps any SAME_AS edge already on its entities. It never deletes. Constraints and indexes (`ensure_schema`, idempotent): unique `Entity.entity_id`, `Mention.mention_id`, `Place.place_id`; index on `Entity(type, normalized)` (the matcher's exact-value lookup, key B1) and `Entity.case_id`. Rulings (Iyer): entity `confidence` is the highest mention confidence (an attribution keeps its own, lower, confidence); `SEEN_AT` is drawn for the calling number only (`tower_place` is the calling party's cell).

**Re-upload.** A loaded file is immutable in this slice and upsert-only is the rule: Backend rejects a re-upload of an already loaded file name with different content (409) until a replace-case flow exists. Replacing a case is a later slice owned by Backend (upload flow) with Graph (the delete/replace primitive); it must hand SAME_AS edges on removed entities to the engine as transitions, never delete them silently.

## 5. Interface the matcher imports

`build_case_graph(records) -> CaseGraph`; `CaseGraphStore` with `ensure_schema()`, `write_case(graph)`, `read_case(case_id) -> CaseGraph | None`, `case_ids()`, `find_entities(type, normalized) -> tuple[Entity, ...]` (all cases, sort-key order); `Neo4jCaseGraphStore.connect(uri, user, password)`, `InMemoryCaseGraphStore`; the model types; `entity_sort_key`.

**Case district.** The district of a case is the `District:` line of its FIR header (data-kit section 4.1; the only source of case metadata the ingest layer reads). The extractor carries it as `CaseRecords.district` and `district_source`; the builder puts it on the graph as `CaseGraph.district = CaseDistrict(normalized, display_value, file, line)`, or `None` when the case has no FIR, no `District:` line or an empty value (an unreadable header line stays an extraction error). Neo4j keeps it on a `:Case {case_id}` node (`district`, `district_display`, `district_file`, `district_line`; unique `case_id`); `read_case` returns it, and rewriting a case rewrites it. The matcher's corpus exposes `Corpus.district_of_case(case_id) -> str | None` (normalized) and `Corpus.effective_districts(entity_id) -> frozenset[str]`: the districts stated for the entity (mention attribute `district`), else the district of its case, else empty. Evidence that relies on a case district cites `CaseDistrict.file` and `line`.

**Neighbourhood helpers (Tier 3).** `NetworkIndex(graphs)` (`graph/neighbourhood.py`) answers, over case graphs and without knowing flags, tiers or scores: `neighbourhood(entity_id)` gives the identifiers within 2 hops through OWNS, CALLED and TRANSFERRED_TO with edge direction ignored, each with the lines of the edges on the paths to it (REGISTERED_TO and MENTIONED_WITH are not hops; a path may pass through any identifier); `owned(entity_id, type)` the identifiers of one type the entity owns; `seen_at(phone_id)` the (place, call date, CDR line) records of a phone. `match_seen_at(a, b)` pairs the place-dates two lists share on the same normalized place within one day, each unit used once, cited by its earliest row. The matcher's Tier 3 provider (`matching/tier3.py`) applies the flag exclusions and the Tier 1 exclusion on top.

## 6. Acceptance criteria

1. Same `CaseRecords` twice gives equal graphs (ids, mentions, edges); ordinals follow load order.
2. Section 2 table, one test per row and per veto; an ambiguous mention starts its own entity.
3. Every mention and edge carries its extractor source; mention counts equal extractor mention counts per type.
4. Edges per section 1 on hand-written cases, incl. hedged flag, SDR REGISTERED_TO, DR and CR direction, name counterparties giving no edge.
5. On kit data (small tier, all cases): every engine entity maps onto at most one ground-truth `within_case` group or ungrouped entity, and every planted within-case group maps onto exactly one engine entity. Noise groups do too, except where a Devanagari writing and its Roman writing transliterate differently (`shrivastav` / `srivastava`): joining those needs fuzzy matching, so at most 5% may stay split, each containing a non-ASCII writing.
6. Both stores: writing a case twice leaves counts and read-back equal; read-back equals the built graph; `find_entities` returns every case's entity for a value; SAME_AS edges survive a rewrite. Neo4j tests run when `NEO4J_URI` is set and are skipped, with a visible reason, otherwise.

## 7. Out of scope

Cross-case matching, SAME_AS writing, flags (SHARED, HUB, MULTI_USER) and Tier 3 signals (next slices); deleting or replacing a case's stored graph; fuzzy name merging; Postgres mirror; access control.
