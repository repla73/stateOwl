import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { publicationFixtureMap } from "./publish-fixture-map.js";

test("R3 TypeScript tooling maps every shared publication case exactly once",()=>{
 const root=resolve(process.cwd(),"..");
 const cases=JSON.parse(readFileSync(resolve(root,"docs/protocol/publish-cases.json"),"utf8")) as Array<{id:string}>;
 const actual=Object.keys(publicationFixtureMap).sort();const expected=cases.map(c=>c.id).sort();
 assert.equal(cases.length,89);assert.deepEqual(actual,expected);
});