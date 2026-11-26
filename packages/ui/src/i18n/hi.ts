import type { en } from "./en";

export const hi: Record<keyof typeof en, string> = {
  "language.en": "English",
  "language.hi": "हिन्दी",
  "language.switchLabel": "भाषा",

  "item.person": "व्यक्ति",
  "item.phone": "फ़ोन नंबर",
  "item.bank": "बैंक खाता",
  "item.vehicle": "वाहन",
  "item.case": "मामला",

  "nav.back": "वापस",
  "nav.signOut": "साइन आउट करें",
  "nav.breadcrumbLabel": "आप यहाँ हैं",
  "nav.mainLabel": "मुख्य भाग",
  "nav.openRow": "खोलें",

  "strength.strong": "पक्का मिलान",
  "strength.possible": "संभावित मिलान। कृपया जाँचें।",
  "strength.bar3": "पट्टी: 3 में से 3 भरी",
  "strength.bar2": "पट्टी: 3 में से 2 भरी",
  "strength.score": "अंक: {score}",

  "reasons.for": "हमें ऐसा क्यों लगता है",
  "reasons.against": "यह गलत क्यों हो सकता है",
  "reasons.noneAgainst": "इस लिंक के खिलाफ़ कुछ नहीं मिला।",
  "reasons.supportSr": "लिंक के पक्ष में:",
  "reasons.againstSr": "लिंक के विरुद्ध:",

  "evidence.heading": "यह कहाँ से आया",
  "evidence.case": "मामला {case}",
  "evidence.page": "पृष्ठ {page}",
  "evidence.line": "पंक्ति {line}",

  "detail.label": "और जानकारी",

  "restricted.title": "दूसरा थाना क्षेत्र",
  "restricted.body": "यह दूसरे थाना क्षेत्र के एक मामले में भी है।",
  "restricted.ask": "पहुँच माँगें",
  "restricted.sent": "अनुरोध {date} को भेजा गया। फ़ैसला होने पर हम आपको बताएँगे।",

  "message.info": "सूचना:",
  "message.success": "हो गया:",
  "message.error": "समस्या:",
  "message.dismiss": "यह संदेश बंद करें",

  "confirm.no": "नहीं, वापस जाएँ",
  "confirm.reasonHint": "{min} से {max} अक्षरों के बीच।",

  "field.required": "कृपया भरें: {field}।",
  "field.requiredMark": "(ज़रूरी)",
  "field.tooShort": "कृपया कम से कम {min} अक्षर लिखें: {field}।",
  "search.button": "खोजें",

  "filedrop.choose": "फ़ाइल चुनें",
  "filedrop.drop": "या उसे यहाँ छोड़ें",
  "filedrop.chosen": "चुनी गई फ़ाइल: {name}",

  "table.sortBy": "{column} के अनुसार क्रम लगाएँ",
  "table.sortedUp": "छोटे से बड़े क्रम में",
  "table.sortedDown": "बड़े से छोटे क्रम में",

  "tabs.selected": "(चुना गया)",

  "pager.more": "और दिखाएँ",
  "pager.count": "{total} में से {shown} दिखाए गए",

  "loading.default": "लोड हो रहा है...",
  "loading.slow": "इसमें देर लग रही है। कृपया रुकें या दोबारा कोशिश करें।",
  "empty.hint": "यहाँ अभी कुछ दिखाने को नहीं है।",
};
