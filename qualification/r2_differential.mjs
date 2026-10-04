#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { MemoryProvider, Reader } from "../typescript/dist/src/index.js";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const readJson = (path) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));

const fixturePack = readJson("docs/protocol/fixtures.json");
const assets = fixturePack.assets;
const normativeCases = readJson("docs/protocol/read-cases.json");
const nativeFixture = readJson("tests/fixtures/r2-native-state/fixture.json");

function expand(value, stack = []) {
  if (Array.isArray(value)) return value.map((item) => expand(item, stack));
  if (value && typeof value === "object") {
    const keys = Object.keys(value);
    if (keys.length === 1 && keys[0] === "$fixture") {
      const name = value.$fixture;
      if (typeof name !== "string" || !(name in assets) || stack.includes(name) || stack.length >= 64) {
        throw new Error(`bad fixture ${String(name)}`);
      }
      return expand(structuredClone(assets[name]), [...stack, name]);
    }
    const out = {};
    for (const [key, item] of Object.entries(value)) out[key] = expand(item, stack);
    return out;
  }
  return value;
}

function patch(base, delta) {
  if (delta === null) return undefined;
  if (!delta || typeof delta !== "object" || Array.isArray(delta)) return structuredClone(delta);
  const out = base && typeof base === "object" && !Array.isArray(base) ? structuredClone(base) : {};
  for (const [key, value] of Object.entries(delta)) {
    if (value === null) delete out[key];
    else out[key] = patch(out[key], value);
  }
  return out;
}

async function runTypeScriptNormative() {
  const results = [];
  for (const rawCase of normativeCases) {
    const testCase = expand(rawCase);
    let request = expand(fixturePack.requests[testCase.request]);
    if (testCase.request_patch) request = patch(request, expand(testCase.request_patch));

    let world = expand(fixturePack.defaults.world);
    if (testCase.world) world = patch(world, expand(fixturePack.worlds[testCase.world]));
    if (testCase.world_patch) world = patch(world, expand(testCase.world_patch));

    let capabilities = expand(fixturePack.defaults.capabilities);
    if (testCase.cap_patch) capabilities = patch(capabilities, expand(testCase.cap_patch));

    const input = testCase.request_bytes ? Buffer.from(testCase.request_bytes, "base64") : request;
    const output = await new Reader(new MemoryProvider(world), capabilities).read(input);
    results.push({ id: testCase.id, output });
  }
  return results;
}

async function runTypeScriptNative() {
  const identity = nativeFixture.identities.opaque;
  const files = {};
  for (const declared of nativeFixture.files) {
    const bytes = readFileSync(resolve(ROOT, "tests/fixtures/r2-native-state", declared.path));
    files[declared.path] = { base64: Buffer.from(bytes).toString("base64"), mode: "100644" };
  }

  const capabilities = expand(fixturePack.defaults.capabilities);
  const results = [];
  for (const testCase of nativeFixture.cases) {
    const provider = new MemoryProvider({
      target: identity.target,
      head: identity.current_resolves_to.id,
      native: false,
      objects: {
        [identity.snapshot.id]: {
          type: "commit",
          parents: [],
          message: "shared native fixture\n",
          files
        }
      }
    });
    const output = await new Reader(provider, structuredClone(capabilities)).read(structuredClone(testCase.request));
    results.push({ id: testCase.id, output });
  }
  return results;
}

const pythonProgram = String.raw`
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from stateowl.r2 import R2Reader
from stateowl.r2_memory import MemoryReadProvider
from r2_fixture_support import FixtureProvider, case_inputs, load_read_inputs

suite, cases = load_read_inputs(ROOT)
normative = []
for case in cases:
    raw, world, capabilities = case_inputs(suite, case)
    output = R2Reader(FixtureProvider(world), capabilities).read_bytes(raw)
    normative.append({"id": case["id"], "output": output})

fixture_root = ROOT / "tests" / "fixtures" / "r2-native-state"
native_fixture = json.loads((fixture_root / "fixture.json").read_text())
identity = native_fixture["identities"]["opaque"]
files = {item["path"]: (fixture_root / item["path"]).read_bytes() for item in native_fixture["files"]}
native = []
for case in native_fixture["cases"]:
    provider = MemoryReadProvider(
        identity["target"],
        {identity["snapshot"]["id"]: {"type": "snapshot", "files": files}},
        head=identity["current_resolves_to"]["id"],
        algorithm=None,
    )
    output = R2Reader(provider).read(case["request"])
    native.append({"id": case["id"], "output": output})

print(json.dumps({"normative": normative, "native": native}, separators=(",", ":"), sort_keys=True))
`;

function runPython() {
  const command = process.env.PYTHON || "python3";
  const result = spawnSync(command, ["-c", pythonProgram, ROOT], {
    cwd: ROOT,
    encoding: "utf8",
    env: process.env
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.stderr.write(result.stderr || "");
    throw new Error(`Python differential side exited ${result.status}`);
  }
  return JSON.parse(result.stdout);
}

function same(left, right) {
  try {
    assert.deepEqual(left, right);
    return true;
  } catch {
    return false;
  }
}

function compareSuite(name, expectedCases, pythonResults, typescriptResults) {
  const expected = new Map(expectedCases.map((testCase) => [testCase.id, expand(testCase).expected]));
  const py = new Map(pythonResults.map((result) => [result.id, result.output]));
  const ts = new Map(typescriptResults.map((result) => [result.id, result.output]));
  const mismatches = [];

  for (const [id, want] of expected) {
    if (!py.has(id) || !ts.has(id)) {
      mismatches.push({ suite: name, id, reason: "missing_result" });
      continue;
    }
    const pyOut = py.get(id);
    const tsOut = ts.get(id);
    if (!same(pyOut, want)) mismatches.push({ suite: name, id, reason: "python_expected_mismatch" });
    if (!same(tsOut, want)) mismatches.push({ suite: name, id, reason: "typescript_expected_mismatch" });
    if (!same(pyOut, tsOut)) mismatches.push({ suite: name, id, reason: "cross_language_mismatch" });
  }

  for (const id of py.keys()) if (!expected.has(id)) mismatches.push({ suite: name, id, reason: "unexpected_python_result" });
  for (const id of ts.keys()) if (!expected.has(id)) mismatches.push({ suite: name, id, reason: "unexpected_typescript_result" });

  return { total: expected.size, matched: expected.size - new Set(mismatches.map((item) => item.id)).size, mismatches };
}

const python = runPython();
const typescriptNormative = await runTypeScriptNormative();
const typescriptNative = await runTypeScriptNative();

const normative = compareSuite("normative", normativeCases, python.normative, typescriptNormative);
const nativeState = compareSuite("native_state", nativeFixture.cases, python.native, typescriptNative);
const mismatches = [...normative.mismatches, ...nativeState.mismatches];

const result = {
  schema: "stateowl.r2-differential/v1",
  normative: { matched: normative.matched, total: normative.total },
  native_state: { matched: nativeState.matched, total: nativeState.total },
  mismatches
};

process.stdout.write(JSON.stringify(result, null, 2) + "\n");
if (mismatches.length) process.exitCode = 1;
