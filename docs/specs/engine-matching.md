# Engine spec: cross-case matching and scoring

Owner: Iyer (Engine Lead) · Task P1.1 · Ruleset version: `engine-matching/1.0`
Readers: NLP (comparators), Graph (blocking, Tier 3 signals, flags), Backend (contract, review queue), app leads (explanation panel), QA.

**Purpose.** Decide whether two entities from different cases are the same real-world thing, say why, and never lose the originals. A wrong link costs more than a missed one: when in doubt, no link or a human review, never an automatic link.

All names, numbers and cases in this document are invented.

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

| Edge | Factor `a` | Can be an anchor (§5) |
|---|---|---|
| `owns` (stated user/holder in FIR or note; account holder field of a bank statement) | 1.0 | yes |
| `registered to` (SIM subscriber record) | 0.5 | no |
| `mentioned alongside` | 0.2 | no |

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

Further rules: same type, different cases; each unordered pair once; pairs on the block list (§6) are dropped before comparison; a block with >500 members is skipped and counted as `oversized_block` in the run report.

**Common tokens.** A name token is *common* if it is in the ruleset list (mohammad and its variants mohd/md/muhammad, kumar, kumari, singh, kaur, devi, lal, ram, prasad, chand, das, khan, ali, ahmed, shaikh, ansari, sharma, yadav, begum, bai, ben) or appears in ≥1% of all person entities (minimum 20 entities).

**Name comparator contract (NLP).** Normalize: transliterate Devanagari offline to Roman, lowercase, strip punctuation, drop honorifics and kinship words (bhai, ji, sahab, shri, smt, mr, bhaiya, chacha, urf), expand abbreviations (mohd/md → mohammad). Two tokens *match* if their phonetic keys are equal or RapidFuzz `ratio` ≥ 85. Then:

```
name_sim     = (mean ratio/100 of matched token pairs) × |matched| / |tokens in shorter name|
completeness = 0.75 if the shorter name has one token, else 1.0
rarity       = 1.0 if any matched token is non-common, else 0.4
```
Over main names and aliases, the highest `name_sim` is used. Must-pass vectors: `Mohd. Irfan` = `मोहम्मद इरफ़ान` (both → `mohammad irfan`); `Irfan bhai` → `irfan`; `Jaswinder` ~ `Jasvinder`, `Shaikh` ~ `Sheikh`, `Salim` ~ `Saleem` (phonetic keys equal); `Ramesh` ≁ `Suresh`.

## 3. Evidence catalogue

Each evidence item: contribution `c = round(weight × strength, 1)`, strength in [0, 1]. Opposing items subtract. Template keys are `match.evidence.<id lowercase>`; `{params}` are filled by the engine, which also returns the rendered English.

### 3.1 Identifier pairs (PHONE, ACCOUNT, VEHICLE)

| Id | Tier | Trigger | Strength | Weight | Dir | English template |
|---|---|---|---|---|---|---|
| ID_EXACT | 1 | identical normalized value | 1.0 | 100 | + | The same {id_label} {value} appears in both cases. |
| PHONE_TRANSPOSED | 2 | phones equal except one pair of adjacent digits swapped | 1.0 | 55 | + | Phone numbers {value_a} and {value_b} differ only by two swapped digits. This may be a writing mistake. |
| ACCT_BANK_CONFLICT | – | same account digits, both banks/IFSC known and different | – | veto | − | Same account number but at different banks ({bank_a}, {bank_b}). These are different accounts. |

Caps: T1 100, T2 55. A transposed phone can never reach High (55 < 80).

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
| PER_LOCALITY | 2 | same locality (1.0) or same district only (0.4) | as stated | 10 | Both are linked to the same area: {place}. |
| PER_NEAR_PHONE | 2 | attributed phones form a CONFIRMED PHONE_TRANSPOSED link | min(a_A, a_B) | 15 | Their phone numbers differ by two swapped digits, and an officer confirmed it is the same phone. |
| PER_SHARED_NETWORK | 3 | k ≥ 2 distinct identifiers within 2 hops (called, transferred money to, owns) on both sides; excludes HUB/SHARED identifiers and any identifier already used in a Tier 1 item of this pair | k=2: 0.6, k=3: 0.8, k≥4: 1.0 | 30 | Both are connected to the same {k} phone numbers or accounts: {list}. |
| PER_CO_LOCATION | 3 | k ≥ 2 distinct (place, date ±1 day) pairs from `seen at` edges on both sides | k=2: 0.7, k≥3: 1.0 | 20 | Both were recorded at the same place on the same day {k} times. |
| ORG_NAME_SIM | 2 | reduced names `name_sim` ≥ 0.85 and reduced name not empty | name_sim | 40 | Organisation names are similar: "{name_a}" and "{name_b}". |

