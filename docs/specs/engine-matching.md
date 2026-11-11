# Engine spec: cross-case matching and scoring

Owner: Iyer (Engine Lead) · Task P1.1 · Ruleset version: `engine-matching/1.1` · Readers: NLP (comparators), Graph (blocking, Tier 3 signals, flags), Backend (contract, review queue), app leads (explanation panel), QA.

**Purpose.** Decide whether two entities from different cases are the same real-world thing, say why, and never lose the originals. A wrong link costs more than a missed one: when in doubt, no link or a human review, never an automatic link.

**Jurisdiction-blind.** The engine matches across all cases with no access awareness. No gate looks at districts or states, and AUTO links are created regardless of jurisdiction (`docs/specs/api-access-control.md` §1). The API enforces what a viewer sees of a link and who may decide on it (§6). All names, numbers and cases in this document are invented.

**Errata 1 (2026-11-11, from the P1.5 data-kit review).** AC-03 numbers corrected (the old pair was not an adjacent swap and reused AC-01's phone). Filled gaps: run scope (`input_case_ids`), REGISTERED_TO source, `seen at` sources, person district, Tier 3 hop rules, identifier-pair run order and entity id order; from the P1.2 contract review: engine call signatures, `decision_id` in edge history, and a reopened pair may be rejected again. No weight, cap, band or flag changed; no engine code existed, so the ruleset version stays `engine-matching/1.1`.

## 1. Entity types and linkable pairs

| Type | Comparable attributes (normalized form produced upstream) |
|---|---|
| PERSON | names (main + aliases from "urf"/"alias"), tokens and phonetic keys after transliteration to Roman, relative name (s/o, d/o, w/o), gender, DOB or age-at-date, locality (village/mohalla/ward), district, attributed identifiers (via edges), case-graph neighbourhood |
| ORG | name without legal/generic suffixes (Pvt Ltd, Traders, Enterprises), locality, district, attributed identifiers |
| PHONE | 10-digit Indian mobile (country code and leading 0 stripped) or STD+landline; UPI handles that are phone numbers become PHONE |
| ACCOUNT | account digits (leading zeros kept), bank/IFSC when known |
| VEHICLE | registration uppercase, no spaces or hyphens (`UP32AB1234`) |
| PLACE, DATE | evidence only, never linked |

Rules: SAME_AS only between two entities of the **same type** from **different cases**. Allowed: PERSON–PERSON, ORG–ORG, PHONE–PHONE, ACCOUNT–ACCOUNT, VEHICLE–VEHICLE. Never cross-type (a person is not their phone; a proprietor is not their shop). Within-case duplicates are merged by the graph stage before matching.

**Attribution** (how a person or org is tied to an identifier, from case-graph edges):

| Edge | Code | Factor `a` | Can be an anchor (§5) |
|---|---|---|---|
| `owns` (stated user/holder in FIR or note; account holder field of a bank statement) | OWNS | 1.0 | yes |
| `registered to` (SIM subscriber record: a row of the subscriber file, `sdr.csv` in the data kit; never an OWNS source) | REGISTERED_TO | 0.5 | no |
| `mentioned alongside` | MENTIONED_WITH | 0.2 | no |

**Identifier flags** (computed by Graph over all cases before scoring; a flagged identifier is a *trap identifier*):

| Flag | Trigger (defaults are ruleset constants, not admin config) |
|---|---|
| SHARED | within one case, attributed (`owns` or `registered to`) to ≥2 distinct persons; or a note on the same line calls it a shop, PCO, office, family or landline number |
| HUB | ≥25 distinct counterparties (called / transferred) in any single case |
| MULTI_USER | attributed with `owns` to persons in ≥2 cases whose best name similarity is < 0.5 and who are not in a confirmed SAME_AS (mule pattern) |

## 2. Candidate generation (blocking)

A pair is compared only if it shares at least one block key. No key, no comparison: the entities stay separate.

| Key | Types | Key value |
|---|---|---|
| B1 ID_VALUE | PHONE, ACCOUNT, VEHICLE | normalized value (accounts: digits only; bank checked at comparison) |
| B2 PHONE_DIGITSET | PHONE | first 2 digits + the 10 digits sorted (finds adjacent transpositions) |
| B3 ANCHOR | PERSON, ORG | any identifier attributed to it shares a B1 or B2 key with one attributed to the other |
| B4 NAME_KEY | PERSON | phonetic key of each *non-common* name token (main or alias) |
| B5 COMMON_LOC | PERSON | name has only common tokens: (phonetic key of whole name, district) |
| B6 NETWORK | PERSON | 2-hop identifier neighbourhoods share ≥2 identifiers that are not HUB or SHARED |
| B7 ORG_KEY | ORG | phonetic key of the reduced org name |

Further rules: same type, different cases; both end cases in the run's `input_case_ids` (default: every loaded case); each unordered pair once; pairs on the block list (§6) are dropped before comparison; a block with >500 members is skipped and counted as `oversized_block` in the run record.

**Common tokens.** A name token is *common* if it is in the ruleset list (mohammad and its variants mohd/md/muhammad, kumar, kumari, singh, kaur, devi, lal, ram, prasad, chand, das, khan, ali, ahmed, shaikh, ansari, sharma, yadav, begum, bai, ben) or appears in ≥1% of all person entities (minimum 20 entities).

**Name comparator contract (NLP).** Normalize: transliterate Devanagari offline to Roman, lowercase, strip punctuation, drop honorifics and kinship words (bhai, ji, sahab, shri, smt, mr, bhaiya, chacha, urf), expand abbreviations (mohd/md → mohammad). Two tokens *match* if their phonetic keys are equal or RapidFuzz `ratio` ≥ 85. Then:

```
name_sim     = (mean ratio/100 of matched token pairs) × |matched| / |tokens in shorter name|
completeness = 0.75 if the shorter name has one token, else 1.0
rarity       = 1.0 if any matched token is non-common, else 0.4
```
Over main names and aliases, the highest `name_sim` is used. Must-pass vectors: `Mohd. Irfan` = `मोहम्मद इरफ़ान` (both → `mohammad irfan`); `Irfan bhai` → `irfan`; `Jaswinder` ~ `Jasvinder`, `Shaikh` ~ `Sheikh`, `Salim` ~ `Saleem` (phonetic keys equal); `Ramesh` ≁ `Suresh`.

## 3. Evidence catalogue

Each item has contribution `c = round(weight × strength, 1)` with strength in [0, 1]; opposing items subtract. **Template key** is `match.evidence.<id lowercase>`; the English below is that key's text and is not in the payload. **Params** hold only values (ids, numbers, normalized values, dates) and codes, never display text; an attribution code renders via `match.attribution.<code lowercase>` (English: "stated user", "SIM registered in this name", "mentioned together"). **Provenance:** an item's `sources` list every line it relies on (for PER_SHARED_NETWORK and PER_CO_LOCATION, each listed identifier or place-date on both sides). Every source belongs to one of the link's two end cases; no item cites or names a third case.

### 3.1 Identifier pairs (PHONE, ACCOUNT, VEHICLE). Caps: T1 100, T2 55, so a transposed phone never reaches High.

| Id | Tier | Trigger | Strength | Weight | Dir | English template |
|---|---|---|---|---|---|---|
| ID_EXACT | 1 | identical normalized value | 1.0 | 100 | + | The same {id_label} {value} appears in both cases. |
| PHONE_TRANSPOSED | 2 | phones equal except one pair of adjacent digits swapped | 1.0 | 55 | + | Phone numbers {value_a} and {value_b} differ only by two swapped digits. This may be a writing mistake. |
| ACCT_BANK_CONFLICT | – | same account digits, both banks/IFSC known and different | – | veto | − | Same account number but at different banks ({bank_a}, {bank_b}). These are different accounts. |

### 3.2 PERSON and ORG pairs: supporting

| Id | Tier | Trigger | Strength | Weight | English template |
|---|---|---|---|---|---|
| SHARED_PHONE | 1 | each side attributed to a phone; the two phones have an AUTO or CONFIRMED SAME_AS | min(a_A, a_B) × t | 45 | Both are linked to phone {value} ({how_a} in {case_a}; {how_b} in {case_b}). |
| SHARED_ACCOUNT | 1 | as above, accounts | min(a_A, a_B) × t | 50 | Both are linked to bank account {value} ({how_a} in {case_a}; {how_b} in {case_b}). |
| SHARED_VEHICLE | 1 | as above, vehicles | min(a_A, a_B) × t | 35 | Both are linked to vehicle {value} ({how_a} in {case_a}; {how_b} in {case_b}). |
| PER_NAME_SIM | 2 | `name_sim` ≥ 0.80 | name_sim × completeness × rarity | 30 | Names are similar: "{name_a}" and "{name_b}" (match {sim} out of 1, after converting Hindi spelling to English letters). |
| PER_RELATIVE_NAME | 2 | both have relative name of same relation, `name_sim` ≥ 0.85 | name_sim | 15 | Father's (or relative's) names match: "{rel_a}" and "{rel_b}". |
| PER_DOB_MATCH | 2 | identical full DOB | 1.0 | 20 | Same date of birth: {dob}. |
| PER_AGE_CLOSE | 2 | no full DOB on one side; ages at a common date differ ≤2 years | 1.0 if Δ≤1, 0.5 if Δ=2 | 10 | Ages are close: {age_a} and {age_b} years. |
| PER_LOCALITY | 2 | same locality (1.0) or same district only (0.4); a person's district is the stated one, else the district of the case | as stated | 10 | Both are linked to the same area: {place}. |
| PER_NEAR_PHONE | 2 | attributed phones form a CONFIRMED PHONE_TRANSPOSED link | min(a_A, a_B) | 15 | Their phone numbers differ by two swapped digits, and an officer confirmed it is the same phone. |
| PER_SHARED_NETWORK | 3 | k ≥ 2 distinct identifiers within 2 hops (called, transferred money to, owns) on both sides; excludes HUB/SHARED identifiers and any identifier already used in a Tier 1 item of this pair. Edge direction is ignored; a path may pass through an excluded identifier, which is itself not counted; `registered to` is not a hop | k=2: 0.6, k=3: 0.8, k≥4: 1.0 | 30 | Both are connected to the same {k} phone numbers or accounts: {list}. |
| PER_CO_LOCATION | 3 | k ≥ 2 distinct (place, date ±1 day) pairs from `seen at` edges on both sides. Sources: a CDR row's tower place and call date for a phone the person `owns` that is not SHARED, HUB or MULTI_USER; a case line stating the person was seen at a place on a date. Places compare by normalized text | k=2: 0.7, k≥3: 1.0 | 20 | Both were recorded at the same place on the same day {k} times. |
| ORG_NAME_SIM | 2 | reduced names `name_sim` ≥ 0.85 and reduced name not empty | name_sim | 40 | Organisation names are similar: "{name_a}" and "{name_b}". |

