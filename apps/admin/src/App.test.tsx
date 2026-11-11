import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { App } from "./App";

test("renders the title in English and Hindi", () => {
  const { rerender } = render(<App />);
  expect(screen.getByRole("heading").textContent).toBe("TraceX Admin");

  rerender(<App lang="hi" />);
  expect(screen.getByRole("heading").textContent).toBe("ट्रेसएक्स एडमिन");
});
