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
  "restricted.ask": "पहुँच माँगें",
  "restricted.sent": "अनुरोध {date} को भेजा गया। फ़ैसला होने पर हम आपको बताएँगे।",

  "message.info": "सूचना:",
  "message.success": "हो गया:",
  "message.error": "समस्या:",
  "message.dismiss": "यह संदेश बंद करें",

  "confirm.no": "नहीं, वापस जाएँ",
  "confirm.reasonHint": "{min} से {max} अक्षर के बीच।",

  "field.required": "कृपया भरें: {field}।",
  "field.requiredMark": "(ज़रूरी)",
  "field.tooShort": "थोड़ा और लिखें: कम से कम {min} अक्षर।",
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

  "role.junior": "अधिकारी",
  "role.investigator": "जाँच अधिकारी",
  "role.supervisor": "पर्यवेक्षक",
  "role.senior": "वरिष्ठ अधिकारी",
  "role.admin": "प्रशासक",

  "access.stub.connection_exists": "यह दूसरे थाना क्षेत्र के एक मामले में भी है।",
  "restricted.cannotSee": "आप वह मामला नहीं देख सकते।",
  "restricted.refused": "पहुँच नहीं दी गई।",
  "restricted.refusedNote": "बताया गया कारण:",
  "restricted.askAgain": "दोबारा माँगें",

  "match.id_label.phone": "फ़ोन नंबर",
  "match.id_label.account": "बैंक खाता नंबर",
  "match.id_label.vehicle": "वाहन नंबर",
  "match.attribution.owns": "बताया गया उपयोगकर्ता",
  "match.attribution.registered_to": "इस नाम पर सिम दर्ज है",
  "match.attribution.mentioned_with": "साथ में उल्लेख",

  "match.evidence.id_exact": "दोनों मामलों में एक ही {id_label} {value} है।",
  "match.evidence.phone_transposed":
    "फ़ोन नंबर {value_a} और {value_b} में सिर्फ़ दो अंकों की जगह बदली है। यह लिखने की गलती हो सकती है।",
  "match.evidence.acct_bank_conflict":
    "खाता नंबर एक है, पर बैंक अलग हैं ({bank_a}, {bank_b})। ये अलग खाते हैं।",
  "match.evidence.shared_phone":
    "दोनों फ़ोन {value} से जुड़े हैं ({case_a} में {how_a}; {case_b} में {how_b})।",
  "match.evidence.shared_account":
    "दोनों बैंक खाता {value} से जुड़े हैं ({case_a} में {how_a}; {case_b} में {how_b})।",
  "match.evidence.shared_vehicle":
    "दोनों वाहन {value} से जुड़े हैं ({case_a} में {how_a}; {case_b} में {how_b})।",
  "match.evidence.per_name_sim": "नाम मिलते-जुलते हैं: {name_a} / {name_b}",
  "match.evidence.per_relative_name": "पिता (या रिश्तेदार) के नाम मिलते हैं: {rel_a} / {rel_b}",
  "match.evidence.per_dob_match": "जन्म तारीख़ एक है: {dob}।",
  "match.evidence.per_age_close": "उम्र लगभग बराबर है: {age_a} और {age_b} साल।",
  "match.evidence.per_locality": "दोनों एक ही इलाके से जुड़े हैं: {place}।",
  "match.evidence.per_near_phone":
    "उनके फ़ोन नंबरों में दो अंकों की जगह बदली है, और एक अधिकारी ने पुष्टि की कि यह वही फ़ोन है।",
  "match.evidence.per_shared_network": "दोनों एक ही {k} फ़ोन नंबरों या खातों से जुड़े हैं: {list}।",
  "match.evidence.per_co_location": "दोनों एक ही दिन एक ही जगह {k} बार दर्ज हुए।",
  "match.evidence.org_name_sim": "संस्थाओं के नाम मिलते-जुलते हैं: {name_a} / {name_b}",
  "match.evidence.per_dob_conflict": "जन्म तारीख़ अलग हैं: {dob_a} और {dob_b}।",
  "match.evidence.per_dob_mismatch": "जन्म तारीख़ में थोड़ा फ़र्क है: {dob_a} और {dob_b}।",
  "match.evidence.per_age_conflict": "उम्र मेल नहीं खाती: {age_a} और {age_b} साल।",
  "match.evidence.per_gender_conflict": "लिंग अलग दर्ज है।",
  "match.evidence.per_relative_conflict": "पिता (या रिश्तेदार) के नाम अलग हैं: {rel_a} / {rel_b}",

  "match.gate.below_high": "अपने आप लिंक करने के लिए सबूत काफ़ी मज़बूत नहीं है।",
  "match.gate.no_anchor":
    "अधिकारी को जाँचना होगा: कोई फ़ोन, खाता या वाहन साफ़ तौर पर दोनों का नहीं है।",
  "match.gate.single_tier": "अधिकारी को जाँचना होगा: सबूत सिर्फ़ एक तरह की जाँच से आया है।",
  "match.gate.hard_conflict": "अधिकारी को जाँचना होगा: कुछ सबूत मेल नहीं खाते।",
  "match.gate.low_extraction": "अधिकारी को जाँचना होगा: एक रिकॉर्ड पढ़ना मुश्किल था।",
  "match.gate.cluster_conflict":
    "अधिकारी को जाँचना होगा: इससे ऐसे रिकॉर्ड जुड़ सकते हैं जो साथ के नहीं हैं।",
  "match.gate.cluster_bridge":
    "अधिकारी को जाँचना होगा: इससे ऐसे रिकॉर्ड जुड़ सकते हैं जो साथ के नहीं हैं।",
  "match.gate.cluster_same_case":
    "अधिकारी को जाँचना होगा: इससे ऐसे रिकॉर्ड जुड़ सकते हैं जो साथ के नहीं हैं।",
  "match.gate.org_review_only": "संस्थाओं के लिंक को हमेशा अधिकारी को जाँचना होता है।",

  "match.adjust.cap": "अंक घटाए गए: इस तरह की जाँच अपनी सीमा तक पहुँच गई है।",
  "match.adjust.clamp": "अंक 0 और 100 के बीच रखने के लिए बदले गए।",
  "match.modifier.trap_identifier":
    "यह {id_label} एक से ज़्यादा लोग इस्तेमाल करते हैं, इसलिए इसका वज़न कम है।",
};
