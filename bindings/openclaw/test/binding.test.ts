import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  BindingInputError,
  R4_PROFILE_DIGEST,
  R4_PROFILE_ID,
  TOOL_NAMES,
  isWritePathAuthorized,
  readRequestFromHandoff,
  requestedPublicationPaths,
  unrelatedPaths,
  type BindingConfig,
} from "../core.ts";

const here = dirname(fileURLToPath(import.meta.url));
const pluginRoot = resolve(here, "..");
const repoRoot = resolve(pluginRoot, "../..");
const source = readFileSync(resolve(pluginRoot, "index.ts"), "utf8");
const manifest = JSON.parse(readFileSync(resolve(pluginRoot, "openclaw.plugin.json"), "utf8"));
const handoff = readFileSync(resolve(repoRoot, "tests/fixtures/r4-continuity/handoff.json"), "utf8");
const configuredTarget = {
  kind: "git",
  authority: "github.com",
  resource: "repla73/stateowl-r4-qualification",
  namespace: "refs/heads/stateowl-r4-qualification",
};

test("exactly two bounded model-facing tools are declared", () => {
  assert.deepEqual(manifest.contracts.tools, [...TOOL_NAMES]);
  const registered = [...source.matchAll(/name:\s*"(stateowl_[a-z]+)"/g)].map((match) => match[1]);
  assert.deepEqual(registered, [...TOOL_NAMES]);
  assert.equal((source.match(/Type\.String\(\{ minLength: 2, maxLength: MAX_TOOL_INPUT_BYTES \}\)/g) ?? []).length, 2);
  assert.match(source, /additionalProperties: false/);
});

test("binding delegates directly to accepted TypeScript Reader and Publisher", () => {
  assert.match(source, /typescript\/dist\/src\/index\.js/);
  assert.match(source, /new stateowl\.Reader\(/);
  assert.match(source, /new stateowl\.Publisher\(/);
  assert.doesNotMatch(source, /child_process|spawn\(|exec\(|python|MCP|mcp|daemon|scheduler|database/i);
});

test("R4 handoff fixture drives a direct read without transcript context", () => {
  const mapped = readRequestFromHandoff(handoff, configuredTarget);
  assert.equal(mapped.request.protocol, "stateowl/0.2-draft.3");
  assert.equal(mapped.request.op, "read");
  assert.deepEqual(mapped.request.target, configuredTarget);
  assert.deepEqual(mapped.requestedPaths, ["state/task.json", "state/work.json"]);
  assert.equal((JSON.parse(handoff) as any).profile.id, R4_PROFILE_ID);
  assert.equal((JSON.parse(handoff) as any).profile.digest, R4_PROFILE_DIGEST);
});

test("handoff target escape is rejected before stateOwl provider access", () => {
  const value = JSON.parse(handoff);
  value.target.namespace = "refs/heads/other";
  assert.throws(
    () => readRequestFromHandoff(JSON.stringify(value), configuredTarget),
    (error: unknown) => error instanceof BindingInputError && error.code === "FORBIDDEN",
  );
});

test("write-path confinement is fail-closed", () => {
  const config: BindingConfig = {
    target: configuredTarget,
    publishEnabled: true,
    singleStepContinuity: true,
    writePaths: new Set(["state/work.json"]),
  };
  assert.equal(isWritePathAuthorized(config, "state/work.json"), true);
  assert.equal(isWritePathAuthorized(config, "state/task.json"), false);
  assert.equal(
    isWritePathAuthorized({ ...config, publishEnabled: false }, "state/work.json"),
    false,
  );
  assert.equal(
    isWritePathAuthorized({ ...config, singleStepContinuity: false }, "state/work.json"),
    false,
  );
});

test("publication-disabled mode has no raw-write fallback", () => {
  assert.match(source, /operations: publishEnabled \? \["read", "publish"\] : \["read"\]/);
  assert.match(source, /isWritePathAuthorized\(config, path\)/);
  assert.doesNotMatch(source, /updateRefs|createBlob|createCommit|createTree|git\/refs|git\/blobs|git\/commits|git\/trees/);
});

test("publication request is passed unchanged to the accepted Publisher", () => {
  assert.match(source, /publisher\.publish\(params\.requestJson\)/);
  assert.doesNotMatch(source, /mode\s*[:=]\s*["']submit["']|mode\s*[:=]\s*["']reconcile["']/);
  const raw = JSON.stringify({
    protocol: "stateowl/0.2-draft.3",
    op: "publish",
    target: configuredTarget,
    expected: { id: "git:sha1:" + "1".repeat(40) },
    mode: "reconcile",
    validation: null,
    changes: [{ path: "state/work.json", put: { encoding: "utf8", data: "{\"step\":1}\n" } }],
  });
  assert.deepEqual(requestedPublicationPaths(raw), ["state/work.json"]);
});

test("indeterminate and verification_pending are not translated into success", () => {
  assert.doesNotMatch(source, /outcome\s*===\s*["'](?:indeterminate|verification_pending)["']/);
  assert.match(source, /const text = JSON\.stringify\(result\)/);
  assert.match(source, /stateowl: result/);
});

test("binding performs no repository discovery or crawl", () => {
  assert.doesNotMatch(source, /searchRepositories|listRepositories|repository discovery|\/search\/|\/repos\/\$\{.*\}\/contents\/\?/i);
  assert.match(source, /new Set\(\[config\.target\.resource\]\)/);
});

test("secrets stay in trusted config and out of tool output", () => {
  assert.equal(manifest.configContracts.secretInputs.paths[0].path, "githubToken");
  assert.match(source, /githubFetchTransport\(config\.githubToken\)/);
  assert.match(source, /githubPublicationFetchTransports\(config\.githubToken\)/);
  const resultBody = source.slice(source.indexOf("function toolResult"), source.indexOf("export default"));
  assert.doesNotMatch(resultBody, /githubToken|pluginConfig/);
});

test("qualification evidence reports unrelated provider-observed paths", () => {
  assert.deepEqual(
    unrelatedPaths(["state/task.json", "state/work.json"], ["state/work.json"]),
    ["state/task.json"],
  );
  assert.match(source, /provider_operations/);
  assert.match(source, /requested_paths/);
  assert.match(source, /unrelated_paths/);
  assert.match(source, /declared_tools/);
});
