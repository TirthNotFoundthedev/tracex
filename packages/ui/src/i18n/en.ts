export const en = {
  "language.en": "English",
  "language.hi": "हिन्दी",
  "language.switchLabel": "Language",

  "item.person": "Person",
  "item.phone": "Phone number",
  "item.bank": "Bank account",
  "item.vehicle": "Vehicle",
  "item.case": "Case",

  "nav.back": "Back",
  "nav.signOut": "Sign out",
  "nav.breadcrumbLabel": "You are here",
  "nav.mainLabel": "Main sections",
  "nav.openRow": "Open",

  "strength.strong": "Strong match",
  "strength.possible": "Possible match. Please check.",
  "strength.bar3": "Bar: 3 of 3 filled",
  "strength.bar2": "Bar: 2 of 3 filled",
  "strength.score": "Score: {score}",

  "reasons.for": "Why we think so",
  "reasons.against": "Why it may be wrong",
  "reasons.noneAgainst": "Nothing found against this link.",
  "reasons.supportSr": "Supports the link:",
  "reasons.againstSr": "Against the link:",

  "evidence.heading": "Where this came from",
  "evidence.case": "Case {case}",
  "evidence.page": "page {page}",
  "evidence.line": "line {line}",

  "detail.label": "More detail",

  "restricted.title": "Another police area",
  "restricted.ask": "Ask for access",
  "restricted.sent": "Request sent on {date}. We will tell you when it is decided.",

  "message.info": "Note:",
  "message.success": "Done:",
  "message.error": "Problem:",
  "message.dismiss": "Close this message",

  "confirm.no": "No, go back",
  "confirm.reasonHint": "Between {min} and {max} characters.",

  "field.required": "Please fill in: {field}.",
  "field.requiredMark": "(required)",
  "field.tooShort": "Please write a little more: at least {min} characters.",
  "search.button": "Search",

  "filedrop.choose": "Choose a file",
  "filedrop.drop": "or drop it here",
  "filedrop.chosen": "Chosen file: {name}",

  "table.sortBy": "Sort by {column}",
  "table.sortedUp": "sorted low to high",
  "table.sortedDown": "sorted high to low",

  "tabs.selected": "(selected)",

  "pager.more": "Show more",
  "pager.count": "Showing {shown} of {total}",

  "loading.default": "Loading...",
  "loading.slow": "This is taking long. Please wait or try again.",
  "empty.hint": "Nothing to show here yet.",

  "role.junior": "Officer",
  "role.investigator": "Investigating officer",
  "role.supervisor": "Supervisor",
  "role.senior": "Senior officer",
  "role.admin": "Administrator",

  "access.stub.connection_exists": "Also appears in a case in another police area.",
  "restricted.cannotSee": "You cannot see that case.",
  "restricted.refused": "Access was not given.",
  "restricted.refusedNote": "Reason given:",
  "restricted.askAgain": "Ask again",

  "match.id_label.phone": "phone number",
  "match.id_label.account": "bank account number",
  "match.id_label.vehicle": "vehicle number",
  "match.attribution.owns": "stated user",
  "match.attribution.registered_to": "SIM registered in this name",
  "match.attribution.mentioned_with": "mentioned together",

  "match.evidence.id_exact": "The same {id_label} {value} appears in both cases.",
  "match.evidence.phone_transposed":
    "Phone numbers {value_a} and {value_b} differ only by two swapped digits. This may be a writing mistake.",
  "match.evidence.acct_bank_conflict":
    "Same account number but at different banks ({bank_a}, {bank_b}). These are different accounts.",
  "match.evidence.shared_phone":
    "Both are linked to phone {value} ({how_a} in {case_a}; {how_b} in {case_b}).",
  "match.evidence.shared_account":
    "Both are linked to bank account {value} ({how_a} in {case_a}; {how_b} in {case_b}).",
  "match.evidence.shared_vehicle":
    "Both are linked to vehicle {value} ({how_a} in {case_a}; {how_b} in {case_b}).",
  "match.evidence.per_name_sim": "Names sound alike: {name_a} / {name_b}",
  "match.evidence.per_relative_name": "Father's (or relative's) names match: {rel_a} / {rel_b}",
  "match.evidence.per_dob_match": "Same date of birth: {dob}.",
  "match.evidence.per_age_close": "Ages are close: {age_a} and {age_b} years.",
  "match.evidence.per_locality": "Both are linked to the same area: {place}.",
  "match.evidence.per_near_phone":
    "Their phone numbers differ by two swapped digits, and an officer confirmed it is the same phone.",
  "match.evidence.per_shared_network":
    "Both are connected to the same {k} phone numbers or accounts: {list}.",
  "match.evidence.per_co_location":
    "Both were recorded at the same place on the same day {k} times.",
  "match.evidence.org_name_sim": "Organisation names are similar: {name_a} / {name_b}",
  "match.evidence.per_dob_conflict": "Dates of birth differ: {dob_a} and {dob_b}.",
  "match.evidence.per_dob_mismatch": "Dates of birth are slightly different: {dob_a} and {dob_b}.",
  "match.evidence.per_age_conflict": "Ages do not fit: {age_a} and {age_b} years.",
  "match.evidence.per_gender_conflict": "Recorded as different genders.",
  "match.evidence.per_relative_conflict":
    "Father's (or relative's) names differ: {rel_a} / {rel_b}",

  "match.gate.below_high": "The evidence is not strong enough for an automatic link.",
  "match.gate.no_anchor":
    "Needs officer review: no phone, account or vehicle clearly belongs to both.",
  "match.gate.single_tier": "Needs officer review: the evidence comes from only one kind of check.",
  "match.gate.hard_conflict": "Needs officer review: some evidence disagrees.",
  "match.gate.low_extraction": "Needs officer review: one record was hard to read.",
  "match.gate.cluster_conflict":
    "Needs officer review: this would join records that may not belong together.",
  "match.gate.cluster_bridge":
    "Needs officer review: this would join records that may not belong together.",
  "match.gate.cluster_same_case":
    "Needs officer review: this would join records that may not belong together.",
  "match.gate.org_review_only": "Organisation links always need officer review.",

  "match.adjust.cap": "Score reduced: this kind of check has reached its limit.",
  "match.adjust.clamp": "Score adjusted to stay between 0 and 100.",
  "match.modifier.trap_identifier":
    "This {id_label} is used by more than one person, so it counts for less.",
} as const;