**Trap factor `t`** = 0.2 if the identifier is SHARED, HUB or MULTI_USER, else 1.0. A trap item carries a modifier (shape in §7; key `match.modifier.trap_identifier`; English: "This {id_label} is used by more than one person, so it counts for less."). A modifier has no sources and never says which other cases raised the flag. Each shared identifier gives its own item. Name dissimilarity alone is never opposing evidence (aliases are common).

### 3.3 PERSON pairs: opposing (soft subtracts; hard subtracts and blocks AUTO; veto forces Low and no edge)

| Id | Trigger | Weight | Severity | English template |
|---|---|---|---|---|
| PER_DOB_CONFLICT | both have full DOB, differ by >1 year | 40 | hard | Dates of birth differ: {dob_a} and {dob_b}. |
| PER_DOB_MISMATCH | both have full DOB, differ by ≤1 year | 15 | soft | Dates of birth are slightly different: {dob_a} and {dob_b}. |
| PER_AGE_CONFLICT | ages at a common date differ >5 years (hard if >10) | 20 (40 if hard) | soft / hard | Ages do not fit: {age_a} and {age_b} years. |
| PER_GENDER_CONFLICT | both genders stated and different | 50 | hard | Recorded as different genders. |
| PER_RELATIVE_CONFLICT | same relation on both sides, `name_sim` < 0.6 | 20 | soft | Father's (or relative's) names differ: "{rel_a}" and "{rel_b}". |

