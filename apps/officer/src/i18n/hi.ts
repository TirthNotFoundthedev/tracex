import type { en } from "./en";

export const hi: Record<keyof typeof en, string> = {
  title: "ट्रेसएक्स अधिकारी",

  "nav.back": "वापस जाएँ",
  "nav.myCases": "मेरे मामले",
  "nav.signOut": "साइन आउट करें",

  // O1 Sign in
  "signIn.title": "साइन इन करें",
  "signIn.userId": "आपका यूज़र आईडी",
  "signIn.password": "आपका पासवर्ड",
  "signIn.show": "दिखाएँ",
  "signIn.hide": "छिपाएँ",
  "signIn.submit": "साइन इन करें",
  "signIn.working": "आपको साइन इन किया जा रहा है...",
  "signIn.forgot": "पासवर्ड भूल गए? अपने एडमिन से पूछें।",
  "signIn.missing": "कृपया अपना यूज़र आईडी और पासवर्ड लिखें।",
  "signIn.error": "हम आपको साइन इन नहीं कर सके। अपना यूज़र आईडी और पासवर्ड जाँचें।",
  "signIn.tooManyTries": "बहुत बार कोशिश हो चुकी है। 15 मिनट रुकें, फिर कोशिश करें।",
  "signIn.tryAgain": "फिर कोशिश करें",

  // O2 My cases
  "cases.title": "मेरे मामले",
  "cases.intro": "खोलने के लिए एक मामला चुनें।",
  "cases.searchLabel": "मामला नंबर से खोजें",
  "cases.searchButton": "खोजें",
  "cases.opened": "खोला गया: {date}",
  "cases.otherCases.one": "1 चीज़ दूसरे मामलों में भी है",
  "cases.otherCases.other": "{n} चीज़ें दूसरे मामलों में भी हैं",
  "cases.showMore": "और दिखाएँ",
  "cases.loading": "आपके मामले लोड हो रहे हैं...",
  "cases.empty": "अभी कोई मामला नहीं है। अपने पर्यवेक्षक से मामले जुड़वाएँ।",
  "cases.noResults": "आपके किसी मामले का यह नंबर नहीं है।",
  "cases.accessApproved": "पहुँच के लिए आपका अनुरोध मंज़ूर हो गया।",
  "cases.seeCase": "मामला देखें",

  // O3 Case
  "case.title": "मामला {number}",
  "case.subtitle": "इस मामले के लोग, फ़ोन नंबर, बैंक खाते और वाहन",
  "case.group.person": "लोग ({n})",
  "case.group.phone": "फ़ोन नंबर ({n})",
  "case.group.account": "बैंक खाते ({n})",
  "case.group.vehicle": "वाहन ({n})",
  "case.groupEmpty": "इस मामले में कोई नहीं है।",
  "case.alsoIn.one": "1 और मामले में भी है",
  "case.alsoIn.other": "{n} और मामलों में भी है",
  "case.onlyHere": "सिर्फ़ इस मामले में",
  "case.org": "संस्था",
  "case.hiddenConnection": "ऐसे मामले में भी है जो आप नहीं देख सकते",
  "case.pleaseCheck": "कृपया जाँचें",

  // O4 Item
  "item.typeIn.person": "मामला {number} का व्यक्ति",
  "item.typeIn.phone": "मामला {number} का फ़ोन नंबर",
  "item.typeIn.account": "मामला {number} का बैंक खाता",
  "item.typeIn.vehicle": "मामला {number} का वाहन",
  "item.showOther": "दूसरे मामले दिखाएँ",
  "item.onlyHere": "यह सिर्फ़ इस मामले में है।",

  // O5 Also appears in
  "also.title": "यह यहाँ भी है",
  "also.intro": "{value} इन मामलों में भी है।",
  "also.caseLine": "मामला {number}, {title}",
  "also.whyLinked": "यह क्यों जोड़ा गया?",
  "also.checkThis": "इसे जाँचें",
  "also.empty": "दिखाने के लिए कोई और मामला नहीं है।",

  // O6 Why linked
  "why.titleStrong": "ये क्यों जुड़े हैं",
  "why.titlePossible": "कृपया इस जुड़ाव को जाँचें",
  "why.confirm": "पुष्टि करें कि यह वही है",
  "why.reject": "यह जुड़ाव अस्वीकार करें",
  "why.undo": "यह जुड़ाव वापस लें",
  "why.reopen": "इस लिंक को फिर से खोलें",
  "why.autoNote": "यह अपने आप जुड़ा था। गलत हो तो आप इसे वापस ले सकते हैं।",
  "why.saving": "आपका फ़ैसला सेव हो रहा है...",
  "why.cannot.lookOnly":
    "आप इस जुड़ाव को देख सकते हैं, पर फ़ैसला नहीं कर सकते। अपने जाँच अधिकारी या पर्यवेक्षक से कहें।",
  "why.cannot.notBothCases": "आपको दोनों मामलों की पहुँच नहीं है।",
  "why.cannot.twoAreas":
    "यह जुड़ाव दो थाना क्षेत्रों को जोड़ता है। इसका फ़ैसला सिर्फ़ वरिष्ठ अधिकारी कर सकते हैं।",
  "why.cannot.notBothAreas": "दोनों थाना क्षेत्र आपके अधीन नहीं हैं।",

  // O7 Reject and undo check
  "reject.title": "यह जुड़ाव अस्वीकार करें?",
  "reject.body": "दोनों रिकॉर्ड अब एक जैसे नहीं दिखाए जाएँगे।",
  "reject.reasonLabel": "आप इसे क्यों अस्वीकार कर रहे हैं?",
  "reject.reasonMissing": "कृपया अपना कारण लिखें।",
  "reject.goBack": "नहीं, वापस जाएँ",
  "reject.confirm": "हाँ, अस्वीकार करें",
  "undo.title": "यह जुड़ाव वापस लें?",
  "undo.body": "दोनों रिकॉर्ड अब एक जैसे नहीं दिखाए जाएँगे।",
  "undo.reasonLabel": "आप इसे क्यों वापस ले रहे हैं?",
  "undo.reasonMissing": "कृपया अपना कारण लिखें।",
  "undo.goBack": "नहीं, वापस जाएँ",
  "undo.confirm": "हाँ, वापस लें",
  "reopen.title": "इस लिंक को फिर से खोलें?",
  "reopen.body":
    "दोनों रिकॉर्ड फिर से संभावित मेल के रूप में दिखेंगे। फिर कोई उन्हें जाँच सकता है।",
  "reopen.reasonLabel": "आप इसे फिर से क्यों खोल रहे हैं?",
  "reopen.goBack": "नहीं, वापस जाएँ",
  "reopen.confirm": "हाँ, फिर से खोलें",

  // O8 Link decided
  "decided.confirmed": "आपने इस जुड़ाव की पुष्टि की। दोनों रिकॉर्ड अब एक जैसे दिखाए जाते हैं।",
  "decided.rejected": "आपने इस जुड़ाव को अस्वीकार किया। गलती हुई हो तो अपने पर्यवेक्षक से कहें।",
  "decided.undone": "आपका फ़ैसला वापस ले लिया गया।",
  "decided.reopened": "आपने इस लिंक को फिर से खोला। यह फ़ैसले का इंतज़ार कर रहा है।",
  "decided.checkAgain": "यह जुड़ाव फिर से जाँचें",
  "decided.undo": "वापस लें",
  "decided.backToCase": "इस मामले पर वापस जाएँ",

  // O9 Other police area
  "restricted.title": "दूसरा थाना क्षेत्र",
  "restricted.body": "{item} दूसरे थाना क्षेत्र के एक मामले में भी है।",
  "restricted.cannotSee": "आप वह मामला नहीं देख सकते।",
  "restricted.ask": "पहुँच माँगें",
  "restricted.pending": "अनुरोध {date} को भेजा गया। फ़ैसला होने पर हम आपको बताएँगे।",
  "restricted.refused": "पहुँच नहीं दी गई।",
  "restricted.refusedNote": "दूसरे थाना क्षेत्र का संदेश: {note}",
  "restricted.askAgain": "फिर से माँगें",
  "restricted.cooldown": "जवाब के 24 घंटे बाद आप फिर माँग सकते हैं।",
  "restricted.tooManyWaiting": "आपके 10 अनुरोध इंतज़ार में हैं। कृपया जवाब का इंतज़ार करें।",

  // O10 Ask for access
  "access.title": "पहुँच माँगें",
  "access.intro": "दूसरे थाना क्षेत्र को बताएँ कि आपको यह मामला क्यों देखना है।",
  "access.reasonLabel": "आपका कारण",
  "access.reasonHint": "10 से 500 अक्षर। लोगों के नाम या फ़ोन नंबर न लिखें।",
  "access.send": "अनुरोध भेजें",
  "access.cancel": "रद्द करें",
  "access.sending": "आपका अनुरोध भेजा जा रहा है...",
  "access.errorEmpty": "कृपया अपना कारण लिखें।",
  "access.errorShort": "कृपया थोड़ा और लिखें: कम से कम 10 अक्षर।",
  "access.errorLong": "कृपया कारण छोटा करें: ज़्यादा से ज़्यादा 500 अक्षर।",

  // O11 Request sent
  "sent.message": "अनुरोध भेज दिया गया। फ़ैसला होने पर हम आपको बताएँगे।",
  "sent.back": "इस मामले पर वापस जाएँ",

  // O12 States
  "state.loading": "लोड हो रहा है...",
  "state.loadingLong": "इसमें समय लग रहा है। कृपया रुकें या फिर कोशिश करें।",
  "state.noConnection": "कनेक्शन नहीं है। कुछ भी नहीं बदला।",
  "state.serverProblem": "हमारी तरफ़ कुछ गड़बड़ हो गई। कुछ भी नहीं बदला।",
  "state.serverHelp": "बार-बार हो तो अपने एडमिन को बताएँ।",
  "state.tryAgain": "फिर कोशिश करें",
  "state.notAllowed": "आपको इसकी पहुँच नहीं है।",
  "state.notFound": "हमें यह नहीं मिला। हो सकता है इसे हटा दिया गया हो। अपने मामलों पर वापस जाएँ।",
  "state.backToCases": "मेरे मामलों पर वापस जाएँ",
  "state.changedMeanwhile":
    "आपके देखते-देखते यह जुड़ाव बदल गया। कुछ भी नहीं बदला। कृपया इसे फिर से जाँचें।",
  "state.somethingMissing": "कुछ कमी है। कृपया जो लिखा है उसे जाँचें।",
  "state.sessionEnding":
    "2 मिनट में आप साइन आउट हो जाएँगे। आपके फ़ैसले पहले ही सहेजे जा चुके हैं। बाद में फिर साइन इन करें।",
  "state.stay": "साइन इन रहें",
  "state.sessionEnded": "आपका सत्र खत्म हो गया। कृपया फिर साइन इन करें।",
  // Added with the screens
  "item.fact.age": "उम्र",
  "item.fact.address": "पता",
  "item.fact.dob": "जन्म तिथि",
  "item.fact.gender": "लिंग",
  "item.fact.relative": "रिश्तेदार",
  "why.moreScore": "मिलान स्कोर: {score} (100 में से)। पक्का मिलान {high} से शुरू होता है।",
  "why.rawValue": "मामला {number}, जैसा लिखा है: {text}",
};
