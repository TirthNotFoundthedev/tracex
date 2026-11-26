import { createRoot } from "react-dom/client";
import { useState, type ReactNode } from "react";

import {
  Badge,
  Breadcrumb,
  Button,
  Checkbox,
  ConfirmStep,
  EmptyState,
  EvidenceSource,
  FileDrop,
  ListRow,
  Loading,
  Message,
  MoreDetail,
  Pager,
  ReasonList,
  RestrictedCard,
  SearchField,
  Select,
  SideNav,
  StrengthBadge,
  Table,
  Tabs,
  TextField,
  TopBar,
  UiProvider,
  type AppVariant,
  type Language,
} from "../src";

/*
 * Gallery of every shared component with the longest real strings, for design review
 * (DESIGN_RULES section 15). Sample content below is demo data, not product strings:
 * product strings live in the i18n files. Use ?app=officer|admin&lang=en|hi.
 */

interface Copy {
  title: string;
  crumbs: [string, string];
  primary: string;
  secondary: string;
  reject: string;
  longest: string;
  searchLabel: string;
  reasonLabel: string;
  rowTitle: string;
  rowSecondary: string;
  reasonsFor: string[];
  reasonAgainst: string;
  docType: string;
  detailBody: string;
  saved: string;
  failed: string;
  tryAgain: string;
  note: string;
  rejectTitle: string;
  rejectBody: string;
  rejectYes: string;
  emptyTitle: string;
  emptyHint: string;
  loadingLabel: string;
  adminReason: string;
  pending: string;
  sections: [string, string, string, string];
  cols: [string, string, string];
  tabs: [string, string, string];
  area: string;
  upload: string;
  include: string;
  name: string;
}

const copy: Record<Language, Copy> = {
  en: {
    title: "Link between two cases",
    crumbs: ["My cases", "Case 24/118"],
    primary: "Confirm they are the same",
    secondary: "Show where it appears",
    reject: "Reject this link",
    longest: "Send a request for access to the other police area",
    searchLabel: "Find a case by number or name",
    reasonLabel: "Reason for the request",
    rowTitle: "Case 24/118",
    rowSecondary: "3 people, 2 phone numbers, 1 bank account",
    reasonsFor: [
      "Same phone number in both cases",
      "Names sound alike: Mohd. Irfan / Irfan",
      "Both called the same 2 numbers",
    ],
    reasonAgainst: "Ages differ: 34 and 29",
    docType: "call record",
    detailBody: "Match score: 91 (out of 100). Strong match starts at 80.",
    saved: "Saved: you confirmed this link.",
    failed: "We could not save. Nothing was changed.",
    tryAgain: "Try again",
    note: "You can look at this link but not decide it. Ask your investigating officer or supervisor.",
    rejectTitle: "Reject this link?",
    rejectBody: "The two items will not be shown as the same. Only an administrator can reopen it.",
    rejectYes: "Yes, reject",
    emptyTitle: "No cases yet.",
    emptyHint: "Ask your supervisor to add your cases.",
    loadingLabel: "Loading your cases...",
    adminReason: "Reason for reopening",
    pending: "Sent for approval",
    sections: ["Upload", "Matching", "Review queue", "Audit log"],
    cols: ["Case", "Phone number", "Link strength"],
    tabs: ["Waiting", "Rejected", "Undone"],
    area: "Police area",
    upload: "Upload a call record",
    include: "Include closed cases",
    name: "Irfan Khan",
  },
  hi: {
    title: "दो मामलों के बीच लिंक",
    crumbs: ["मेरे मामले", "मामला 24/118"],
    primary: "पुष्टि करें कि यह वही है",
    secondary: "देखें कि यह कहाँ-कहाँ आया है",
    reject: "इस लिंक को अस्वीकार करें",
    longest: "दूसरे थाना क्षेत्र के लिए पहुँच का अनुरोध भेजें",
    searchLabel: "मामला नंबर या नाम से मामला खोजें",
    reasonLabel: "अनुरोध का कारण",
    rowTitle: "मामला 24/118",
    rowSecondary: "3 व्यक्ति, 2 फ़ोन नंबर, 1 बैंक खाता",
    reasonsFor: [
      "दोनों मामलों में एक ही फ़ोन नंबर",
      "नाम मिलते-जुलते हैं: मोहम्मद इरफ़ान / इरफ़ान",
      "दोनों ने एक ही 2 नंबरों पर फ़ोन किया",
    ],
    reasonAgainst: "उम्र अलग है: 34 और 29",
    docType: "कॉल रिकॉर्ड",
    detailBody: "मिलान अंक: 91 (100 में से)। पक्का मिलान 80 से शुरू होता है।",
    saved: "सहेजा गया: आपने इस लिंक की पुष्टि की।",
    failed: "हम सहेज नहीं सके। कुछ भी नहीं बदला।",
    tryAgain: "दोबारा कोशिश करें",
    note: "आप यह लिंक देख सकते हैं, पर उस पर फ़ैसला नहीं कर सकते। अपने जाँच अधिकारी या पर्यवेक्षक से पूछें।",
    rejectTitle: "इस लिंक को अस्वीकार करें?",
    rejectBody: "दोनों चीज़ें एक जैसी नहीं दिखाई जाएँगी। इसे केवल प्रशासक दोबारा खोल सकता है।",
    rejectYes: "हाँ, अस्वीकार करें",
    emptyTitle: "अभी कोई मामला नहीं है।",
    emptyHint: "अपने पर्यवेक्षक से अपने मामले जोड़ने को कहें।",
    loadingLabel: "आपके मामले लोड हो रहे हैं...",
    adminReason: "दोबारा खोलने का कारण",
    pending: "मंज़ूरी के लिए भेजा गया",
    sections: ["अपलोड", "मिलान", "समीक्षा सूची", "ऑडिट लॉग"],
    cols: ["मामला", "फ़ोन नंबर", "लिंक की मज़बूती"],
    tabs: ["प्रतीक्षा में", "अस्वीकृत", "वापस लिए गए"],
    area: "थाना क्षेत्र",
    upload: "कॉल रिकॉर्ड अपलोड करें",
    include: "बंद मामले भी शामिल करें",
    name: "इरफ़ान ख़ान",
  },
};

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <p style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--color-ink-2)" }}>
        {title}
      </p>
      {children}
    </section>
  );
}

