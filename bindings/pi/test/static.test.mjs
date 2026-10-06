import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(here, "../index.ts"), "utf8");

test("Pi binding exposes only the two logical stateOwl tools", () => {
  const names = [...source.matchAll(/name:\s*"([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(names, ["stateowl_read", "stateowl_publish"]);
});

test("Pi binding loads the accepted TypeScript implementation in-process", () => {
  assert.match(source, /typescript\/dist\/src\/index\.js/);
  assert.doesNotMatch(source, /child_process|spawn\(|exec\(|python|MCP|registerMcpServer/);
});

test("Pi binding keeps publication fail-closed and scoped", () => {
  assert.match(source, /STATEOWL_PUBLISH_ENABLED/);
  assert.match(source, /STATEOWL_SINGLE_STEP_CONTINUITY/);
  assert.match(source, /STATEOWL_WRITE_PATHS/);
  assert.match(source, /TrustedProjectValidationBoundary/);
  assert.match(source, /ExactTargetReadProvider/);
});
