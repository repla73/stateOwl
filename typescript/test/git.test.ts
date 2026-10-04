import test from "node:test";
import assert from "node:assert/strict";
import { gitBlobId, typedGitOid } from "../src/index.js";

test("native Git blob identities support SHA-1 and SHA-256",()=>{
 const bytes=Buffer.from("hello\n");
 assert.equal(gitBlobId(bytes,"sha1"),"git:sha1:ce013625030ba8dba906f756967f9e9ca394464a");
 assert.equal(gitBlobId(bytes,"sha256"),"git:sha256:2cf8d83d9ee29543b34a87727421fdecb7e3f3a183d337639025de576db9ebb4");
 assert.equal(typedGitOid("a".repeat(40)),"git:sha1:"+"a".repeat(40));assert.equal(typedGitOid("a".repeat(64)),"git:sha256:"+"a".repeat(64));
});
