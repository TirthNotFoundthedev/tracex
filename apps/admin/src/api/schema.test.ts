// @vitest-environment node
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test } from "vitest";

test("generated API types match contracts/openapi.yaml", () => {
  const script = fileURLToPath(new URL("../../scripts/gen-api.mjs", import.meta.url));
  const run = spawnSync(process.execPath, [script, "--check"], { encoding: "utf8" });
  expect(run.stderr).toBe("");
  expect(run.status).toBe(0);
}, 60_000);