## 4. Identifier links vs person links

1. Identifier pairs are scored and settled first in every run. Identical numbers are linked even when the identifier is a trap: the phone *is* the same phone. The flag only limits what it says about people.
2. A person or org gets Tier 1 evidence from an identifier only through attribution edges, and only when the identifier pair is AUTO or CONFIRMED. If the phone link is undone, every person item built on it disappears on the next run.
3. Traps and their guards:

| Trap | Guard |
|---|---|
| Family or shop phone | SHARED flag → t = 0.2, not an anchor; also excluded from Tier 3 overlaps |
| Common name, same city | rarity 0.4; locality worth 10 at most; such names block only on B5 |
| SIM registered to someone else | `registered to` gives a = 0.5 and is never an anchor |
| Mule account | MULTI_USER flag → t = 0.2, not an anchor |
| Same number, different bank | ACCT_BANK_CONFLICT veto |
| Busy number (call centre, bank collection account) | HUB flag → excluded from Tier 3, t = 0.2 |

## 5. Composite score, bands and the High rule

```
c_i        = round_half_up(w_i × s_i, 1)               (support > 0, oppose < 0)
raw_k      = Σ support c_i in tier k
capadj_k   = min(0, cap_k − raw_k)                      (≤ 0, its own line)
S_raw      = Σ_k (raw_k + capadj_k) + Σ oppose c_i
clampadj   = clamp(S_raw, 0, 100) − S_raw
score      = S_raw + clampadj
```
All arithmetic is exact decimal. The rounding of each `c_i` is the only rounding; every later step sums one-decimal values exactly, so the invariant (§7) is tested by equality.

