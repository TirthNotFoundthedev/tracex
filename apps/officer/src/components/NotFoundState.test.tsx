import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { NotFoundState } from "./NotFoundState";

afterEach(cleanup);

test.each([
  ["en", "We could not find this", "Back to my cases"],
  ["hi", "हमें यह नहीं मिला", "वापस"],
] as const)("not-found state in %s has text and a way back", (lang, text, back) => {
  const onBack = vi.fn();
  render(<NotFoundState lang={lang} onBack={onBack} />);
  expect(screen.getByRole("status").textContent).toContain(text);
  expect(screen.queryByText(/police area|पुलिस/i)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: new RegExp(back) }));
  expect(onBack).toHaveBeenCalledOnce();
});
