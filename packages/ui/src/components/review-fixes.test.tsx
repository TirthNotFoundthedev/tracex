import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import schemaSource from "../../../../contracts/explanation.schema.json?raw";
import {
  ConfirmStep,
  RestrictedCard,
  UiProvider,
  en,
  hi,
  type Language,
  type RestrictedCardProps,
} from "../index";

afterEach(cleanup);

function ui(node: React.ReactNode, lang: Language = "en") {
  return render(<UiProvider lang={lang}>{node}</UiProvider>);
}

describe("RestrictedCard states (design-flows O9)", () => {
  test("refused: says access was not given and offers Ask again as the primary button", () => {
    const onAskAgain = vi.fn();
    const { container } = ui(
      <RestrictedCard
        itemType="phone"
        itemValue="98xxxx1234"
        refused={{ note: "Please add the FIR number." }}
        onAskAgain={onAskAgain}
      />,
    );
    expect(screen.getByText("Access was not given.")).toBeTruthy();
    expect(screen.getByText(/Please add the FIR number\./)).toBeTruthy();
    const again = screen.getByRole("button", { name: "Ask again" });
    expect(again.getAttribute("data-variant")).toBe("primary");
    expect(container.querySelectorAll('[data-variant="primary"]')).toHaveLength(1);
    fireEvent.click(again);
    expect(onAskAgain).toHaveBeenCalled();
  });

  test("refused without a note shows no note line", () => {
    ui(
      <RestrictedCard itemType="person" itemValue="A. Kumar" refused={{}} onAskAgain={() => {}} />,
    );
    expect(screen.getByText("Access was not given.")).toBeTruthy();
    expect(screen.queryByText(/Reason given/)).toBeNull();
    cleanup();
    ui(<RestrictedCard itemType="person" itemValue="A. Kumar" refused={{ note: "   " }} />);
    expect(screen.queryByText(/Reason given/)).toBeNull();
  });

  test("shows You cannot see that case in every state", () => {
    ui(<RestrictedCard itemType="phone" itemValue="1" onAskForAccess={() => {}} />);
    expect(screen.getByText("You cannot see that case.")).toBeTruthy();
    cleanup();
    ui(<RestrictedCard itemType="phone" itemValue="1" requestedOn="12 Mar 2026" />);
    expect(screen.getByText("You cannot see that case.")).toBeTruthy();
    cleanup();
    ui(<RestrictedCard itemType="phone" itemValue="1" refused={{}} />);
    expect(screen.getByText("You cannot see that case.")).toBeTruthy();
  });

  test("Ask for access is the one primary button", () => {
    const { container } = ui(
      <RestrictedCard itemType="vehicle" itemValue="UP32 AB 1234" onAskForAccess={() => {}} />,
    );
    expect(
      screen.getByRole("button", { name: "Ask for access" }).getAttribute("data-variant"),
    ).toBe("primary");
    expect(container.querySelectorAll('[data-variant="primary"]')).toHaveLength(1);
  });

  test("the refused state still has no slot for case data", () => {
    // @ts-expect-error refused takes only a note, nothing about the other case
    const refused: RestrictedCardProps["refused"] = { caseNumber: "24/118" };
    const bad = <RestrictedCard itemType="person" itemValue="A" refused={refused} />;
    ui(bad);
    expect(screen.queryByText(/24\/118/)).toBeNull();
  });

  test("refused state reads in Hindi", () => {
    ui(<RestrictedCard itemType="phone" itemValue="1" refused={{}} onAskAgain={() => {}} />, "hi");
    expect(screen.getByText(hi["restricted.refused"])).toBeTruthy();
    expect(screen.getByRole("button", { name: hi["restricted.askAgain"] })).toBeTruthy();
  });
});

describe("ConfirmStep safe choice (design-flows O7)", () => {
  test("with a danger confirm, No go back is primary and comes first", () => {
    const { container } = ui(
      <ConfirmStep
        title="Reject this link?"
        confirmLabel="Yes, reject"
        confirmVariant="danger"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((node) => node.textContent)).toEqual(["No, go back", "Yes, reject"]);
    expect(buttons[0]?.getAttribute("data-variant")).toBe("primary");
    expect(buttons[1]?.getAttribute("data-variant")).toBe("danger");
    expect(container.querySelectorAll('[data-variant="primary"]')).toHaveLength(1);
  });

  test("cancelVariant can be set by the caller", () => {
    ui(
      <ConfirmStep
        title="Reject this link?"
        confirmLabel="Yes, reject"
        confirmVariant="danger"
        cancelVariant="secondary"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "No, go back" }).getAttribute("data-variant")).toBe(
      "secondary",
    );
  });

  test("with a primary confirm the cancel stays secondary and second", () => {
    ui(
      <ConfirmStep
        title="Undo this link?"
        confirmLabel="Yes, undo"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((node) => node.textContent)).toEqual(["Yes, undo", "No, go back"]);
    expect(buttons[1]?.getAttribute("data-variant")).toBe("secondary");
  });
});

describe("shared strings", () => {
  test("role labels exist in English and Hindi", () => {
    const roles = ["junior", "investigator", "supervisor", "senior", "admin"] as const;
    expect(roles.map((role) => en[`role.${role}`])).toEqual([
      "Officer",
      "Investigating officer",
      "Supervisor",
      "Senior officer",
      "Administrator",
    ]);
    for (const role of roles) expect(hi[`role.${role}`].trim()).not.toBe("");
  });

  test("every template_key in the explanation schema has text in both languages", () => {
    const keys = new Set(
      schemaSource.match(/match\.(?:evidence|gate|adjust|modifier)\.[a-z_]+/g) ?? [],
    );
    expect(keys.size).toBeGreaterThan(30);
    const missing = [...keys].filter((key) => !(key in en) || !(key in hi));
    expect(missing).toEqual([]);
  });

  test("attribution and id label codes from the schema have text in both languages", () => {
    for (const code of ["owns", "registered_to", "mentioned_with"]) {
      expect(`match.attribution.${code}` in en && `match.attribution.${code}` in hi).toBe(true);
    }
    for (const code of ["phone", "account", "vehicle"]) {
      expect(`match.id_label.${code}` in en && `match.id_label.${code}` in hi).toBe(true);
    }
  });

  test("placeholders match between English and Hindi for every key", () => {
    const slots = (text: string) =>
      [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
    for (const key of Object.keys(en) as Array<keyof typeof en>) {
      expect(slots(hi[key]), key).toEqual(slots(en[key]));
    }
  });

  test("access.stub.connection_exists is the line the restricted card shows", () => {
    expect(en["access.stub.connection_exists"]).toBe(
      "Also appears in a case in another police area.",
    );
    ui(<RestrictedCard itemType="phone" itemValue="1" onAskForAccess={() => {}} />);
    expect(screen.getByText(en["access.stub.connection_exists"])).toBeTruthy();
  });

  test("reason hint and short-reason error say characters, not letters", () => {
    expect(en["confirm.reasonHint"]).toBe("Between {min} and {max} characters.");
    expect(en["field.tooShort"]).toBe("Please write a little more: at least {min} characters.");
    expect(en["confirm.reasonHint"]).not.toMatch(/letters/);
    expect(en["field.tooShort"]).not.toMatch(/letters/);
  });
});