Caps for PERSON and ORG pairs: T1 60, T2 55, T3 35. No single tier reaches 80, so no pile of evidence from one kind of check reaches High.

**Bands** (defaults): **High ≥ 80**, **Medium 45–79.9**, **Low < 45**. Admin config `matching.thresholds`, stored by the API in Postgres; validation 70 ≤ high_min ≤ 100 and 30 ≤ medium_min ≤ high_min − 10. Each change gets a new `thresholds_version` (increasing integer) through the senior-approved `pending_change` flow (`api-access-control.md` §3.2). A run reads the current version once at start; the run record and every edge it touches carry it. A change takes effect at the next run: AUTO links now below high_min become SUGGESTED; CONFIRMED, REJECTED and UNDONE links are untouched. Weights, caps and flags are not admin-adjustable; changing them bumps the ruleset version.

**High rule: the only path to a link without human review.** A pair becomes AUTO only if every gate passes. Otherwise a pair at Medium or above becomes SUGGESTED and its failed gates are listed.

| Gate | Condition | Template key: English if failed |
|---|---|---|
| G1 score | score ≥ high_min | `match.gate.below_high`: The evidence is not strong enough for an automatic link. |
| G2 anchor | PERSON: at least one SHARED_* item with both attributions OWNS and t = 1.0 | `match.gate.no_anchor`: Needs officer review: no phone, account or vehicle clearly belongs to both. |
| G3 two tiers | PERSON: at least two tiers each contributing ≥15 after caps | `match.gate.single_tier`: Needs officer review: the evidence comes from only one kind of check. |
| G4 no hard conflict | no hard or veto item | `match.gate.hard_conflict`: Needs officer review: some evidence disagrees. |
| G5 legible | both entities' extraction confidence ≥ 0.7 | `match.gate.low_extraction`: Needs officer review: one record was hard to read. |
| G6 cluster safe | C3 and C4 (§6) pass | `match.gate.cluster_conflict` / `_bridge` / `_same_case`: Needs officer review: this would join records that may not belong together. |
| G7 type | ORG pairs never AUTO in this version | `match.gate.org_review_only`: Organisation links always need officer review. |

Identifier pairs need G1, G4, G5 and G6; ID_EXACT alone scores 100 and becomes AUTO. Medium → SUGGESTED. Low → no edge, only a count in the run record.

**Worked numbers (AC-01, person pair):** T1 SHARED_PHONE 45 × min(1.0, 1.0) × 1.0 = 45.0; T2 PER_NAME_SIM "mohammad irfan" vs "irfan", 1.0 × completeness 0.75 × rarity 1.0 → 22.5; T3 PER_SHARED_NETWORK k = 2 → 0.6 × 30 = 18.0. No caps hit, nothing against: 85.5 → High; anchor present, three tiers ≥15, no conflicts → AUTO.

## 6. SAME_AS edges, states, clusters, persistence

**Edge.** A Neo4j relationship between the two untouched entity nodes; nothing is written onto the entities. Properties: `link_id` (random UUIDv4, never derived from entity, case or run ids); `entity_a_id` < `entity_b_id` (canonical pair; at most one SAME_AS edge per pair at any time); `entity_type`, `case_a`, `case_b`, `state`, `score`, `band`, `gates` {passed, failed[]}; `evidence` (the §7 payload); `ruleset_version`, `thresholds_version`, `match_run_id`; `created_at`, `updated_at`; `history[]` ({from, to, actor, at, reason_code, reason_text, decision_id}; `decision_id` null for engine transitions). A later run updates the edge in place (score, evidence, versions; same `link_id`) under the rerun rules below. Apart from withdrawal, the engine never deletes an edge.

**States and transitions.** Roles are the canonical roles of `api-access-control.md` §2.1. "Both ends ALLOW" means the actor has ALLOW on both end cases (§2.4 R3, §3). So a link whose ends are in different districts can be decided only by a SENIOR whose state covers both.

| From → To | Who | Reason |
|---|---|---|
| (none) → AUTO | engine, all gates pass, any jurisdiction | – |
| (none) → SUGGESTED | engine, Medium or a gate failed | – |
| AUTO → SUGGESTED | engine rerun: no longer passes every gate | `DEMOTED` |
| SUGGESTED → AUTO | engine rerun: all AUTO gates now pass | `PROMOTED` |
| SUGGESTED → (edge removed) | engine rerun: score below medium_min | `WITHDRAWN` |
| SUGGESTED → CONFIRMED / REJECTED | INVESTIGATOR or above, both ends ALLOW | reject: required |
| AUTO → CONFIRMED | INVESTIGATOR or above, both ends ALLOW | – |
| AUTO → UNDONE, CONFIRMED → UNDONE | SUPERVISOR or above, both ends ALLOW | required |
| REJECTED → SUGGESTED, UNDONE → SUGGESTED (reopen) | SUPERVISOR or above, both ends ALLOW | required |

