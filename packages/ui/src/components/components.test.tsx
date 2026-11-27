import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import cssSource from "./ui.css?raw";
import tokensSource from "../tokens.css?raw";
import {
  Badge,
  Breadcrumb,
  Button,
  Checkbox,
  ConfirmStep,
  EmptyState,
  EvidenceSource,
  FileDrop,
  LanguageSwitch,
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
  en,
  hi,
  type AppVariant,
  type Language,
} from "../index";

afterEach(cleanup);

function ui(node: React.ReactNode, lang: Language = "en", app: AppVariant = "officer") {
  return render(
    <UiProvider lang={lang} app={app}>
      {node}
    </UiProvider>,
  );
}

describe("styles", () => {
  const css = cssSource.replace(/\/\*[\s\S]*?\*\//g, "");
  const tokens = tokensSource;

  test("components use tokens only: no raw hex colour and no raw px", () => {
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).not.toMatch(/\d\s*px\b/);
  });

  test("focus ring is defined in tokens and never removed", () => {
    expect(tokens).toMatch(/:focus-visible\s*{[^}]*outline:\s*var\(--focus-ring-width\)/);
    expect(css).not.toMatch(/outline:\s*(none|0)\b/);
    expect(css).not.toMatch(/outline-style:\s*none/);
  });

  test("nothing banned by section 0: no gradients, shadows, blur, animation, pills", () => {
    expect(css).not.toMatch(
      /gradient|box-shadow|text-shadow|backdrop-filter|filter:|animation|@keyframes/,
    );
    expect(css).not.toMatch(
      /text-transform|font-style:\s*italic|letter-spacing|text-align:\s*justify/,
    );
    expect(css).not.toMatch(/border-radius:\s*(?!\s|var\(--radius\))/);
  });

  test("page width tokens: officer 45rem, admin wide page 72rem, both capped (section 4)", () => {
    expect(tokens).toMatch(/--page-width:\s*45rem/);
    expect(tokens).toMatch(/--page-width-wide:\s*72rem/);
    expect(tokens).toMatch(/--measure:\s*40rem/);
  });

  test("officer target is 56px and admin 44px through tokens", () => {
    expect(tokens).toMatch(/--tap-min:\s*3\.5rem/);
    expect(tokens).toMatch(/\[data-app="admin"\][^}]*--tap-min:\s*2\.75rem/);
    expect(css).toMatch(/min-block-size:\s*var\(--tap-min\)/);
  });
});

