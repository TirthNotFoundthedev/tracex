import { en as sharedEn, format, tShared, type Language, type SharedMessageKey } from "@tracex/ui";
import type { Reason, Source } from "@tracex/ui";

import type { components } from "../api/schema";
import { formatDate } from "./format";
import { groupPhone, titleCase } from "./value";

type Explanation = components["schemas"]["Explanation"];
type SourceRef = components["schemas"]["explanation.schema"]["$defs"]["source"];
type Template = { template_key: string; params: unknown; sources?: SourceRef[] };

const isShared = (key: string): key is SharedMessageKey => key in sharedEn;

const NAME_PARAMS = new Set(["name", "name_a", "name_b", "rel_a", "rel_b", "place"]);
const DATE_PARAMS = new Set(["dob", "dob_a", "dob_b", "date"]);
const VALUE_PARAMS = new Set(["value", "value_a", "value_b"]);

/** Param values arrive as codes, lists or stored (lower case, ISO date) values; the sentence needs words. */
function wordsFor(name: string, value: unknown, lang: Language, isPhone: boolean): string {
  if (Array.isArray(value)) return value.map(String).join(", ");
  const text = String(value);
  if (NAME_PARAMS.has(name)) return titleCase(text);
  if (DATE_PARAMS.has(name)) return formatDate(text, lang);
  if (VALUE_PARAMS.has(name) && isPhone) return groupPhone(text);
  const kind =
    name === "how_a" || name === "how_b" ? "attribution" : name === "id_label" ? "id_label" : "";
  if (kind) {
    const key = `match.${kind}.${text.toLowerCase()}`;
    if (isShared(key)) return tShared(key, lang);
  }
  return text;
}

/** The sentence for one explanation line, or undefined when the shared catalog has no template for it. */
export function renderTemplate(
  templateKey: string,
  params: unknown,
  lang: Language,
): string | undefined {
  if (!isShared(templateKey)) return undefined;
  const values: Record<string, string> = {};
  if (typeof params === "object" && params !== null) {
    const idLabel = (params as Record<string, unknown>)["id_label"];
    const isPhone = String(idLabel).toLowerCase() === "phone" || templateKey.includes("phone");
    for (const [name, value] of Object.entries(params))
      values[name] = wordsFor(name, value, lang, isPhone);
  }
  return format(tShared(templateKey, lang), values);
}

export interface PanelContent {
  support: Reason[];
  against: Reason[];
  gates: string[];
  sources: Source[];
}

/** Case numbers by case id, from the two records, so a source line can name its case. */
function caseNumbers(
  explanation: Explanation,
  fallback: Record<string, string>,
): Record<string, string> {
  const numbers = { ...fallback };
  for (const record of explanation.records) {
    const known = record.source.case_number;
    if (known) numbers[record.source.case_id] = known;
  }
  return numbers;
}

/**
 * Turns the explanation payload into what the shared panel components show. Numbers (score, tier, cap) are
 * left out on purpose: the officer app shows words, and no figure on any view.
 */
export function panelContent(
  explanation: Explanation,
  lang: Language,
  caseNumberById: Record<string, string>,
  unknownDocument: string,
): PanelContent {
  const numbers = caseNumbers(explanation, caseNumberById);
  const toSource = (source: SourceRef): Source => {
    const result: Source = {
      caseNumber: source.case_number ?? numbers[source.case_id] ?? "",
      documentType: source.document_type ?? unknownDocument,
    };
    if (source.page != null) result.page = source.page;
    result.line = source.line;
    return result;
  };
  const seen = new Set<string>();
  const sources: Source[] = [];
  const toReason = (item: Template): Reason | undefined => {
    const text = renderTemplate(item.template_key, item.params, lang);
    if (text === undefined) return undefined;
    const first = item.sources?.[0];
    const reason: Reason = { text };
    for (const source of item.sources ?? []) {
      const mapped = toSource(source);
      const id = `${mapped.caseNumber}|${mapped.documentType}|${mapped.page}|${mapped.line}`;
      if (!seen.has(id)) {
        seen.add(id);
        sources.push(mapped);
      }
    }
    if (first) reason.source = toSource(first);
    return reason;
  };
  const defined = (list: (Reason | undefined)[]) =>
    list.filter((r): r is Reason => r !== undefined);
  const gates = explanation.gates.passed
    ? []
    : explanation.gates.failed
        .map((gate) => renderTemplate(gate.template_key, {}, lang))
        .filter((text): text is string => text !== undefined);
  return {
    support: defined(
      explanation.support.flatMap((tier) => tier.items.map((item) => toReason(item as Template))),
    ),
    against: defined(explanation.against.map((item) => toReason(item as Template))),
    gates: [...new Set(gates)],
    sources,
  };
}
