import { Button, FileDrop, Loading, Message, Select, Table, TextField } from "@tracex/ui";
import { useCallback, useEffect, useState } from "react";

import type { AdminApi } from "../api";
import type { FailureResult } from "../api/resultKeys";
import type { components } from "../api/schema";
import { FailureView } from "../components/FailureView";
import { dateTime } from "../format";
import { t, type Language, type MessageKey } from "../i18n";

type Batch = components["schemas"]["UploadBatch"];
type Place = { id: string; name: string };
type Field = "case" | "district" | "files";

/** The contract allows 1 to 20 files in one upload. */
const MAX_FILES = 20;
const ACCEPT = ".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,image/*";

const STATUS_KEY: Record<Exclude<Batch["status"], "FAILED">, MessageKey> = {
  WAITING: "upload.status.waiting",
  READING: "upload.status.reading",
  DONE: "upload.status.done",
};

const FIELD_OF: Record<string, Field> = {
  case_number: "case",
  district_id: "district",
  files: "files",
};

const FIELD_LABEL: Record<Field, MessageKey> = {
  case: "upload.case",
  district: "upload.district",
  files: "upload.files",
};

type Load =
  | { state: "loading" }
  | { state: "failed"; result: FailureResult }
  | { state: "ready"; places: Place[] };

interface UploadPageProps {
  api: AdminApi;
  lang: Language;
  /** How often unfinished files are checked again. Tests may pass a small number. */
  pollMs?: number;
}

/**
 * A1 Upload case material. The contract takes a case number (existing or new, the Administrator cannot list
 * cases), a police area and 1 to 20 files, and returns one batch per file. There is no retry or open route,
 * so a failed row shows its reason in words and nothing more.
 */
export function UploadPage({ api, lang, pollMs = 3000 }: UploadPageProps) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [batches, setBatches] = useState<Batch[]>([]);
  const [caseNumber, setCaseNumber] = useState("");
  const [district, setDistrict] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [missing, setMissing] = useState<Field[]>([]);
  const [tooMany, setTooMany] = useState(false);
  const [problem, setProblem] = useState<FailureResult | undefined>();
  const [sending, setSending] = useState(false);
  const [sentTo, setSentTo] = useState<string | undefined>();

  const refresh = useCallback(async () => {
    const [places, uploads] = await Promise.all([
      api.client.listJurisdictions(),
      api.client.listUploads({ limit: 50 }),
    ]);
    if (places.kind !== "ok") return setLoad({ state: "failed", result: places });
    if (uploads.kind !== "ok") return setLoad({ state: "failed", result: uploads });
    setBatches(uploads.data.items);
    setLoad({
      state: "ready",
      places: places.data.items.flatMap((state) =>
        state.districts.map((d) => ({ id: d.district_id, name: d.name })),
      ),
    });
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const unfinished = batches.some((b) => b.status === "WAITING" || b.status === "READING");
  useEffect(() => {
    if (!unfinished) return;
    const timer = setTimeout(() => {
      void api.client.listUploads({ limit: 50 }).then((result) => {
        if (result.kind === "ok") setBatches(result.data.items);
      });
    }, pollMs);
    return () => clearTimeout(timer);
  }, [api, unfinished, batches, pollMs]);

  const submit = async () => {
    setProblem(undefined);
    setSentTo(undefined);
    const absent: Field[] = [];
    if (caseNumber.trim() === "") absent.push("case");
    if (district === "") absent.push("district");
    if (files.length === 0) absent.push("files");
    setMissing(absent);
    setTooMany(false);
    if (absent.length > 0) return;
    if (files.length > MAX_FILES) return setTooMany(true);

    setSending(true);
    const result = await api.client.uploadFiles({
      case_number: caseNumber.trim(),
      district_id: district,
      files,
    });
    setSending(false);
    if (result.kind === "invalid") {
      const named = result.fieldErrors
        .map((error) => FIELD_OF[error.field.split(".").at(-1) ?? ""])
        .filter((field): field is Field => field !== undefined);
      setMissing(named);
      setProblem(result);
      return;
    }
    if (result.kind !== "ok") return setProblem(result);
    setBatches((old) => [...result.data.batches, ...old]);
    setFiles([]);
    setSentTo(caseNumber.trim());
  };

  if (load.state === "loading") return <Loading label={t("loading.default", lang)} />;
  if (load.state === "failed") {
    return (
      <FailureView
        result={load.result}
        lang={lang}
        onRetry={() => {
          setLoad({ state: "loading" });
          void refresh();
        }}
      />
    );
  }

  const error = (field: Field) =>
    missing.includes(field)
      ? t("common.fillIn", lang, { field: t(FIELD_LABEL[field], lang) })
      : undefined;
  const places = load.places;

  return (
    <div className="admin-page">
      <h2>{t("upload.title", lang)}</h2>
      {missing.length > 1 ? (
        <Message kind="error">{t("common.fillInCount", lang, { n: missing.length })}</Message>
      ) : null}
      {problem ? <FailureView result={problem} lang={lang} /> : null}
      {sentTo ? <Message kind="success">{t("upload.sent", lang, { case: sentTo })}</Message> : null}
      {tooMany ? <Message kind="error">{t("upload.tooMany", lang)}</Message> : null}
      <form
        className="admin-form"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <TextField
          label={t("upload.case", lang)}
          hint={t("upload.case.hint", lang)}
          value={caseNumber}
          maxLength={64}
          error={error("case")}
          onChange={setCaseNumber}
        />
        <Select
          label={t("upload.district", lang)}
          value={district}
          options={[
            { value: "", label: "" },
            ...places.map((place) => ({ value: place.id, label: place.name })),
          ]}
          error={error("district")}
          onChange={setDistrict}
        />
        <FileDrop
          label={t("upload.files", lang)}
          accept={ACCEPT}
          onFile={(file) => setFiles((old) => [...old, file])}
        />
        {files.length > 0 ? (
          <ul className="admin-files">
            {files.map((file, index) => (
              <li key={`${file.name}-${index}`}>
                <span>{file.name}</span>
                <Button
                  variant="secondary"
                  type="button"
                  onClick={() => setFiles((old) => old.filter((_, i) => i !== index))}
                >
                  {t("upload.remove", lang, { name: file.name })}
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        <p className="admin-hint">{t("upload.types", lang)}</p>
        {error("files") ? <p className="admin-error">{error("files")}</p> : null}
        <div className="admin-actions">
          <Button variant="primary" type="submit" icon="upload" disabled={sending}>
            {t("upload.submit", lang)}
          </Button>
        </div>
      </form>
      {batches.length === 0 ? (
        <p>{t("upload.empty", lang)}</p>
      ) : (
        <Table
          caption={t("upload.title", lang)}
          rows={batches}
          rowKey={(batch) => batch.batch_id}
          columns={[
            { id: "file", header: t("upload.col.file", lang), cell: (b) => b.file_name },
            {
              id: "status",
              header: t("common.status", lang),
              cell: (b) =>
                b.status === "FAILED"
                  ? `${t("upload.failed.row", lang)} ${t("upload.retryHint", lang)}`
                  : t(STATUS_KEY[b.status], lang),
            },
            {
              id: "date",
              header: t("common.date", lang),
              numeric: true,
              cell: (b) => dateTime(b.created_at, lang),
            },
          ]}
        />
      )}
    </div>
  );
}