`t` (trap factor) = 0.2 if the identifier is SHARED, HUB or MULTI_USER, else 1.0. A trap item carries a modifier `{code, factor, template_key}` with English: "This {id_label} is used by more than one person, so it counts for less." Each shared identifier gives its own item. Name dissimilarity alone is never opposing evidence (aliases are common).

### 3.3 PERSON pairs: opposing

| Id | Trigger | Weight | Severity | English template |
|---|---|---|---|---|
| PER_DOB_CONFLICT | both have full DOB, differ by >1 year | 40 | hard | Dates of birth differ: {dob_a} and {dob_b}. |
| PER_DOB_MISMATCH | both have full DOB, differ by ≤1 year | 15 | soft | Dates of birth are slightly different: {dob_a} and {dob_b}. |
| PER_AGE_CONFLICT | ages at a common date differ >5 years (hard if >10) | 20 (40 if hard) | soft / hard | Ages do not fit: {age_a} and {age_b} years. |
| PER_GENDER_CONFLICT | both genders stated and different | 50 | hard | Recorded as different genders. |
| PER_RELATIVE_CONFLICT | same relation on both sides, `name_sim` < 0.6 | 20 | soft | Father's (or relative's) names differ: "{rel_a}" and "{rel_b}". |

Severity: **soft** subtracts only; **hard** subtracts and blocks automatic linking; **veto** forces Low and no edge.

## 4. Identifier links vs person links

