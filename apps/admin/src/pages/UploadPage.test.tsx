import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { t } from "../i18n";
import { DISTRICT, fakeApi, json, renderPage, type Routes } from "../testing";
import { UploadPage } from "./UploadPage";

afterEach(cleanup);

const places = json(200, {
  items: [
    {
      state_id: "s",
      name: "Rivergate State",
      districts: [{ district_id: DISTRICT, name: "Rivergate" }],
    },
  ],
});

function batch(over: Record<string, unknown> = {}) {
  return {
    batch_id: "11111111-1111-4111-8111-111111111111",
    file_name: "statement.pdf",
    file_sha256: "a".repeat(64),
    byte_count: 1200,
    status: "WAITING",
    created_at: "2026-03-12T14:05:00Z",
    ...over,
  };
}

function page(over: Routes = {}) {
  return fakeApi({
    "GET /jurisdictions": places,
    "GET /uploads": json(200, { items: [], next_cursor: null }),
    ...over,
  });
}

function pick(name = "notes.pdf") {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["x"], name, { type: "application/pdf" });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

async function ready() {
  await screen.findByRole("option", { name: "Rivergate" });
}

function fillCase(value = "31/207") {
  fireEvent.change(screen.getByLabelText("Case"), { target: { value } });
  fireEvent.change(screen.getByLabelText("Police area"), { target: { value: DISTRICT } });
}

test("shows the title, the accepted types in words and an empty list", async () => {
  const { api } = page();
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  expect(screen.getByText("PDF, Word, Excel, text, images")).toBeTruthy();
  expect(await screen.findByText("No files uploaded yet.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Upload files" })).toBeTruthy();
});

test("lists earlier uploads with their status in words and a reason for a failed one", async () => {
  const { api } = page({
    "GET /uploads": json(200, {
      items: [
        batch(),
        batch({ batch_id: "2", file_name: "log.xlsx", status: "READING" }),
        batch({ batch_id: "3", file_name: "scan.png", status: "DONE", document_count: 2 }),
        batch({
          batch_id: "4",
          file_name: "bad.doc",
          status: "FAILED",
          error_code: "INGEST_ERROR",
        }),
      ],
      next_cursor: null,
    }),
  });
  renderPage(<UploadPage api={api} lang="en" />);
  expect(await screen.findByText("statement.pdf")).toBeTruthy();
  expect(screen.getByText("Waiting")).toBeTruthy();
  expect(screen.getByText("Reading")).toBeTruthy();
  expect(screen.getByText("Done")).toBeTruthy();
  expect(
    screen.getByText(
      "Could not read: the file could not be opened. Choose the file again to try it again.",
    ),
  ).toBeTruthy();
  // The contract returns no retry or open route, so the page offers none.
  expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
});

