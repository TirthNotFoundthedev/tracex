export const en = {
  "language.en": "English",
  "language.hi": "हिन्दी",
  "language.switchLabel": "Language",

  "item.person": "Person",
  "item.phone": "Phone number",
  "item.bank": "Bank account",
  "item.vehicle": "Vehicle",
  "item.case": "Case",
  "item.org": "Organisation",

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
  "error.runInProgress": "A matching run is in progress. Try again in a few minutes.",
  "error.safetyPause": "The system is paused for a safety check. Try again later.",

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

  "graph.canvasLabel":
    "Network picture: {nodes} items and {links} links. Use Tab to move between items. Choose Show as list for a text version.",
  "graph.empty": "Nothing to show yet. Search for a person, phone number, account or vehicle.",
  "graph.truncated": "Showing the 150 closest. Narrow the search to see others.",
  "graph.labelsHidden":
    "Some names are hidden so the picture stays readable ({count} hidden). Select a node to see its name, or show the list.",
  "graph.showList": "Show as list",
  "graph.showPicture": "Show as picture",
  "graph.zoomIn": "Zoom in",
  "graph.zoomOut": "Zoom out",
  "graph.zoomReset": "Reset view",
  "graph.nodeName": "{type}: {label}",
  "graph.edge.strongShort": "Strong",
  "graph.edge.possibleShort": "Possible",
  "graph.edge.connectedLabel": "Connected: {a} and {b}",
  "graph.edge.restrictedLabel": "A link to another police area from {a}",
  "graph.edge.sameAsLabel": "{strength}, {state}: {a} and {b}",
  "graph.state.auto": "Linked automatically",
  "graph.state.suggested": "Waiting for a person to check",
  "graph.state.confirmed": "Confirmed by an officer",
  "graph.connected": "Connected",
  "graph.col.type": "Type",
  "graph.col.name": "Name or number",
  "graph.col.from": "From",
  "graph.col.to": "To",
  "graph.col.link": "Link",
  "graph.col.state": "Status",
  "graph.nodesCaption": "Items in the network",
  "graph.linksCaption": "Links in the network",
  "graph.legend.title": "How to read the picture",
  "graph.legend.nodes": "Shapes",
  "graph.legend.edges": "Lines",
  "graph.legend.node.person": "Person",
  "graph.legend.node.phone": "Phone number",
  "graph.legend.node.bank": "Bank account",
  "graph.legend.node.vehicle": "Vehicle",
  "graph.legend.node.org": "Organisation",
  "graph.legend.node.restricted": "Another police area (no details shown)",
  "graph.legend.edge.strong": "Solid thick line: strong match, same one",
  "graph.legend.edge.possible": "Dashed line: possible match, needs a person to check",
  "graph.legend.edge.connected":
    "Dotted thin line: connected, for example a person and their phone",
  "graph.legend.edge.restricted": "Dashed line to a lock: a link to another police area",
} as const;