**Illegal transitions.** Every other transition is illegal: the API returns 409 and nothing changes (e.g. REJECTED → CONFIRMED, CONFIRMED → REJECTED, AUTO → REJECTED). An AUTO link cannot be rejected, only undone; an INVESTIGATOR who thinks an AUTO link is wrong escalates to a SUPERVISOR. This is intended: one junior decision cannot remove a High link. Free-text reasons are stored only in the edge `history`, never in the audit log.

**Rerun rules.** Each change below emits a transition record:
- A rerun never changes CONFIRMED, REJECTED or UNDONE edges.
- An AUTO edge that no longer passes every gate becomes SUGGESTED (`DEMOTED`); it is never demoted silently.
- A SUGGESTED edge becomes AUTO only if all AUTO gates pass (`PROMOTED`).
- A SUGGESTED edge whose score falls below medium_min is withdrawn: the edge is removed (`WITHDRAWN`) and the pair is **not** put on the block list. If a later run proposes the pair again, that is a new edge with a new `link_id`; a `link_id` never comes back.
- A reopened edge (its history contains REJECTED or UNDONE) is never promoted or withdrawn: per the block-list rule, only a human ends it.

**Block list.** The block list is the set of SAME_AS edges in REJECTED or UNDONE state, keyed by canonical pair; there is no second store. The engine never proposes a blocked pair again and never makes it AUTO. Only a reopen moves it out, and a reopened pair is ended only by a human (CONFIRMED, or REJECTED again); it never becomes AUTO. Scores are never fed back into weights. Undo removes nothing: entities, provenance and the edge with its history remain.

**Audit hand-off.** The engine never imports the API and never writes audit rows. Every engine call that creates or changes edges returns one transition record per transition, its own demotions included: `{link_id, from, to, actor ("engine" or user id), match_run_id, decision_id, reason_code, at}` (`to` is null for WITHDRAWN; `decision_id` is null for engine transitions, `match_run_id` null for human decisions). The API writes the audit rows from these records.

**Engine calls.** `run_matching(input_case_ids, triggered_by, thresholds_version, thresholds)` returns the run record and transition records. `apply_decision(link_id, expected_from, to_state, actor_user_id, decision_id, reason_code, reason_text)` is the only way a human decision changes an edge. The engine checks only that `expected_from` is the edge's current state and that the transition is legal (§6 table); role and jurisdiction are the API's. It returns the transition record, or `ILLEGAL_TRANSITION` / `STATE_MISMATCH` with nothing changed. The API commits the decision and its audit row first and then calls `apply_decision`, replaying it until the engine has applied it. The call is idempotent on `decision_id`: a replay returns the same record and changes nothing. Because the edge may lag the committed decision, `run_matching` starts only when no committed decision is still unapplied, and no decision is accepted while a run is RUNNING; otherwise a rerun could promote, demote or withdraw an edge a human has already decided. The API maps its run scope to case ids; `input_case_ids` empty or omitted means every loaded case.

**Run record** (the engine returns it; the API persists it): `match_run_id` (random), `started_at`, `finished_at`, `triggered_by` (user id of whoever started the run), `input_case_ids`, `ruleset_version`, `thresholds_version`, counts by resulting state and by band (Low pairs counted, not stored), `oversized_block` count, `status` (RUNNING / SUCCEEDED / FAILED), `error_code`.

**Identity clusters**
- C1. A cluster is a connected component of **active** edges (AUTO, CONFIRMED) of one entity type. Membership is derived on read and never stored. The engine exposes no cluster id. Any cluster id the API returns is random and not derived from member ids.
- C2. No implied links: A~B and B~C never create an A~C edge. The API builds cluster and path responses per viewer. Any link with an end case the viewer lacks ALLOW on is a hideable segment and becomes a stub (`api-access-control.md` §4). Members beyond that segment are not listed.
- C3. Before an edge becomes AUTO, the engine checks every cross-case pair in the resulting cluster for opposing items (§3.3 and ACCT_BANK_CONFLICT), whether or not that pair has an edge. A hard or veto item on any pair makes the new edge SUGGESTED (`match.gate.cluster_conflict`). A veto between the edge's own two ends means no edge.
- C4. An AUTO edge may not join two clusters that each have ≥2 members (`match.gate.cluster_bridge`). It may not put two distinct entities from the same case into one cluster (`match.gate.cluster_same_case`). A human may still confirm such an edge.
- C5. Run order: identifier pairs first, then person and org pairs; within each group by score descending, ties by (`entity_a_id`, `entity_b_id`). Entity ids are assigned by ingest, increasing in load order (case id compared numerically, then file, then line), and are stable across runs; random entity ids would break AC-23 and AC-26.