test("uploading sends the case number, the area and the files as a form", async () => {
  const { api, calls } = page({
    "POST /uploads": json(202, { batches: [batch({ file_name: "notes.pdf" })] }),
  });
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  fillCase();
  pick("notes.pdf");
  fireEvent.click(screen.getByRole("button", { name: "Upload files" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
  const post = calls.find((c) => c.method === "POST");
  const form = post?.init.body as FormData;
  expect(post?.path).toBe("/uploads");
  expect(form.get("case_number")).toBe("31/207");
  expect(form.get("district_id")).toBe(DISTRICT);
  expect((form.getAll("files")[0] as File).name).toBe("notes.pdf");
  expect(await screen.findByText("Files sent to case 31/207.")).toBeTruthy();
});

test("every picked file is listed with a Remove button, and only the kept files are sent", async () => {
  const { api, calls } = page({
    "POST /uploads": json(202, { batches: [batch({ file_name: "a.pdf" })] }),
  });
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  fillCase();
  pick("a.pdf");
  pick("b.pdf");
  pick("c.pdf");
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
  fireEvent.click(screen.getByRole("button", { name: "Remove b.pdf" }));
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Upload files" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
  const form = calls.find((c) => c.method === "POST")?.init.body as FormData;
  expect(form.getAll("files").map((f) => (f as File).name)).toEqual(["a.pdf", "c.pdf"]);
  expect(await screen.findByText("Files sent to case 31/207.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Remove a.pdf" })).toBeNull();
});

test("choosing a failed file again sends it again through the same route", async () => {
  const { api, calls } = page({
    "GET /uploads": json(200, {
      items: [batch({ file_name: "bad.doc", status: "FAILED", error_code: "INGEST_ERROR" })],
      next_cursor: null,
    }),
    "POST /uploads": json(202, { batches: [batch({ file_name: "bad.doc" })] }),
  });
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  fillCase();
  pick("bad.doc");
  fireEvent.click(screen.getByRole("button", { name: "Upload files" }));
  await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(1));
});

test("a missing case number, area or file is named and nothing is sent", async () => {
  const { api, calls } = page();
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Upload files" }));
  expect(await screen.findByText("Please fill in: Case.")).toBeTruthy();
  expect(screen.getByText("Please fill in: Police area.")).toBeTruthy();
  expect(screen.getByText("Please fill in: Files.")).toBeTruthy();
  expect(screen.getByText("Please fill in 3 fields.")).toBeTruthy();
  expect(calls.some((c) => c.method === "POST")).toBe(false);
});

test("more than 20 files is refused before sending", async () => {
  const { api, calls } = page();
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  fillCase();
  for (let i = 0; i < 21; i++) pick(`f${i}.pdf`);
  fireEvent.click(screen.getByRole("button", { name: "Upload files" }));
  expect(await screen.findByText("You can upload up to 20 files at a time.")).toBeTruthy();
  expect(calls.some((c) => c.method === "POST")).toBe(false);
});

test.each([
  [403, undefined, "You do not have access to do this."],
  [404, undefined, "We could not find this. Go back and try again."],
  [429, undefined, "The system is busy. Please wait a moment, then try again."],
  [503, undefined, "The system is paused for a safety check. Try again later."],
  [409, { code: "RUN_IN_PROGRESS" }, "A matching run is in progress. Try again in a few minutes."],
  [500, undefined, "Something went wrong on our side. Nothing was changed. Try again."],
])("a %s answer to the upload shows the shared message", async (status, body, text) => {
  const { api } = page({ "POST /uploads": json(status, body) });
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  fillCase();
  pick();
  fireEvent.click(screen.getByRole("button", { name: "Upload files" }));
  expect(await screen.findByText(text)).toBeTruthy();
});

test("a 422 puts the error beside the field that the API names", async () => {
  const { api } = page({
    "POST /uploads": json(422, {
      code: "VALIDATION_ERROR",
      field_errors: [{ field: "case_number", code: "too_long" }],
    }),
  });
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  fillCase();
  pick();
  fireEvent.click(screen.getByRole("button", { name: "Upload files" }));
  expect(
    await screen.findByText("Something is missing. Check the fields marked below."),
  ).toBeTruthy();
  expect(screen.getByLabelText("Case").getAttribute("aria-invalid")).toBe("true");
});

test("a field error named files.0 marks the Files field", async () => {
  const { api } = page({
    "POST /uploads": json(422, {
      code: "VALIDATION_ERROR",
      field_errors: [{ field: "body.district_id", code: "invalid" }],
    }),
  });
  renderPage(<UploadPage api={api} lang="en" />);
  await ready();
  fillCase();
  pick();
  fireEvent.click(screen.getByRole("button", { name: "Upload files" }));
  expect(await screen.findByText("Please fill in: Police area.")).toBeTruthy();
});

test("a failed list shows the failure and Try again loads it again", async () => {
  let n = 0;
  const { api } = page({
    "GET /uploads": () =>
      n++ === 0 ? json(503) : json(200, { items: [batch()], next_cursor: null }),
  });
  renderPage(<UploadPage api={api} lang="en" />);
  expect(
    await screen.findByText("The system is paused for a safety check. Try again later."),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("statement.pdf")).toBeTruthy();
});

test("the page reads in Hindi", async () => {
  const { api } = page();
  renderPage(<UploadPage api={api} lang="hi" />);
  expect(await screen.findByRole("button", { name: "फ़ाइलें अपलोड करें" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "फ़ाइलें अपलोड करें" }));
  expect(await screen.findByText("कृपया भरें: मामला।")).toBeTruthy();
});

test("a failed file row reads as full sentences in Hindi, each ending with the danda", async () => {
  const { api } = page({
    "GET /uploads": json(200, { items: [batch({ status: "FAILED" })], next_cursor: null }),
  });
  renderPage(<UploadPage api={api} lang="hi" />);
  const row = await screen.findByText(/पढ़ नहीं सके/);
  expect(row.textContent).toBe(
    "पढ़ नहीं सके: फ़ाइल खुल नहीं सकी। फिर कोशिश करने के लिए फ़ाइल दोबारा चुनें।",
  );
  expect(row.textContent).not.toContain(".");
  // The Hindi text differs from the English text for the keys this row uses.
  expect(t("upload.failed.row", "hi")).not.toBe(t("upload.failed.row", "en"));
  expect(t("upload.retryHint", "hi")).not.toBe(t("upload.retryHint", "en"));
});
