import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { gitBlobId, MemoryProvider, Reader, sha256, type Capabilities, type Target } from "../src/index.js";

const repositoryRoot = resolve(process.cwd(), "..");
const fixtureRoot = resolve(repositoryRoot, "tests/fixtures/r2-native-state");
const fixture = JSON.parse(readFileSync(resolve(fixtureRoot, "fixture.json"), "utf8"));

const capabilities: Capabilities = {
  protocol: "stateowl/0.2-draft.3",
  operations: ["read"],
  formats: ["json", "text", "base64"],
  features: ["routes", "expand"],
  resolvers: ["urn:stateowl:binding:router-v1:1"],
  limits: {
    request_bytes: 65536,
    record_bytes: 16384,
    mutation_bytes: 32768,
    response_bytes: 65536,
    records: 32,
    expansions: 16,
    changes: 32,
    tag_hops: 8,
    reconcile_commits: 16,
    json_depth: 64
  }
};

const target = fixture.identities.opaque.target as Target;
const snapshot = fixture.identities.opaque.snapshot.id as string;
const fixtureFiles: Record<string, { base64: string; mode: string }> = {};

for (const declared of fixture.files) {
  const bytes = readFileSync(resolve(fixtureRoot, declared.path));
  assert.equal(bytes.byteLength, declared.bytes, `${declared.path} byte length`);
  assert.equal(sha256(bytes), declared.digest, `${declared.path} digest`);
  assert.equal(gitBlobId(bytes, "sha1"), declared.git_blob_sha1, `${declared.path} Git blob identity`);
  fixtureFiles[declared.path] = { base64: Buffer.from(bytes).toString("base64"), mode: "100644" };
}

class TraceProvider extends MemoryProvider {
  filePaths: string[] = [];
  override async file(t: Target, s: string, path: string) {
    this.filePaths.push(path);
    return super.file(t, s, path);
  }
}

function provider() {
  return new TraceProvider({
    target,
    head: fixture.identities.opaque.current_resolves_to.id,
    native: false,
    objects: {
      [snapshot]: { type: "commit", parents: [], message: "shared native fixture\n", files: fixtureFiles }
    }
  });
}

assert.equal(fixture.stateowl_router_required, false);
assert.equal(fixture.governance_semantics_in_core, false);

for (const sharedCase of fixture.cases) {
  test(`shared native .state: ${sharedCase.id}`, async () => {
    const p = provider();
    const got = await new Reader(p, structuredClone(capabilities)).read(sharedCase.request);
    assert.deepEqual(got, sharedCase.expected);

    assert.equal(p.calls.resolve, sharedCase.trace.mutable_ref_resolutions, "mutable ref resolutions");
    assert.deepEqual(p.filePaths, sharedCase.trace.file_reads, "focused file reads");
    assert.ok(!p.filePaths.includes(".stateowl/router.json"), "router must not be read");
    assert.ok(!("routing" in got), "routing response must be absent");

    if (sharedCase.trace.all_records_snapshot) {
      assert.equal(got.snapshot.id, sharedCase.trace.all_records_snapshot);
    }
    if (sharedCase.assertions?.not_returned) {
      for (const record of got.records) {
        if (record.status !== "found" || record.format !== "json") continue;
        for (const field of sharedCase.assertions.not_returned) {
          assert.ok(!(field in record.value), `project-only field leaked: ${field}`);
        }
      }
    }
  });
}