## 7. Explanation payload (one link, `GET` by `link_id`)

```json
{
  "link_id": "6f1c2e9a-0b4d-4f7e-9a51-3c2d8e7b1a40",
  "entity_type": "PERSON", "state": "AUTO", "score": 85.5, "band": "HIGH",
  "thresholds": { "high_min": 80, "medium_min": 45, "thresholds_version": 1 },
  "ruleset_version": "engine-matching/1.1", "gates": { "passed": true, "failed": [] },
  "records": [
    { "entity_id": "ent_a12", "case_id": "CASE-A", "raw_text": "Mohd. Irfan", "normalized": "mohammad irfan", "extraction_confidence": 0.9, "source": { "case_id": "CASE-A", "document_id": "doc_fir_a", "line": 12 } },
    { "entity_id": "ent_b07", "case_id": "CASE-B", "raw_text": "Irfan bhai", "normalized": "irfan", "extraction_confidence": 0.9, "source": { "case_id": "CASE-B", "document_id": "doc_note_b", "line": 3 } }
  ],
  "support": [
    { "tier": 1, "cap": 60, "raw": 45.0, "cap_adjustment": { "value": 0.0, "template_key": "match.adjust.cap" }, "subtotal": 45.0, "items": [
      { "evidence_id": "ev_1", "kind": "SHARED_PHONE", "strength": 1.0, "weight": 45, "contribution": 45.0,
        "is_anchor": true, "modifiers": [], "template_key": "match.evidence.shared_phone",
        "params": { "value": "9000014471", "how_a": "OWNS", "case_a": "CASE-A", "how_b": "OWNS", "case_b": "CASE-B" },
        "sources": [ { "case_id": "CASE-A", "document_id": "doc_fir_a", "line": 12 }, { "case_id": "CASE-B", "document_id": "doc_note_b", "line": 3 } ] } ] },
    { "tier": 2, "cap": 55, "raw": 22.5, "cap_adjustment": { "value": 0.0, "template_key": "match.adjust.cap" }, "subtotal": 22.5, "items": [ "…PER_NAME_SIM 22.5…" ] },
    { "tier": 3, "cap": 35, "raw": 18.0, "cap_adjustment": { "value": 0.0, "template_key": "match.adjust.cap" }, "subtotal": 18.0, "items": [ "…PER_SHARED_NETWORK 18.0…" ] }
  ],
  "against": [],
  "clamp_adjustment": { "value": 0.0, "template_key": "match.adjust.clamp" },
  "history": [ { "from": null, "to": "AUTO", "at": "2026-11-20T10:00:00Z", "reason_code": null } ]
}
```
Other shapes: **modifier** `{ "code": "SHARED" | "HUB" | "MULTI_USER", "factor": 0.2, "template_key": "match.modifier.trap_identifier" }`; **`against` item** = a support item plus `"severity": "soft" | "hard" | "veto"`, with a negative `contribution`; **failed gate** `{ "gate": "G2", "template_key": "match.gate.no_anchor" }`. The payload carries no English text; the client renders every line from `template_key` + `params`. Payload `history` entries carry only `from`, `to`, `at` and `reason_code`; `actor` and `reason_text` stay on the edge and are never in the explanation payload. The engine emits sources as `{case_id, document_id, line}` only; the API may add `page`, `document_type` and `case_number` of that same source document when it serves the payload. The **cited-line set** of a link (what an access grant exposes) is the union of `records[].source` and every `items[].sources`.

**Invariant:** Σ `support[].subtotal` + Σ `against[].contribution` + `clamp_adjustment.value` = `score`, where `subtotal` = `raw` + `cap_adjustment.value`, by exact decimal equality. Masking identifier values, and returning 404 for a link the viewer may not fully see, are the API's job (`api-access-control.md` §2.4 R2, §4).

## 8. Acceptance criteria

Comparator outputs (name_sim, flags, k) are fixtures, so scoring tests do not depend on NLP. Extraction confidence is 0.9 unless stated. "Person" means the PERSON pair.