function Gallery({
  app,
  lang,
  setLang,
}: {
  app: AppVariant;
  lang: Language;
  setLang: (l: Language) => void;
}) {
  const c = copy[lang];
  const [tab, setTab] = useState("waiting");
  const [area, setArea] = useState("a");
  const [checked, setChecked] = useState(true);
  const [file, setFile] = useState<string>();
  const [sort, setSort] = useState<{ columnId: string; direction: "up" | "down" }>({
    columnId: "case",
    direction: "up",
  });
  const admin = app === "admin";
  const noop = () => {};
  const source = { caseNumber: "24/118", documentType: c.docType, page: 2, line: 14 };

  const rows = [
    { id: "1", a: "24/118", b: "98xxxx1234", s: "strong" as const },
    { id: "2", a: "31/207", b: "97xxxx5588", s: "possible" as const },
  ];

  return (
    <>
      <TopBar
        title={c.title}
        onBack={noop}
        onLanguageChange={setLang}
        {...(admin ? { userName: c.name, jurisdiction: c.area, onSignOut: noop } : {})}
      />
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          flexWrap: "wrap",
          background: "var(--color-sunken)",
        }}
      >
        {admin ? (
          <SideNav
            items={[
              { id: "upload", label: c.sections[0], icon: "upload" },
              { id: "match", label: c.sections[1], icon: "alsoAppearsIn" },
              { id: "queue", label: c.sections[2], icon: "case" },
              { id: "audit", label: c.sections[3], icon: "help" },
            ]}
            currentId="queue"
            onSelect={noop}
          />
        ) : null}
        <main
          style={{
            flex: "1 1 20rem",
            minInlineSize: 0,
            maxInlineSize: admin ? "none" : "var(--page-width)",
            marginInline: admin ? 0 : "auto",
            padding: "var(--space-4)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-6)",
            background: "var(--color-paper)",
          }}
        >
          <Block title="Breadcrumb, Button">
            <Breadcrumb items={[{ label: c.crumbs[0], onClick: noop }, { label: c.crumbs[1] }]} />
            <div className="tx-actions">
              <Button variant="primary" icon="confirm">
                {c.primary}
              </Button>
              <Button variant="danger" icon="reject">
                {c.reject}
              </Button>
              <Button variant="secondary" icon="alsoAppearsIn">
                {c.secondary}
              </Button>
            </div>
            <Button variant="secondary">{c.longest}</Button>
          </Block>

          <Block title="StrengthBadge, Badge">
            <StrengthBadge strength="strong" {...(admin ? { adminScore: 91 } : {})} />
            <StrengthBadge strength="possible" {...(admin ? { adminScore: 72 } : {})} />
            <Badge icon="pending">{c.pending}</Badge>
          </Block>

          <Block title="ReasonList, EvidenceSource, MoreDetail">
            <ReasonList
              support={c.reasonsFor.map((text) => ({ text, source }))}
              against={[{ text: c.reasonAgainst, source }]}
            />
            <ReasonList support={[]} against={[]} />
            <EvidenceSource sources={[source, { caseNumber: "31/207", documentType: c.docType }]} />
            <MoreDetail defaultOpen>
              <p>{c.detailBody}</p>
            </MoreDetail>
            <MoreDetail>
              <p>{c.detailBody}</p>
            </MoreDetail>
          </Block>

          <Block title="RestrictedCard">
            <RestrictedCard itemType="phone" itemValue="98xxxx1234" onAskForAccess={noop} />
            <RestrictedCard
              itemType="person"
              itemValue={c.name}
              requestedOn={lang === "en" ? "12 Mar 2026" : "12 मार्च 2026"}
            />
          </Block>

          <Block title="Message, ConfirmStep">
            <Message kind="success" onDismiss={noop}>
              {c.saved}
            </Message>
            <Message kind="info">{c.note}</Message>
            <Message kind="error" action={<Button variant="secondary">{c.tryAgain}</Button>}>
              {c.failed}
            </Message>
            <ConfirmStep
              title={c.rejectTitle}
              body={c.rejectBody}
              confirmLabel={c.rejectYes}
              confirmIcon="reject"
              confirmVariant="danger"
              onConfirm={noop}
              onCancel={noop}
            />
            {admin ? (
              <ConfirmStep
                title={c.rejectTitle}
                confirmLabel={c.rejectYes}
                reason={{ label: c.adminReason, min: 10, max: 500 }}
                onConfirm={noop}
                onCancel={noop}
              />
            ) : null}
          </Block>

          <Block title="TextField, SearchField, Checkbox, LanguageSwitch (in header)">
            <SearchField label={c.searchLabel} onSearch={noop} />
            <TextField label={c.reasonLabel} multiline required maxLength={500} />
            <TextField
              label={c.reasonLabel}
              required
              error={
                lang === "en"
                  ? "Please fill in: Reason for the request."
                  : "कृपया भरें: अनुरोध का कारण।"
              }
            />
            <Checkbox label={c.include} checked={checked} onChange={setChecked} />
          </Block>

          <Block title="ListRow, Pager, EmptyState, Loading">
            <div>
              <ListRow icon="case" title={c.rowTitle} secondary={c.rowSecondary} onOpen={noop} />
              <ListRow
                icon="phone"
                title="98xxxx1234"
                secondary={c.rowSecondary}
                badge={<StrengthBadge strength="possible" />}
                onOpen={noop}
              />
            </div>
            <Pager shown={50} total={120} onMore={noop} />
            <EmptyState title={c.emptyTitle} hint={c.emptyHint} />
            <Loading label={c.loadingLabel} slowAfterMs={0} />
          </Block>

          {admin ? (
            <Block title="Tabs, Table, Select, FileDrop (admin only)">
              <Tabs
                label={c.sections[2]}
                selectedId={tab}
                onSelect={setTab}
                items={[
                  { id: "waiting", label: c.tabs[0], count: 14, panel: <p>{c.tabs[0]}</p> },
                  { id: "rejected", label: c.tabs[1], count: 3, panel: <p>{c.tabs[1]}</p> },
                  { id: "undone", label: c.tabs[2], count: 1, panel: <p>{c.tabs[2]}</p> },
                ]}
              />
              <Table
                caption={c.sections[2]}
                rowKey={(row) => row.id}
                rows={rows}
                sort={sort}
                onSort={(columnId) =>
                  setSort((s) => ({ columnId, direction: s.direction === "up" ? "down" : "up" }))
                }
                onOpenRow={noop}
                columns={[
                  { id: "case", header: c.cols[0], sortable: true, cell: (row) => row.a },
                  { id: "phone", header: c.cols[1], numeric: true, cell: (row) => row.b },
                  {
                    id: "strength",
                    header: c.cols[2],
                    cell: (row) => (
                      <StrengthBadge strength={row.s} adminScore={row.s === "strong" ? 91 : 72} />
                    ),
                  },
                ]}
              />
              <Select
                label={c.area}
                value={area}
                onChange={setArea}
                options={[
                  { value: "a", label: c.area + " A" },
                  { value: "b", label: c.area + " B" },
                ]}
              />
              <FileDrop label={c.upload} fileName={file} onFile={(f) => setFile(f.name)} />
            </Block>
          ) : null}
        </main>
      </div>
    </>
  );
}

