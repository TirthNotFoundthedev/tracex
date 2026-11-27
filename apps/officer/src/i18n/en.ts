/**
 * Officer app strings, screens O1-O12 (design-flows section 2). Wording follows DESIGN_RULES section 7.
 * `{name}` marks a value filled in by `t(key, lang, { name })`. Keys ending `.one` and `.other` are the
 * singular and plural forms; the caller picks one by count.
 * Not here (shared with the admin panel, owned by packages/ui): strength words, role labels,
 * explanation template keys, entity type names, language names.
 */
export const en = {
  title: "TraceX Officer",

  "nav.back": "Back",
  "nav.myCases": "My cases",
  "nav.signOut": "Sign out",

  // O1 Sign in
  "signIn.title": "Sign in",
  "signIn.userId": "Your user ID",
  "signIn.password": "Your password",
  "signIn.show": "Show",
  "signIn.hide": "Hide",
  "signIn.submit": "Sign in",
  "signIn.working": "Signing you in...",
  "signIn.forgot": "Forgot your password? Ask your admin.",
  "signIn.missing": "Please write your user ID and your password.",
  "signIn.error": "We could not sign you in. Check your user ID and password.",
  "signIn.tooManyTries": "Too many tries. Please wait 15 minutes, then try again.",
  "signIn.tryAgain": "Try again",

  // O2 My cases
  "cases.title": "My cases",
  "cases.intro": "Choose a case to open.",
  "cases.searchLabel": "Search by case number",
  "cases.searchButton": "Search",
  "cases.opened": "Opened {date}",
  "cases.otherCases.one": "1 item appears in other cases",
  "cases.otherCases.other": "{n} items appear in other cases",
  "cases.showMore": "Show more",
  "cases.loading": "Loading your cases...",
  "cases.empty": "No cases yet. Ask your supervisor to add your cases.",
  "cases.noResults": "No case of yours has that number.",
  "cases.accessApproved": "Your request for access was approved.",
  "cases.seeCase": "See the case",

  // O3 Case
  "case.title": "Case {number}",
  "case.subtitle": "People, phone numbers, bank accounts and vehicles in this case",
  "case.group.person": "People ({n})",
  "case.group.phone": "Phone numbers ({n})",
  "case.group.account": "Bank accounts ({n})",
  "case.group.vehicle": "Vehicles ({n})",
  "case.groupEmpty": "None in this case.",
  "case.alsoIn.one": "Also in 1 case",
  "case.alsoIn.other": "Also in {n} cases",
  "case.onlyHere": "Only in this case",
  "case.pleaseCheck": "Please check",

  // O4 Item
  "item.typeIn.person": "Person in Case {number}",
  "item.typeIn.phone": "Phone number in Case {number}",
  "item.typeIn.account": "Bank account in Case {number}",
  "item.typeIn.vehicle": "Vehicle in Case {number}",
  "item.showOther": "Show other cases",
  "item.onlyHere": "This appears only in this case.",

  // O5 Also appears in
  "also.title": "Also appears in",
  "also.intro": "{value} also appears in these cases.",
  "also.caseLine": "Case {number}, {place}",
  "also.whyLinked": "Why was this linked?",
  "also.checkThis": "Check this",
  "also.empty": "There are no other cases to show.",

  // O6 Why linked
  "why.titleStrong": "Why these are linked",
  "why.titlePossible": "Please check this link",
  "why.confirm": "Confirm they are the same",
  "why.reject": "Reject this link",
  "why.undo": "Undo this link",
  "why.autoNote": "This was linked automatically. You can undo it if it is wrong.",
  "why.saving": "Saving your decision...",
  "why.cannot.lookOnly":
    "You can look at this link but not decide it. Ask your investigating officer or supervisor.",
  "why.cannot.notBothCases": "You do not have access to both cases.",
  "why.cannot.twoAreas": "This link joins two police areas. Only a senior officer can decide it.",
  "why.cannot.notBothAreas": "You do not cover both police areas.",

  // O7 Reject and undo check
  "reject.title": "Reject this link?",
  "reject.body": "The two records will no longer be shown as the same.",
  "reject.reasonLabel": "Why are you rejecting it?",
  "reject.reasonMissing": "Please write your reason.",
  "reject.goBack": "No, go back",
  "reject.confirm": "Yes, reject",
  "undo.title": "Undo this link?",
  "undo.body": "The two records will no longer be shown as the same.",
  "undo.reasonLabel": "Why are you undoing it?",
  "undo.reasonMissing": "Please write your reason.",
  "undo.goBack": "No, go back",
  "undo.confirm": "Yes, undo",

  // O8 Link decided
  "decided.confirmed": "You confirmed this link. The two records are now shown as the same.",
  "decided.rejected": "You rejected this link. If this was a mistake, ask your supervisor.",
  "decided.undone": "Your decision was undone.",
  "decided.checkAgain": "Check this link again",
  "decided.undo": "Undo",
  "decided.backToCase": "Back to this case",

  // O9 Other police area
  "restricted.title": "Another police area",
  "restricted.body": "{item} also appears in a case in another police area.",
  "restricted.cannotSee": "You cannot see that case.",
  "restricted.ask": "Ask for access",
  "restricted.pending": "Request sent on {date}. We will tell you when it is decided.",
  "restricted.refused": "Access was not given.",
  "restricted.refusedNote": "Note from the other police area: {note}",
  "restricted.askAgain": "Ask again",
  "restricted.cooldown": "You can ask again 24 hours after the answer.",
  "restricted.tooManyWaiting": "You have 10 requests waiting. Please wait for an answer.",

  // O10 Ask for access
  "access.title": "Ask for access",
  "access.intro": "Tell the other police area why you need to see this case.",
  "access.reasonLabel": "Your reason",
  "access.reasonHint": "10 to 500 characters. Do not write names or phone numbers.",
  "access.send": "Send request",
  "access.cancel": "Cancel",
  "access.sending": "Sending your request...",
  "access.errorEmpty": "Please write your reason.",
  "access.errorShort": "Please write a little more: at least 10 characters.",
  "access.errorLong": "Please shorten your reason: at most 500 characters.",

  // O11 Request sent
  "sent.message": "Request sent. We will tell you when it is decided.",
  "sent.back": "Back to this case",

  // O12 States
  "state.loading": "Loading...",
  "state.loadingLong": "This is taking long. Please wait or try again.",
  "state.noConnection": "No connection. Nothing was changed.",
  "state.serverProblem": "Something went wrong on our side. Nothing was changed.",
  "state.serverHelp": "If it keeps happening, tell your admin.",
  "state.tryAgain": "Try again",
  "state.notAllowed": "You do not have access to this.",
  "state.notFound": "We could not find this. It may have been removed. Go back to your cases.",
  // Temporary: replace with the shared packages/ui safety-pause string when it exists (see PR #44).
  "state.safetyPause":
    "The system is paused for safety. Nothing was changed. Please try again later.",
  "state.backToCases": "Back to my cases",
  "state.runInProgress":
    "The system is updating links between cases. Nothing was changed. Please try again in a minute.",
  "state.changedMeanwhile":
    "This link changed while you were looking. Nothing was changed. Please check it again.",
  "state.somethingMissing": "Something is missing. Please check what you wrote.",
  "state.sessionEnding": "You will be signed out in 2 minutes.",
  "state.stay": "Stay signed in",
  "state.sessionEnded": "Your session has ended. Please sign in again.",
} as const;