| # | Synthetic input | Expected |
|---|---|---|
| AC-01 | **Worked scenario.** CASE-A FIR line 12: "Mohd. Irfan … mobile 90000 14471 … a/c 5010000019082 (IFSC SYNB0000123)". CASE-A bank statement: a/c …9082 transfers to UPI 9000021203@upi (line 4) and 9000028816@upi (line 7). CASE-B CDR: 9000021203 → 9000014471 (line 33), 9000028816 → 9000014471 (line 41). CASE-B note line 3: "Number 9000014471 is used by Irfan bhai." | Phone pairs …4471, …1203, …8816: ID_EXACT 100 → AUTO (three edges). Person: SHARED_PHONE 45.0 + PER_NAME_SIM 22.5 + PER_SHARED_NETWORK (k=2) 18.0 = **85.5 High, AUTO**, all gates pass. Four SAME_AS edges in all, in a run with `input_case_ids` [CASE-A, CASE-B]; entities untouched. |
| AC-02 | Vehicle `UP32AB1234` in CASE-C FIR and `up 32 ab 1234` in CASE-D note | Vehicle pair 100 High AUTO |
| AC-03 | Phones 9000081914 (CASE-E) and 9000081194 (CASE-F) (adjacent swap) | PHONE_TRANSPOSED 55 → Medium SUGGESTED |
| AC-04 | Account 5010000077345 at IFSC SYNB0000123 (CASE-G) and at IFSC FAKE0000456 (CASE-H) | ACCT_BANK_CONFLICT veto → Low, no edge |
| AC-05 | "Jaswinder Bhullar", age 34, Village Kherapur (CASE-J) vs "Jasvinder Bhullar", age 35, Kherapur (CASE-K); fixture name_sim 0.94 | 28.2 + 10 + 10 = **48.2 Medium** SUGGESTED (no anchor) |
| AC-06 | **Trap, common name same city.** "Mohammed Khan" (CASE-L) vs "Mohd Khan" (CASE-M), both district Rampur only; name_sim 1.0, rarity 0.4 | 12.0 + 4.0 = **16.0 Low**, no edge |
| AC-07 | **Trap, family phone.** 9000022310 `owns` by "Ramesh Yadav" and "Sunita Yadav" in CASE-N (SHARED); `owns` by "Suresh Yadav" in CASE-P; network k=3 | Phone pair AUTO. Ramesh~Suresh: 45 × 0.2 = 9.0 + 24.0 = **33.0 Low**, no edge |
| AC-08 | **Trap, SIM in another's name.** "Vikram Chauhan" `owns` 9000035562 (CASE-Q); subscriber record "Kamla Devi" `registered to` it (CASE-R); same district; genders not recorded; network k=4 | 22.5 + 4.0 + 30.0 = **56.5 Medium** SUGGESTED; never AUTO (no anchor) |
| AC-09 | **Trap, mule account.** a/c 5010000055501 (same IFSC) `owns` by "Ajay Pal" (CASE-S), "Imran Qureshi" (CASE-T), "Deepak Rawat" (CASE-U) → MULTI_USER; Ajay~Imran network k=3 | Account pairs AUTO. Ajay~Imran: 50 × 0.2 = 10.0 + 24.0 = **34.0 Low** |
| AC-10 | **Trap, same name, different DOB.** "Arjun Mehra" DOB 1990-04-12 vs "Arjun Mehra" DOB 1978-09-30, same locality, both `owns` 9000046120 | 45 + 30 + 10 − 40 = **45.0 Medium** (boundary inclusive); G4 fails, never AUTO |
| AC-11 | **Trap, pile of weak evidence.** No shared identifier. name_sim 0.95 rare, same DOB, same locality, relative name_sim 0.9, network k=4, co-location k=3 | T2 raw 72.0, cap −17.0 → 55; T3 raw 50.0, cap −15.0 → 35; **score 90.0**, G2 fails → **SUGGESTED** |
| AC-12 | **Trap, weak chain.** P1 "Sohan Rawat" DOB 1985-02-01 (CASE-V) ~ P2 "Sohan Rawat" no DOB (CASE-W) passes, 88; P2 ~ P3 "Sohan Rawat" DOB 1999-07-15 (CASE-X) passes pairwise, 84 | P1~P2 AUTO; P2~P3 **SUGGESTED** (`match.gate.cluster_conflict`); no P1~P3 edge; cluster {P1, P2} |
| AC-13 | **Trap, bridge.** Clusters {Q1,Q2} CONFIRMED and {Q3,Q4} AUTO; Q2~Q3 passes G1–G5 with 91 | **SUGGESTED** (`match.gate.cluster_bridge`); clusters stay separate |
| AC-14 | **Trap, same-case merge.** R1 (CASE-Y) ~ R2 (CASE-Z) AUTO; R3 (CASE-Y, distinct from R1) ~ R2 passes G1–G5 | R3~R2 **SUGGESTED** (`match.gate.cluster_same_case`) |
| AC-15 | AC-05 pair REJECTED by an INVESTIGATOR; next run adds a shared owned phone (score would pass every gate) | No new edge, no state change, no transition record; pair stays REJECTED |
| AC-16 | AC-01 person link UNDONE by a SUPERVISOR with reason | State UNDONE, history 2 entries; entities and phone link unchanged; cluster splits; payload still retrievable; one transition record |
| AC-17 | "मोहम्मद इरफ़ान" (Devanagari, CASE-AA) vs "Mohd Irfan" (CASE-AB), both `owns` 9000051234 | name_sim 1.0 → 30.0 + 45.0 = **75.0 Medium** SUGGESTED |
| AC-18 | high_min set to 90 (thresholds_version 2). Rerun AC-01; separately, rerun AC-01 after its person link was CONFIRMED. | AUTO person link → SUGGESTED with transition record `reason_code DEMOTED`, edge `thresholds_version` 2; phone links stay AUTO. A CONFIRMED link is untouched, with no record. Setting high_min 65 fails validation. |
| AC-19 | AC-02 but one vehicle entity has extraction confidence 0.5 | Score 100, G5 fails → **SUGGESTED** |
| AC-20 | Every edge in AC-01…AC-27 | Invariant (§7) holds by decimal equality. Every item has ≥1 source, all in the two end cases. Every `how_*` param is an attribution code. No English in the payload. |
| AC-21 | ORG "Shree Balaji Traders" vs "Shri Balaji Trading Co", both `owns` a/c 5010000066602, same locality | Score ≥ 80 possible but G7 → **SUGGESTED** only |
| AC-22 | **Cross-district.** "Naveen Tomar" `owns` 9000062201 in CASE-RG (district Rivergate); "Naveen Tomar" `owns` it in CASE-HC (district Hillcrest); network k=3 | 45 + 30 + 24 = **99.0 AUTO**. A Rivergate INVESTIGATOR with no grant sees a stub only; the link by id is 404. Only a SENIOR covering both districts may undo it. |
| AC-23 | **Determinism.** AC-01…AC-22 inputs run twice on empty stores; then run again on the same store | Identical pairs, states, scores, evidence and transitions (ids and timestamps aside). The rerun creates no edges, keeps every `link_id` and emits no transition records. |
| AC-24 | **Illegal transitions.** REJECTED → CONFIRMED; CONFIRMED → REJECTED; AUTO → REJECTED; an INVESTIGATOR tries AUTO → UNDONE | 409 for each, or 403 for the role case (`api-access-control.md` R2). Edge, history and audit unchanged. |
| AC-25 | **Reopen then confirm.** AC-15 pair reopened by a SUPERVISOR with reason, then confirmed by an INVESTIGATOR; then a rerun | REJECTED → SUGGESTED → CONFIRMED, two transition records; the rerun never makes it AUTO |
| AC-26 | **Veto inside a cluster.** Entity ids A1 < A2 < A3, a/c 5010000088801: A1 at IFSC SYNB0000123 (CASE-1), A2 bank unknown (CASE-2), A3 at IFSC FAKE0000456 (CASE-3) | A1~A2 AUTO; A2~A3 **SUGGESTED** (`match.gate.cluster_conflict`, since A1 vs A3 is a veto); A1~A3 no edge |
| AC-27 | AC-01 run record | Has every §6 run-record field: `thresholds_version` 1, counts AUTO 4, `status` SUCCEEDED |

## 9. Out of scope, and open risks for Fable

Out of scope: machine-learned matching or score feedback; linking PLACE, DATE or cross-type; within-case dedupe (Graph stage); masking, access control and audit rows (API); Hindi template text (i18n owners); incremental real-time matching (runs are batch).

Open risks:
1. Weights, caps and the 0.2 trap factor are expert-set, not calibrated; they need the P1.5 golden set before demo, and any tuning is a ruleset version bump.
2. Very common given names outside the list (e.g. "Rajesh Kumar") rely on the 1% corpus rule; on a small demo corpus that rule may not fire, which would flood review with Medium pairs.
3. The worked scenario depends on NLP extracting `owns` from note phrasing ("is used by") and UPI handles as phones; if extraction misses these, AC-01 drops to Medium.
4. Requiring an owned identifier for AUTO means aliases linked only by behaviour always need review; intended, but it adds reviewer load.
5. Cluster guards depend on processing order (C5); deterministic, but a link held for review today may have been AUTO under a different run history.