function App() {
  const params = new URLSearchParams(window.location.search);
  const app: AppVariant = params.get("app") === "admin" ? "admin" : "officer";
  const [lang, setLang] = useState<Language>(params.get("lang") === "hi" ? "hi" : "en");
  return (
    <UiProvider lang={lang} app={app}>
      <Gallery app={app} lang={lang} setLang={setLang} />
    </UiProvider>
  );
}

const admin = new URLSearchParams(window.location.search).get("app") === "admin";
const root = document.getElementById("root");
if (root) {
  createRoot(root).render(<App />);
  // Lets the screenshot script size the window and report the section 15 measurements.
  setTimeout(() => {
    const min = admin ? 44 : 56;
    const small: string[] = [];
    document
      .querySelectorAll(
        "button, select, input:not([type=file]):not([type=checkbox]), label.tx-button, textarea",
      )
      .forEach((node) => {
        const box = node.getBoundingClientRect();
        if (box.width < 3 || getComputedStyle(node).opacity === "0") return;
        if (box.height < min - 0.5) small.push(`${node.tagName}:${Math.round(box.height)}`);
      });
    let past = 0;
    document.querySelectorAll("main *").forEach((node) => {
      if (node.getBoundingClientRect().right > window.innerWidth + 0.5) past += 1;
    });
    document.title = `h=${document.documentElement.scrollHeight} w=${document.documentElement.scrollWidth} vw=${window.innerWidth} small=${small.length}[${small.slice(0, 5).join(",")}] past=${past}`;
  }, 1500);
}
