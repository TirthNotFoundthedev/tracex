import process from "node:process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import openapiTS, { astToString } from "openapi-typescript";
import { format, resolveConfig } from "prettier";

const here = dirname(fileURLToPath(import.meta.url));
const contract = resolve(here, "../../../contracts/openapi.yaml");
const target = resolve(here, "../src/api/schema.d.ts");
const check = process.argv.includes("--check");

const normalise = (text) => text.replace(/\r\n/g, "\n");

const ast = await openapiTS(pathToFileURL(contract));
const raw = astToString(ast);
const options = (await resolveConfig(target)) ?? {};
const generated = normalise(await format(raw, { ...options, filepath: target }));

if (check) {
  let current = "";
  try {
    current = normalise(readFileSync(target, "utf8"));
  } catch {
    current = "";
  }
  if (current !== generated) {
    process.stderr.write("src/api/schema.d.ts is stale. Run: npm run gen:api -w @tracex/admin\n");
    process.exit(1);
  }
  process.stdout.write("src/api/schema.d.ts matches contracts/openapi.yaml\n");
} else {
  writeFileSync(target, generated);
}
