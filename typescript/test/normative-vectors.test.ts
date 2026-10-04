import test from "node:test";import assert from "node:assert/strict";import {readFileSync} from "node:fs";import {resolve} from "node:path";import {canonicalBase64,canonicalJson,gitBlobId,parseStrictJson,ProtocolError,type Json} from "../src/index.js";
const fx=JSON.parse(readFileSync(resolve(process.cwd(),"../docs/protocol/fixtures.json"),"utf8"));

test("normative strict serialization vectors",()=>{for(const v of fx.serialization){const b=Buffer.from(v.base64,"base64");if(v.error===null)parseStrictJson(b);else{let got:string|null=null;try{parseStrictJson(b)}catch(e){got=(e as ProtocolError).code}assert.equal(got,v.error,v.id);}}});
test("normative canonical base64 vectors",()=>{for(const v of fx.base64_cases){let ok=true;try{canonicalBase64(v.text)}catch{ok=false}assert.equal(ok,v.valid,JSON.stringify(v.text));}});
test("normative JCS metric vectors",()=>{for(const v of fx.jcs_vectors)assert.equal(canonicalJson(v.value as Json),v.canonical,v.id)});
test("normative Git blob SHA-1/SHA-256 vectors",()=>{for(const v of fx.git_blob_vectors)assert.equal(gitBlobId(Buffer.from(v.base64,"base64"),v.algorithm),v.object)});
