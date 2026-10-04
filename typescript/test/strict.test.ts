import test from "node:test";
import assert from "node:assert/strict";
import { canonicalBase64, parseStrictJson, ProtocolError } from "../src/index.js";

const ok=(s:string)=>parseStrictJson(Buffer.from(s,"utf8"));
const code=(fn:()=>unknown)=>{try{fn();return null}catch(e){return (e as ProtocolError).code}};

test("strict JSON duplicate, UTF-8, surrogate and number rules",()=>{
 assert.equal(code(()=>ok('{"a":1,"a":2}')),"INVALID_SOURCE");
 assert.equal(code(()=>ok('{"a":1,"\\u0061":2}')),"INVALID_SOURCE");
 assert.equal(code(()=>parseStrictJson(new Uint8Array([0x22,0xff,0x22]))),"INVALID_SOURCE");
 assert.equal(code(()=>ok('"\\ud800"')),"INVALID_SOURCE");
 assert.equal(ok('"\\ud83d\\ude00"'),"😀");
 assert.equal(code(()=>ok('-0')),"INVALID_SOURCE");
 assert.equal(code(()=>ok('-0.0')),"INVALID_SOURCE");
 assert.equal(code(()=>ok('9007199254740993')),"NUMBER_UNREPRESENTABLE");
 assert.equal(code(()=>ok('0.10000000000000001')),"NUMBER_UNREPRESENTABLE");
 assert.equal(ok('0.1'),0.1);
 assert.equal(ok('1.00e0'),1);
});

test("canonical base64",()=>{
 assert.deepEqual([...canonicalBase64("AP8=")],[0,255]);
 for(const s of ["AB==","AP9=","AA","AA==\n","-w==","AA==="])assert.equal(code(()=>canonicalBase64(s)),"INVALID_SOURCE");
});
