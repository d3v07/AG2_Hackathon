// Loads public/data.js into window.CONCORD_DATA for tests. The fixture
// file uses `window.CONCORD_DATA = {...}` in module-execution syntax, so
// we use vm.runInThisContext to set the global before app.jsx imports.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = join(__dirname, "..", "..", "public", "data.js");

export function loadFixture() {
  const source = readFileSync(FIXTURE_PATH, "utf8");
  // Run in jsdom's window context — sets window.CONCORD_DATA
  vm.runInThisContext(source);
  return window.CONCORD_DATA;
}
