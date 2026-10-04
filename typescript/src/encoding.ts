import { createHash } from "node:crypto";
import { ProtocolError, type Json } from "./types.js";

export function sha256(bytes: Uint8Array): string {
  return "sha256:" + createHash("sha256").update(bytes).digest("hex");
}

export function canonicalBase64(text: string): Uint8Array {
  if (text.length % 4 !== 0) throw new ProtocolError("INVALID_SOURCE");
  let pad = 0;
  if (text.endsWith("==")) pad = 2; else if (text.endsWith("=")) pad = 1;
  const bodyEnd = text.length - pad;
  for (let i=0;i<bodyEnd;i++) { const c=text.charCodeAt(i); const ok=(c>=65&&c<=90)||(c>=97&&c<=122)||(c>=48&&c<=57)||c===43||c===47; if(!ok) throw new ProtocolError("INVALID_SOURCE"); }
  for (let i=bodyEnd;i<text.length;i++) if(text.charCodeAt(i)!==61) throw new ProtocolError("INVALID_SOURCE");
  const b = Buffer.from(text, "base64");
  if (b.toString("base64") !== text) throw new ProtocolError("INVALID_SOURCE");
  return b;
}

export function canonicalJson(value: Json): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value) || Object.is(value, -0)) throw new ProtocolError("INVALID_SOURCE");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return "[" + value.map(canonicalJson).join(",") + "]";
  const keys = Object.keys(value).sort((a,b) => a < b ? -1 : a > b ? 1 : 0);
  return "{" + keys.map(k => JSON.stringify(k)+":"+canonicalJson(value[k]!)).join(",") + "}";
}

function decimalParts(s: string): { sign: bigint; coeff: bigint; scale: number } | null {
  const m = /^(-)?(?:(0|[1-9]\d*))(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(s);
  if (!m) return null;
  const neg = !!m[1];
  const int = m[2]!;
  const frac = m[3] ?? "";
  const exp = Number(m[4] ?? "0");
  if (!Number.isSafeInteger(exp) || Math.abs(exp) > 100000) return null;
  const digits = (int + frac).replace(/^0+(?=\d)/, "");
  const coeff = BigInt(digits || "0");
  return { sign: neg ? -1n : 1n, coeff, scale: frac.length - exp };
}
function equalDecimal(a: string, b: string): boolean {
  const x = decimalParts(a), y = decimalParts(b); if (!x || !y) return false;
  let ax=x.sign*x.coeff, by=y.sign*y.coeff;
  if (x.scale > y.scale) by *= 10n ** BigInt(x.scale-y.scale);
  else if (y.scale > x.scale) ax *= 10n ** BigInt(y.scale-x.scale);
  return ax===by;
}

export function validateNumberToken(token: string): number {
  const p = decimalParts(token); if (!p) throw new ProtocolError("INVALID_SOURCE");
  if (p.coeff === 0n && p.sign < 0n) throw new ProtocolError("INVALID_SOURCE");
  const n = Number(token);
  if (!Number.isFinite(n)) throw new ProtocolError("NUMBER_UNREPRESENTABLE");
  if (Number.isInteger(n)) {
    if (!Number.isSafeInteger(n)) throw new ProtocolError("NUMBER_UNREPRESENTABLE");
    if (!equalDecimal(token, JSON.stringify(n))) throw new ProtocolError("NUMBER_UNREPRESENTABLE");
    return n;
  }
  const rt = JSON.stringify(n);
  if (!equalDecimal(token, rt)) throw new ProtocolError("NUMBER_UNREPRESENTABLE");
  return n;
}

function scalarOk(s: string): boolean {
  for (let i=0;i<s.length;i++) {
    const c=s.charCodeAt(i);
    if (c>=0xD800 && c<=0xDBFF) { const d=s.charCodeAt(++i); if (!(d>=0xDC00&&d<=0xDFFF)) return false; }
    else if (c>=0xDC00&&c<=0xDFFF) return false;
  }
  return true;
}

export function parseStrictJson(bytes: Uint8Array, maxDepth = 64): Json {
  if (bytes.length>=3 && bytes[0]===0xEF && bytes[1]===0xBB && bytes[2]===0xBF) throw new ProtocolError("INVALID_SOURCE");
  let s: string;
  try { s = new TextDecoder("utf-8", {fatal:true}).decode(bytes); } catch { throw new ProtocolError("INVALID_SOURCE"); }
  if (s.charCodeAt(0)===0xFEFF) throw new ProtocolError("INVALID_SOURCE");
  let i=0;
  const ws=()=>{while(i<s.length && /[\x20\x09\x0a\x0d]/.test(s[i]!))i++;};
  const str=():string=>{
    const start=i; if(s[i++]!=='"') throw new ProtocolError("INVALID_SOURCE");
    let esc=false;
    while(i<s.length){const c=s[i++]!; if(!esc&&c==='"')break; if(!esc&&c==='\\'){esc=true;continue;} if(!esc&&c<' ')throw new ProtocolError("INVALID_SOURCE"); esc=false;}
    if(s[i-1]!== '"') throw new ProtocolError("INVALID_SOURCE");
    let v:string; try{v=JSON.parse(s.slice(start,i));}catch{throw new ProtocolError("INVALID_SOURCE");}
    if(!scalarOk(v))throw new ProtocolError("INVALID_SOURCE"); return v;
  };
  const value=(depth:number):Json=>{
    if(depth>maxDepth) throw new ProtocolError("LIMIT_EXCEEDED"); ws(); const c=s[i];
    if(c==='"')return str();
    if(c==='{'){i++; const o:{[k:string]:Json}={}; const seen=new Set<string>(); ws(); if(s[i]==='}'){i++;return o;} while(true){ws(); if(s[i]!=='"')throw new ProtocolError("INVALID_SOURCE"); const k=str(); if(seen.has(k))throw new ProtocolError("INVALID_SOURCE"); seen.add(k); ws(); if(s[i++]!==':')throw new ProtocolError("INVALID_SOURCE"); o[k]=value(depth+1); ws(); if(s[i]==='}'){i++;return o;} if(s[i++]!==',')throw new ProtocolError("INVALID_SOURCE");}}
    if(c==='['){i++; const a:Json[]=[]; ws(); if(s[i]===']'){i++;return a;} while(true){a.push(value(depth+1));ws();if(s[i]===']'){i++;return a;}if(s[i++]!==',')throw new ProtocolError("INVALID_SOURCE");}}
    if(s.startsWith('true',i)){i+=4;return true;} if(s.startsWith('false',i)){i+=5;return false;} if(s.startsWith('null',i)){i+=4;return null;}
    const m=/-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(s.slice(i)); if(!m||m.index!==0)throw new ProtocolError("INVALID_SOURCE"); i+=m[0].length; return validateNumberToken(m[0]);
  };
  ws(); const out=value(1); ws(); if(i!==s.length)throw new ProtocolError("INVALID_SOURCE"); return out;
}