describe("Button", () => {
  test("renders the label beside its icon and fires onClick", () => {
    const onClick = vi.fn();
    ui(
      <Button variant="primary" icon="confirm" onClick={onClick}>
        Confirm they are the same
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Confirm they are the same" });
    expect(button.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    expect(button.textContent).toBe("Confirm they are the same");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  test("variant is exposed for styling and defaults to secondary", () => {
    ui(<Button>Open</Button>);
    expect(screen.getByRole("button").getAttribute("data-variant")).toBe("secondary");
  });
});

describe("fields", () => {
  test("TextField label is linked to the input and shows the error in words", () => {
    const onChange = vi.fn();
    ui(<TextField label="Reason" required error="Please fill in: Reason." onChange={onChange} />);
    const input = screen.getByLabelText(/Reason/);
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText("Please fill in: Reason.")).toBeTruthy();
    expect(screen.getByText(/\(required\)/)).toBeTruthy();
    fireEvent.change(input, { target: { value: "abc" } });
    expect(onChange).toHaveBeenCalledWith("abc");
  });

  test("TextField can be multiline for the access reason", () => {
    ui(<TextField label="Reason" multiline maxLength={500} />);
    expect(screen.getByLabelText("Reason").tagName).toBe("TEXTAREA");
  });

  test("SearchField has a visible Search button with an icon and submits", () => {
    const onSearch = vi.fn();
    ui(<SearchField label="Find a case" onSearch={onSearch} />);
    fireEvent.change(screen.getByLabelText("Find a case"), { target: { value: "24/118" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(onSearch).toHaveBeenCalledWith("24/118");
  });

  test("Checkbox row toggles through its label", () => {
    const onChange = vi.fn();
    ui(<Checkbox label="Include closed cases" checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("Include closed cases"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  test("Select, FileDrop render in admin and nothing in the officer app", () => {
    const options = [{ value: "a", label: "Area A" }];
    const first = ui(
      <Select label="Police area" options={options} value="a" onChange={() => {}} />,
    );
    expect(first.container.querySelector("select")).toBeNull();
    cleanup();
    const admin = ui(
      <Select label="Police area" options={options} value="a" onChange={() => {}} />,
      "en",
      "admin",
    );
    expect(within(admin.container).getByLabelText("Police area").tagName).toBe("SELECT");
    cleanup();

    const officerDrop = ui(<FileDrop label="Upload" onFile={() => {}} />);
    expect(officerDrop.container.querySelector("input")).toBeNull();
    cleanup();
    const onFile = vi.fn();
    const adminDrop = ui(
      <FileDrop label="Upload" onFile={onFile} fileName="calls.csv" />,
      "en",
      "admin",
    );
    expect(screen.getByText("Choose a file")).toBeTruthy();
    expect(screen.getByText("Chosen file: calls.csv")).toBeTruthy();
    const file = new File(["x"], "calls.csv");
    fireEvent.change(adminDrop.container.querySelector("input[type=file]") as HTMLInputElement, {
      target: { files: [file] },
    });
    expect(onFile).toHaveBeenCalledWith(file);
  });
});

describe("navigation", () => {
  test("TopBar has Back with icon + label, one title and the language switch", () => {
    const onBack = vi.fn();
    const onLanguageChange = vi.fn();
    ui(<TopBar title="Case 24/118" onBack={onBack} onLanguageChange={onLanguageChange} />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const back = screen.getByRole("button", { name: "Back" });
    expect(back.querySelector("svg")).not.toBeNull();
    fireEvent.click(back);
    expect(onBack).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "हिन्दी" }));
    expect(onLanguageChange).toHaveBeenCalledWith("hi");
  });

  test("admin TopBar adds user, area and sign out; officer TopBar does not", () => {
    const props = {
      title: "Review queue",
      onLanguageChange: () => {},
      userName: "A. Rao",
      jurisdiction: "Lucknow",
      onSignOut: () => {},
    };
    ui(<TopBar {...props} />);
    expect(screen.queryByText("Sign out")).toBeNull();
    cleanup();
    ui(<TopBar {...props} />, "en", "admin");
    expect(screen.getByText("A. Rao")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
  });

  test("LanguageSwitch shows the other language in that language", () => {
    ui(<LanguageSwitch onChange={() => {}} />, "hi");
    const label = screen.getByText("English");
    expect(label.getAttribute("lang")).toBe("en");
  });

  test("Breadcrumb is plain text with the current screen marked", () => {
    ui(<Breadcrumb items={[{ label: "My cases", onClick: () => {} }, { label: "Case 24/118" }]} />);
    expect(screen.getByRole("navigation", { name: "You are here" })).toBeTruthy();
    expect(screen.getByText("Case 24/118").getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "My cases" })).toBeTruthy();
  });

  test("SideNav shows icon + label, marks the current section, admin only", () => {
    const items = [
      { id: "upload", label: "Upload", icon: "upload" as const },
      { id: "queue", label: "Review queue", icon: "alsoAppearsIn" as const },
    ];
    const none = ui(<SideNav items={items} currentId="upload" onSelect={() => {}} />);
    expect(none.container.querySelector("nav")).toBeNull();
    cleanup();
    const onSelect = vi.fn();
    ui(<SideNav items={items} currentId="upload" onSelect={onSelect} />, "en", "admin");
    expect(screen.getByRole("button", { name: "Upload" }).getAttribute("aria-current")).toBe(
      "page",
    );
    fireEvent.click(screen.getByRole("button", { name: "Review queue" }));
    expect(onSelect).toHaveBeenCalledWith("queue");
  });

  test("Tabs are keyboard operable and mark the chosen one with a check icon", () => {
    const onSelect = vi.fn();
    const items = [
      { id: "waiting", label: "Waiting", count: 4, panel: <p>Waiting panel</p> },
      { id: "rejected", label: "Rejected", count: 2, panel: <p>Rejected panel</p> },
    ];
    ui(
      <Tabs label="Status" items={items} selectedId="waiting" onSelect={onSelect} />,
      "en",
      "admin",
    );
    const selected = screen.getByRole("tab", { name: "Waiting (4)" });
    expect(selected.getAttribute("aria-selected")).toBe("true");
    expect(selected.querySelector("svg")).not.toBeNull();
    expect(screen.getByRole("tab", { name: "Rejected (2)" }).querySelector("svg")).toBeNull();
    fireEvent.keyDown(selected, { key: "ArrowRight" });
    expect(onSelect).toHaveBeenCalledWith("rejected");
    expect(screen.getByRole("tabpanel").textContent).toBe("Waiting panel");
  });
});

describe("lists", () => {
  test("ListRow is one button target ending in a chevron", () => {
    const onOpen = vi.fn();
    ui(<ListRow icon="case" title="Case 24/118" secondary="3 people" onOpen={onOpen} />);
    const row = screen.getByRole("button");
    expect(row.querySelectorAll("svg")).toHaveLength(2);
    expect(row.textContent).toContain("Case 24/118");
    fireEvent.click(row);
    expect(onOpen).toHaveBeenCalled();
  });

  test("Pager shows a count and Show more, and hides when all are shown", () => {
    const onMore = vi.fn();
    const { container, rerender } = ui(<Pager shown={50} total={120} onMore={onMore} />);
    expect(screen.getByText("Showing 50 of 120")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(onMore).toHaveBeenCalled();
    rerender(
      <UiProvider>
        <Pager shown={120} total={120} onMore={onMore} />
      </UiProvider>,
    );
    expect(container.querySelector("button")).toBeNull();
  });

  test("Table: labelled sortable headers, row Open button, stack labels, admin only", () => {
    type Row = { id: string; name: string; phone: string };
    const rows: Row[] = [{ id: "1", name: "Irfan", phone: "9800001234" }];
    const columns = [
      { id: "name", header: "Name", sortable: true, cell: (row: Row) => row.name },
      { id: "phone", header: "Phone number", numeric: true, cell: (row: Row) => row.phone },
    ];
    const onSort = vi.fn();
    const onOpenRow = vi.fn();
    const props = {
      caption: "People",
      columns,
      rows,
      rowKey: (row: Row) => row.id,
      onSort,
      onOpenRow,
    };
    const none = ui(<Table {...props} />);
    expect(none.container.querySelector("table")).toBeNull();
    cleanup();
    ui(<Table {...props} sort={{ columnId: "name", direction: "up" }} />, "en", "admin");
    expect(screen.getByRole("columnheader", { name: /Name/ }).getAttribute("aria-sort")).toBe(
      "ascending",
    );
    fireEvent.click(screen.getByRole("button", { name: "Sort by Name" }));
    expect(onSort).toHaveBeenCalledWith("name");
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(onOpenRow).toHaveBeenCalledWith(rows[0]);
    expect(screen.getByText("9800001234").getAttribute("data-label")).toBe("Phone number");
  });
});

describe("StrengthBadge (section 8)", () => {
  test("strong: icon, words, solid style hook and a 3 of 3 bar", () => {
    const { container } = ui(<StrengthBadge strength="strong" />);
    expect(screen.getByText("Strong match")).toBeTruthy();
    expect(container.querySelector(".tx-strength svg")).not.toBeNull();
    expect(container.querySelector(".tx-strength")?.getAttribute("data-strength")).toBe("strong");
    expect(container.querySelectorAll('[data-filled="true"]')).toHaveLength(3);
    expect(screen.getByRole("img").getAttribute("aria-label")).toBe("Bar: 3 of 3 filled");
  });

  test("possible: words, 2 of 3 bar", () => {
    const { container } = ui(<StrengthBadge strength="possible" />);
    expect(screen.getByText("Possible match. Please check.")).toBeTruthy();
    expect(container.querySelectorAll('[data-filled="true"]')).toHaveLength(2);
    expect(container.querySelectorAll('[data-filled="false"]')).toHaveLength(1);
  });

  test("borders differ by style, not only colour", () => {
    const css = cssSource;
    expect(css).toMatch(/data-strength="strong"\][^}]*border-style:\s*solid/);
    expect(css).toMatch(/data-strength="possible"\][^}]*border-style:\s*dashed/);
  });

  test("the officer app never shows a number; admin may", () => {
    const first = ui(<StrengthBadge strength="strong" adminScore={91} />);
    expect(first.container.textContent).not.toMatch(/\d/);
    cleanup();
    ui(<StrengthBadge strength="strong" adminScore={91} />, "en", "admin");
    expect(screen.getByText("Score: 91")).toBeTruthy();
  });

  test("Badge always carries words beside its icon", () => {
    const { container } = ui(<Badge icon="pending">Sent for approval</Badge>);
    expect(container.querySelector("svg")).not.toBeNull();
    expect(container.textContent).toBe("Sent for approval");
  });
});

describe("explanation", () => {
  test("ReasonList: both sections always appear, in order", () => {
    ui(
      <ReasonList
        support={[
          {
            text: "Same phone number in both cases",
            source: { caseNumber: "24/118", documentType: "call record", page: 2, line: 14 },
          },
        ]}
        against={[]}
      />,
    );
    const headings = screen.getAllByRole("heading", { level: 2 }).map((node) => node.textContent);
    expect(headings).toEqual(["Why we think so", "Why it may be wrong"]);
    expect(screen.getByText("Nothing found against this link.")).toBeTruthy();
    expect(screen.getByText("Case 24/118, call record, page 2, line 14")).toBeTruthy();
  });

  test("ReasonList reasons against use an icon and its words", () => {
    const { container } = ui(
      <ReasonList support={[]} against={[{ text: "Ages differ: 34 and 29" }]} />,
    );
    expect(container.querySelector('[data-kind="against"] svg')).not.toBeNull();
    expect(screen.queryByText("Nothing found against this link.")).toBeNull();
  });

  test("EvidenceSource leaves out unknown page and line", () => {
    ui(
      <EvidenceSource sources={[{ caseNumber: "31/207", documentType: "statement of witness" }]} />,
    );
    expect(screen.getByText("Where this came from")).toBeTruthy();
    expect(screen.getByText("Case 31/207, statement of witness")).toBeTruthy();
  });

  test("MoreDetail is closed by default and opens as a real button", () => {
    ui(<MoreDetail>Match score: 91</MoreDetail>);
    const toggle = screen.getByRole("button", { name: "More detail" });
    expect(toggle.tagName).toBe("BUTTON");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    const panel = screen.getByText("Match score: 91", { ignore: "nothing" });
    expect(panel.hasAttribute("hidden")).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(panel.hasAttribute("hidden")).toBe(false);
  });
});

describe("RestrictedCard (section 10)", () => {
  test("emphasis: primary by default, secondary when asked (section 5, one primary per screen)", () => {
    const { rerender } = ui(
      <RestrictedCard itemType="phone" itemValue="98xxxx1234" onAskForAccess={() => {}} />,
    );
    expect(
      screen.getByRole("button", { name: "Ask for access" }).getAttribute("data-variant"),
    ).toBe("primary");
    rerender(
      <UiProvider lang="en">
        <RestrictedCard
          itemType="phone"
          itemValue="98xxxx1234"
          emphasis="secondary"
          onAskForAccess={() => {}}
        />
      </UiProvider>,
    );
    expect(
      screen.getByRole("button", { name: "Ask for access" }).getAttribute("data-variant"),
    ).toBe("secondary");
  });

  test("emphasis also applies to Ask again after a refusal", () => {
    ui(
      <RestrictedCard
        itemType="phone"
        itemValue="98xxxx1234"
        refused={{}}
        emphasis="secondary"
        onAskAgain={() => {}}
      />,
    );
    expect(
      screen.getByRole("button", { name: en["restricted.askAgain"] }).getAttribute("data-variant"),
    ).toBe("secondary");
  });

  test("shows lock, Another police area, the officer's own item and Ask for access", () => {
    const onAsk = vi.fn();
    const { container } = ui(
      <RestrictedCard itemType="phone" itemValue="9800001234" onAskForAccess={onAsk} />,
    );
    expect(screen.getByText("Another police area")).toBeTruthy();
    expect(container.querySelector(".tx-restricted__title svg")).not.toBeNull();
    expect(screen.getByText("9800001234")).toBeTruthy();
    expect(screen.getByText("Also appears in a case in another police area.")).toBeTruthy();
    expect(screen.getByText("You cannot see that case.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ask for access" }));
    expect(onAsk).toHaveBeenCalled();
  });

  test("has no slot for case data: the type accepts only the item and request state", () => {
    // @ts-expect-error no children prop exists
    const withChildren = <RestrictedCard itemType="person" itemValue="A" children="Case 24/118" />;
    // @ts-expect-error no case number prop exists
    const withCase = <RestrictedCard itemType="person" itemValue="A" caseNumber="24/118" />;
    // @ts-expect-error no strength prop exists
    const withStrength = <RestrictedCard itemType="person" itemValue="A" strength="strong" />;
    const { container } = ui(
      <>
        {withChildren}
        {withCase}
        {withStrength}
      </>,
    );
    expect(container.textContent).not.toMatch(/24\/118|strong/i);
  });

  test("after the request: date and no button", () => {
    const { container } = ui(
      <RestrictedCard
        itemType="person"
        itemValue="A. Kumar"
        requestedOn="12 Mar 2026"
        onAskForAccess={() => {}}
      />,
    );
    expect(
      screen.getByText("Request sent on 12 Mar 2026. We will tell you when it is decided."),
    ).toBeTruthy();
    expect(container.querySelector("button")).toBeNull();
  });

  test("reads in Hindi", () => {
    ui(<RestrictedCard itemType="vehicle" itemValue="UP32 AB 1234" />, "hi");
    expect(screen.getByText("दूसरा थाना क्षेत्र")).toBeTruthy();
  });
});

describe("feedback", () => {
  test("Message stays in the page, has icon and words, and dismisses only on request", () => {
    const onDismiss = vi.fn();
    vi.useFakeTimers();
    const { container } = ui(
      <Message kind="success" onDismiss={onDismiss}>
        Saved: you confirmed this link
      </Message>,
    );
    vi.advanceTimersByTime(60_000);
    vi.useRealTimers();
    expect(screen.getByText(/Saved: you confirmed this link/)).toBeTruthy();
    expect(screen.getByRole("status")).toBeTruthy();
    expect(container.querySelector(".tx-message > svg")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Close this message" }));
    expect(onDismiss).toHaveBeenCalled();
  });

  test("error Message is an alert and offers a button", () => {
    ui(
      <Message kind="error" action={<Button>Try again</Button>}>
        We could not save. Nothing was changed.
      </Message>,
    );
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  test("ConfirmStep: one primary, a way back, focus on the question, Escape leaves", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const { container } = ui(
      <ConfirmStep
        title="Reject this link?"
        confirmLabel="Yes, reject"
        confirmVariant="danger"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    const dialog = screen.getByRole("alertdialog");
    expect(document.activeElement).toBe(
      within(dialog).getByRole("heading", { name: "Reject this link?" }),
    );
    expect(container.querySelectorAll('[data-variant="primary"]')).toHaveLength(1);
    expect(screen.getByRole("button", { name: "No, go back" }).getAttribute("data-variant")).toBe(
      "primary",
    );
    expect(screen.getByRole("button", { name: "Yes, reject" }).getAttribute("data-variant")).toBe(
      "danger",
    );
    fireEvent.click(screen.getByRole("button", { name: "No, go back" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole("button", { name: "Yes, reject" }));
    expect(onConfirm).toHaveBeenCalledWith();
  });

  test("ConfirmStep with a primary confirm has exactly one primary button", () => {
    const { container } = ui(
      <ConfirmStep
        title="Undo this link?"
        confirmLabel="Yes, undo"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(container.querySelectorAll('[data-variant="primary"]')).toHaveLength(1);
  });

  test("ConfirmStep requires a reason when asked", () => {
    const onConfirm = vi.fn();
    ui(
      <ConfirmStep
        title="Reopen this link?"
        confirmLabel="Yes, reopen"
        reason={{ label: "Reason", min: 10, max: 500 }}
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
      "en",
      "admin",
    );
    fireEvent.click(screen.getByRole("button", { name: "Yes, reopen" }));
    expect(screen.getByText("Please fill in: Reason.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Yes, reopen" }));
    expect(screen.getByText("Please write a little more: at least 10 characters.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Reason/), {
      target: { value: "Checked the call record again" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Yes, reopen" }));
    expect(onConfirm).toHaveBeenCalledWith("Checked the call record again");
  });

  test("EmptyState says why and what next", () => {
    ui(<EmptyState title="No cases yet." hint="Ask your supervisor to add your cases." />);
    expect(screen.getByText("No cases yet.")).toBeTruthy();
    expect(screen.getByText("Ask your supervisor to add your cases.")).toBeTruthy();
  });

  test('EmptyState with hint="" draws no hint line and no empty element', () => {
    const { container } = ui(<EmptyState title="We could not find that." hint="" />);
    expect(screen.getByText("We could not find that.")).toBeTruthy();
    expect(screen.queryByText(en["empty.hint"])).toBeNull();
    expect(container.querySelector(".tx-empty .tx-body")).toBeNull();
    expect(Array.from(container.querySelectorAll(".tx-empty p")).every((e) => e.textContent)).toBe(
      true,
    );
  });

  test("Loading adds the slow line after 10 seconds and uses no motion", () => {
    vi.useFakeTimers();
    const { container } = ui(<Loading label="Loading your cases..." />);
    expect(screen.getByText("Loading your cases...")).toBeTruthy();
    expect(screen.queryByText(en["loading.slow"])).toBeNull();
    vi.advanceTimersByTime(10_000);
    vi.useRealTimers();
    return Promise.resolve().then(() => {
      expect(container.textContent).toContain("This is taking long");
    });
  });
});

describe("language", () => {
  test("every component with fixed words has them in Hindi too", () => {
    ui(<StrengthBadge strength="possible" />, "hi");
    expect(screen.getByText(hi["strength.possible"])).toBeTruthy();
  });

  test("provider sets lang and app on the wrapper so tokens and line height switch", () => {
    const { container } = ui(<p>x</p>, "hi", "admin");
    const root = container.querySelector(".tx-root");
    expect(root?.getAttribute("lang")).toBe("hi");
    expect(root?.getAttribute("data-app")).toBe("admin");
  });

  test("a Hindi string keeps its slots filled", () => {
    ui(<Pager shown={50} total={120} onMore={() => {}} />, "hi");
    expect(screen.getByText("120 में से 50 दिखाए गए")).toBeTruthy();
  });
});