1. Identifier pairs are scored and settled first in every run. Identical numbers are linked even when the identifier is a trap: the phone *is* the same phone. The flag only limits what it says about people.
2. A person or org gets Tier 1 evidence from an identifier only through attribution edges, and only when the identifier pair is AUTO or CONFIRMED. If a reviewer undoes the phone link, every person item built on it disappears on the next run.
3. Traps:

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
c_i        = round(w_i × s_i, 1)                        (support > 0, oppose < 0)
raw_k      = Σ support c_i in tier k
capadj_k   = min(0, cap_k − raw_k)                      (≤ 0, shown as its own line)
S_raw      = Σ_k (raw_k + capadj_k) + Σ oppose c_i
clampadj   = clamp(S_raw, 0, 100) − S_raw
score      = S_raw + clampadj                           (one decimal, round half up)
```
Every item, cap adjustment and clamp adjustment is in the explanation, so the listed lines sum exactly to the score.

Caps for PERSON and ORG pairs: T1 60, T2 55, T3 35. No single tier reaches 80, so no pile of evidence from one kind of check reaches High.

Default bands (admin config `matching.thresholds`): **High ≥ 80**, **Medium 45–79.9**, **Low < 45**. Validation: 70 ≤ high_min ≤ 100; 30 ≤ medium_min ≤ high_min − 10. A change applies at the next run: AUTO links now below high_min become SUGGESTED; CONFIRMED, REJECTED and UNDONE links are untouched. Weights, caps and flags are not admin-adjustable; changing them bumps the ruleset version.

**High rule: the only path to a link without human review.** A pair becomes AUTO only if every gate passes; otherwise a score ≥ high_min becomes SUGGESTED with the failed gates listed.

| Gate | Condition | Template key / English if failed |
|---|---|---|
| G1 score | score ≥ high_min | (band is not High) |
| G2 anchor | PERSON: at least one SHARED_* item with both attributions `owns` and t = 1.0 | `gate.no_anchor`: Needs officer review: no phone, account or vehicle clearly belongs to both. |
| G3 two tiers | PERSON: at least two tiers each contributing ≥15 after caps | `gate.single_tier`: Needs officer review: the evidence comes from only one kind of check. |
| G4 no hard conflict | no hard or veto item | `gate.hard_conflict`: Needs officer review: some evidence disagrees. |
| G5 legible | both entities' extraction confidence ≥ 0.7 | `gate.low_extraction`: Needs officer review: one record was hard to read. |
| G6 cluster safe | cluster rules C2–C4 (§6) pass | `gate.cluster_conflict`, `gate.cluster_bridge`, `gate.cluster_same_case` |
| G7 type | ORG pairs never AUTO in this version | `gate.org_review_only`: Organisation links always need officer review. |

Identifier pairs need G1, G4, G5, G6 (ID_EXACT alone → 100 → AUTO). Medium → SUGGESTED. Low → no edge; only the count goes into the run report.

**Worked numbers (scenario AC-01, person pair):** SHARED_PHONE 45 × min(1.0, 1.0) × 1.0 = 45.0 (T1). PER_NAME_SIM: "mohammad irfan" vs "irfan", name_sim 1.0 × completeness 0.75 × rarity 1.0 = 0.75 → 22.5 (T2). PER_SHARED_NETWORK k = 2 → 0.6 × 30 = 18.0 (T3). No caps hit, nothing against. Score 85.5 → High; anchor present, three tiers ≥15, no conflicts → AUTO.

## 6. SAME_AS edges, states, clusters

**Edge properties** (on a Neo4j relationship between the two untouched entity nodes; nothing is written onto the entities): `link_id`, `entity_a_id` < `entity_b_id` (canonical order), `entity_type`, `case_a`, `case_b`, `state`, `score`, `band`, `gates` {passed, failed[]}, `evidence` (the §7 payload), `ruleset_version`, `thresholds_used`, `match_run_id`, `created_at`, `created_by` (`engine` or user id), `updated_at`, `history[]` ({from, to, actor, at, reason}).

**States and transitions**

| From → To | Who | Reason required |
|---|---|---|
| (none) → AUTO | engine, all gates pass | no |
| (none) → SUGGESTED | engine, Medium or gate failed | no |
| AUTO → SUGGESTED | engine, after a threshold change or lost evidence | no (system reason recorded) |
| SUGGESTED → CONFIRMED / AUTO → CONFIRMED | reviewer role | no |
| SUGGESTED → REJECTED | reviewer role | yes |
| AUTO → UNDONE / CONFIRMED → UNDONE | reviewer role | yes |
| REJECTED or UNDONE → SUGGESTED (reopen) | reviewer role | yes |

REJECTED and UNDONE pairs go on the **block list**: the engine never proposes them again in any state and never makes them AUTO; only a reviewer can reopen, and a reopened pair can end only in CONFIRMED by a human. Scores are never fed back into weights. Every transition is emitted as an audit event to the API (Backend owns the log). Undo removes nothing: the entities, their provenance and the edge with its history remain.

**Identity clusters**

- C1. A cluster is a connected component of **active** edges (AUTO, CONFIRMED) of one entity type. SUGGESTED, REJECTED and UNDONE edges never join a cluster. Cluster ids are derived (smallest member entity id) and recomputed, never stored on entities.
- C2. No implied links: A~B and B~C never create an A~C edge. The panel shows C as "linked through B" with the path; path strength is the lowest edge score on it.
- C3. Conflict check: before an edge becomes AUTO, every cross-case pair in the resulting cluster is checked for hard or veto items (§3.3). Any hit makes the new edge SUGGESTED (`gate.cluster_conflict`).
- C4. Two guards: an AUTO edge may not join two clusters that each have ≥2 members (`gate.cluster_bridge`), and may not put two distinct entities from the same case into one cluster (`gate.cluster_same_case`). A human may confirm such an edge.
- C5. Run order: identifier pairs first, then person/org pairs by score descending, ties by (`entity_a_id`, `entity_b_id`). Same input gives the same result.

## 7. Explanation payload (one link, `GET` by `link_id`)

```json
{
  "link_id": "lnk_7f3a",
  "entity_type": "PERSON",
  "state": "AUTO",
  "score": 85.5,
  "band": "HIGH",
  "thresholds": { "high_min": 80, "medium_min": 45 },
  "ruleset_version": "engine-matching/1.0",
  "gates": { "passed": true, "failed": [] },
  "records": [
    { "entity_id": "ent_a12", "case_id": "CASE-A", "raw_text": "Mohd. Irfan", "normalized": "mohammad irfan",
      "extraction_confidence": 0.9,
      "source": { "case_id": "CASE-A", "document_id": "doc_fir_a", "line": 12 } },
    { "entity_id": "ent_b07", "case_id": "CASE-B", "raw_text": "Irfan bhai", "normalized": "irfan",
      "extraction_confidence": 0.9,
      "source": { "case_id": "CASE-B", "document_id": "doc_note_b", "line": 3 } }
  ],
  "support": [
    { "tier": 1, "cap": 60, "raw": 45.0, "cap_adjustment": 0.0, "subtotal": 45.0, "items": [
      { "evidence_id": "ev_1", "kind": "SHARED_PHONE", "strength": 1.0, "weight": 45, "contribution": 45.0,
        "modifiers": [], "is_anchor": true,
        "template_key": "match.evidence.shared_phone",
        "params": { "value": "9000014471", "how_a": "stated user", "case_a": "CASE-A",
                    "how_b": "stated user", "case_b": "CASE-B" },
        "text_en": "Both are linked to phone 9000014471 (stated user in CASE-A; stated user in CASE-B).",
        "sources": [ { "case_id": "CASE-A", "document_id": "doc_fir_a", "line": 12 },
                     { "case_id": "CASE-B", "document_id": "doc_note_b", "line": 3 } ] } ] },
    { "tier": 2, "cap": 55, "raw": 22.5, "cap_adjustment": 0.0, "subtotal": 22.5, "items": [ "…PER_NAME_SIM, 22.5…" ] },
    { "tier": 3, "cap": 35, "raw": 18.0, "cap_adjustment": 0.0, "subtotal": 18.0, "items": [ "…PER_SHARED_NETWORK, 18.0…" ] }
  ],
  "against": [],
  "clamp_adjustment": 0.0,
  "history": [ { "from": null, "to": "AUTO", "actor": "engine", "at": "2026-11-20T10:00:00Z", "reason": null } ]
}
```
Items in `against` have the same shape plus `"severity": "soft" | "hard" | "veto"` and negative `contribution`. Failed gates appear as `{ "gate": "G2", "template_key": "gate.no_anchor", "text_en": "…" }`. **Invariant:** Σ `support[].subtotal` + Σ `against[].contribution` + `clamp_adjustment` = `score`. Masking of identifier values is the API's job under access control; the engine returns full normalized values.

## 8. Acceptance criteria

Comparator outputs (name_sim, flags, k) are given as fixtures, so scoring tests do not depend on NLP. Extraction confidence is 0.9 unless stated. "Person" rows describe the PERSON pair.

| # | Synthetic input | Expected |
|---|---|---|
| AC-01 | **Worked scenario.** CASE-A FIR line 12: "Mohd. Irfan … mobile 90000 14471 … a/c 5010000019082 (IFSC SYNB0000123)". CASE-A bank statement: a/c …9082 transfers to UPI 9000021203@upi (line 4) and 9000028816@upi (line 7). CASE-B CDR: 9000021203 → 9000014471 (line 33), 9000028816 → 9000014471 (line 41). CASE-B note line 3: "Number 9000014471 is used by Irfan bhai." | Phone pair: ID_EXACT 100 → AUTO. Person pair: SHARED_PHONE 45.0 + PER_NAME_SIM 22.5 + PER_SHARED_NETWORK (k=2) 18.0 = **85.5 High, AUTO**, all gates pass. Two separate SAME_AS edges; four source lines linked. |
| AC-02 | Vehicle `UP32AB1234` in CASE-C FIR and `up 32 ab 1234` in CASE-D note | Vehicle pair 100 High AUTO |
| AC-03 | Phones 9000014471 (CASE-E) and 9000017441 (CASE-F) | PHONE_TRANSPOSED 55 → Medium SUGGESTED |
| AC-04 | Account 5010000077345 at IFSC SYNB0000123 (CASE-G) and at IFSC FAKE0000456 (CASE-H) | ACCT_BANK_CONFLICT veto → Low, no edge |
| AC-05 | "Jaswinder Bhullar", age 34, Village Kherapur (CASE-J) vs "Jasvinder Bhullar", age 35, Kherapur (CASE-K); fixture name_sim 0.94 | 28.2 + 10 + 10 = **48.2 Medium** SUGGESTED (no anchor) |
| AC-06 | **Trap, common name same city.** "Mohammed Khan" (CASE-L) vs "Mohd Khan" (CASE-M), both district Rampur only; name_sim 1.0, rarity 0.4 | 12.0 + 4.0 = **16.0 Low**, no edge |
| AC-07 | **Trap, family phone.** 9000022310 `owns` by "Ramesh Yadav" and "Sunita Yadav" in CASE-N (SHARED); `owns` by "Suresh Yadav" in CASE-P; network k=3 | Phone pair AUTO. Ramesh~Suresh: 45 × 0.2 = 9.0 + 24.0 = **33.0 Low**, no edge |
| AC-08 | **Trap, SIM in another's name.** "Vikram Chauhan" `owns` 9000035562 (CASE-Q); subscriber record "Kamla Devi" `registered to` it (CASE-R); same district; genders not recorded; network k=4 | 22.5 + 4.0 + 30.0 = **56.5 Medium** SUGGESTED; never AUTO (no anchor) |
| AC-09 | **Trap, mule account.** a/c 5010000055501 (same IFSC) `owns` by "Ajay Pal" (CASE-S), "Imran Qureshi" (CASE-T), "Deepak Rawat" (CASE-U) → MULTI_USER; Ajay~Imran network k=3 | Account pairs AUTO. Ajay~Imran: 50 × 0.2 = 10.0 + 24.0 = **34.0 Low** |
| AC-10 | **Trap, same name, different DOB.** "Arjun Mehra" DOB 1990-04-12 vs "Arjun Mehra" DOB 1978-09-30, same locality, both `owns` 9000046120 | 45 + 30 + 10 − 40 = **45.0 Medium** (boundary inclusive); G4 fails, never AUTO |
| AC-11 | **Trap, pile of weak evidence.** No shared identifier. name_sim 0.95 rare, same DOB, same locality, relative name_sim 0.9, network k=4, co-location k=3 | T2 raw 72.0, cap −17.0 → 55; T3 raw 50.0, cap −15.0 → 35; **score 90.0**, G2 fails → **SUGGESTED** |
| AC-12 | **Trap, weak chain.** P1 "Sohan Rawat" DOB 1985-02-01 (CASE-V) ~ P2 "Sohan Rawat" no DOB (CASE-W) passes, 88; P2 ~ P3 "Sohan Rawat" DOB 1999-07-15 (CASE-X) passes pairwise, 84 | P1~P2 AUTO; P2~P3 **SUGGESTED** (`gate.cluster_conflict`); no P1~P3 edge; cluster {P1, P2} |
| AC-13 | **Trap, bridge.** Clusters {Q1,Q2} CONFIRMED and {Q3,Q4} AUTO; Q2~Q3 passes G1–G5 with 91 | **SUGGESTED** (`gate.cluster_bridge`); clusters stay separate |
| AC-14 | **Trap, same-case merge.** R1 (CASE-Y) ~ R2 (CASE-Z) AUTO; R3 (CASE-Y, distinct from R1) ~ R2 passes G1–G5 | R3~R2 **SUGGESTED** (`gate.cluster_same_case`) |
| AC-15 | AC-01 person pair REJECTED by reviewer; next run adds a shared account (score would be 100) | No new edge or state change; pair stays REJECTED |
| AC-16 | AC-01 person link UNDONE by reviewer with reason | State UNDONE, history has 2 entries; both entities and phone link unchanged; cluster splits; payload still retrievable |
| AC-17 | "मोहम्मद इरफ़ान" (Devanagari, CASE-AA) vs "Mohd Irfan" (CASE-AB), both `owns` 9000051234 | name_sim 1.0 → 30.0 + 45.0 = **75.0 Medium** SUGGESTED |
| AC-18 | Admin sets high_min 90, then reruns AC-01 | Person link AUTO → SUGGESTED (85.5 < 90); phone link stays AUTO. Setting high_min 65 is rejected by validation |
| AC-19 | AC-02 but one vehicle entity has extraction confidence 0.5 | Score 100, G5 fails → **SUGGESTED** |
| AC-20 | Every edge in AC-01…AC-19 | Payload invariant (§7) holds exactly; every item has ≥1 source line |
| AC-21 | ORG "Shree Balaji Traders" vs "Shri Balaji Trading Co", both `owns` a/c 5010000066602, same locality | Score ≥ 80 possible but G7 → **SUGGESTED** only |

## 9. Out of scope, and open risks for Fable

Out of scope: machine-learned matching or score feedback; linking PLACE, DATE or cross-type; within-case dedupe (Graph stage); masking and access control (API); Hindi template text (added by app/i18n owners); incremental real-time matching (runs are batch).

Open risks:
1. Weights, caps and the 0.2 trap factor are expert-set, not calibrated; they need the P1.5 golden set before demo, and any tuning is a ruleset version bump.
2. Very common given names outside the list (e.g. "Rajesh Kumar") rely on the 1% corpus rule; on a small demo corpus that rule may not fire, which would flood review with Medium pairs.
3. The worked scenario depends on NLP extracting `owns` from note phrasing ("is used by") and UPI handles as phones; if extraction misses these, AC-01 drops to Medium.
4. Requiring an owned identifier for AUTO means aliases linked only by behaviour always need review; intended, but it adds reviewer load.
5. Cluster guards depend on processing order (C5); deterministic, but a link held for review today may have been AUTO under a different run history.
