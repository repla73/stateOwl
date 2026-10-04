import { createHash } from "node:crypto";
import { ProtocolError, type Target } from "./types.js";

export function gitAlgorithm(id:string): "sha1"|"sha256" {
  if(/^git:sha1:[0-9a-f]{40}$/.test(id)) return "sha1";
  if(/^git:sha256:[0-9a-f]{64}$/.test(id)) return "sha256";
  throw new ProtocolError("INVALID_SOURCE");
}
export function typedGitOid(oid:string):string {
  if(/^[0-9a-f]{40}$/.test(oid)) return `git:sha1:${oid}`;
  if(/^[0-9a-f]{64}$/.test(oid)) return `git:sha256:${oid}`;
  throw new ProtocolError("INVALID_SOURCE");
}
export function rawOid(id:string):string { gitAlgorithm(id); return id.slice(id.lastIndexOf(":")+1); }
export function gitBlobId(bytes:Uint8Array, alg:"sha1"|"sha256"):string {
  const h=createHash(alg); h.update(`blob ${bytes.byteLength}\0`); h.update(bytes); return `git:${alg}:${h.digest("hex")}`;
}
export function validateGitTarget(t:Target):void {
  if(t.kind!=="git") return;
  if(t.authority==="github.com") {
    if(!/^[a-z0-9_.-]+\/[a-z0-9_.-]+$/.test(t.resource) || t.resource.endsWith(".git")) throw new ProtocolError("INVALID_REQUEST");
  }
  const ref=t.namespace;
  const parts=ref.split("/");
  const invalid=!/^refs\/(heads|tags)\//.test(ref)||parts.some(p=>p.length===0||p.startsWith(".")||p.endsWith(".lock"))||ref.includes("..")||ref.includes("@{")||/[~^:?*\[\\\x00-\x20\x7f]/.test(ref)||ref.endsWith("/")||ref.endsWith(".");
  if(invalid) throw new ProtocolError("INVALID_REQUEST");
}
