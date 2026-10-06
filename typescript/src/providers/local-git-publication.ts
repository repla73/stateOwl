import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { canonicalBase64 } from "../encoding.js";
import { rawOid, typedGitOid } from "../git.js";
import { ProtocolError, type InspectResult, type Target } from "../types.js";
import { PublicationProviderFailure, type AdmissionResult, type PublicationProvider, type PublicationTree } from "../publication.js";

const sameTarget=(a:Target,b:Target)=>a.kind===b.kind&&a.authority===b.authority&&a.resource===b.resource&&a.namespace===b.namespace;
const cmp=(a:string,b:string)=>{const x=new TextEncoder().encode(a),y=new TextEncoder().encode(b),n=Math.min(x.length,y.length);for(let i=0;i<n;i++)if(x[i]!==y[i])return x[i]!-y[i]!;return x.length-y.length;};

export class LocalGitPublicationProvider implements PublicationProvider {
  constructor(private readonly repo:string,private readonly configured:Target){}
  private check(t:Target){if(!sameTarget(t,this.configured))throw new ProtocolError("FORBIDDEN");}
  private run(args:string[],opts:any={}):any {try{return execFileSync("git",["-C",this.repo,...args],{stdio:[opts.input===undefined?"ignore":"pipe","pipe","pipe"],...opts});}catch(e){throw e;}}
  private utf8(bytes:Uint8Array):string {try{return new TextDecoder("utf-8",{fatal:true}).decode(bytes);}catch{throw new ProtocolError("INVALID_SOURCE");}}
  async resolve(t:Target):Promise<string>{
    this.check(t);try{return typedGitOid(String(this.run(["show-ref","--verify","--hash",t.namespace],{encoding:"utf8"})).trim());}catch{throw new ProtocolError("NOT_FOUND");}
  }
  async inspect(t:Target,snapshot:string):Promise<InspectResult>{
    this.check(t);const oid=rawOid(snapshot);let type:string;try{type=String(this.run(["cat-file","-t",oid],{encoding:"utf8"})).trim();}catch{throw new ProtocolError("SNAPSHOT_UNAVAILABLE");}
    if(type!=="commit")return {id:snapshot,type};
    let raw:Uint8Array;try{raw=this.run(["cat-file","commit",oid]) as Uint8Array;}catch{throw new ProtocolError("SNAPSHOT_UNAVAILABLE");}
    let split=-1;for(let i=0;i+1<raw.length;i++)if(raw[i]===10&&raw[i+1]===10){split=i;break;}if(split<0)throw new ProtocolError("INVALID_SOURCE");
    const header=this.utf8(raw.slice(0,split));const message=this.utf8(raw.slice(split+2));const parents=[...header.matchAll(/^parent ([0-9a-f]+)$/gm)].map(m=>typedGitOid(m[1]!));
    return {id:snapshot,type:"commit",parents,message};
  }
  async tree(t:Target,snapshot:string):Promise<PublicationTree>{
    this.check(t);const oid=rawOid(snapshot);let raw:Uint8Array;try{raw=this.run(["ls-tree","-r","-z","--full-tree",oid]) as Uint8Array;}catch{throw new ProtocolError("SNAPSHOT_UNAVAILABLE");}
    const out:PublicationTree={};let start=0;
    for(let i=0;i<=raw.length;i++)if(i===raw.length||raw[i]===0){if(i===start){start=i+1;continue;}const rec=this.utf8(raw.slice(start,i));start=i+1;const tab=rec.indexOf("\t"),head=tab>=0?rec.slice(0,tab):"",path=tab>=0?rec.slice(tab+1):"";const m=/^(\d{6}) (blob|commit) ([0-9a-f]+)$/.exec(head);if(!m||!path)throw new ProtocolError("INVALID_SOURCE");const mode=m[1]!,kind=m[2]!,entryOid=m[3]!;
      if(kind==="commit"){if(mode!=="160000")throw new ProtocolError("INVALID_SOURCE");out[path]={base64:Buffer.from(entryOid,"utf8").toString("base64"),mode};}
      else {let bytes:Uint8Array;try{bytes=this.run(["cat-file","blob",entryOid]) as Uint8Array;}catch{throw new ProtocolError("SNAPSHOT_UNAVAILABLE");}out[path]={base64:Buffer.from(bytes).toString("base64"),mode};}
    }
    return out;
  }
  async admit(t:Target,expected:string,candidate:PublicationTree,message:string):Promise<AdmissionResult>{
    this.check(t);const expectedRaw=rawOid(expected),dir=mkdtempSync(join(tmpdir(),"stateowl-r3-index-")),index=join(dir,"index");const env={...process.env,GIT_INDEX_FILE:index};
    let candidateRaw:string|undefined;
    try{
      this.run(["read-tree","--empty"],{env});
      for(const path of Object.keys(candidate).sort(cmp)){
        const e=candidate[path]!;let object:string;
        if(e.mode==="160000"){
          let bytes:Uint8Array;try{bytes=canonicalBase64(e.base64);}catch{throw new ProtocolError("INVALID_SOURCE");}const text=this.utf8(bytes);if(!/^[0-9a-f]{40}$|^[0-9a-f]{64}$/.test(text))throw new ProtocolError("INVALID_SOURCE");object=text;
        } else {
          if(!["100644","100755","120000"].includes(e.mode))throw new ProtocolError("INVALID_SOURCE");let bytes:Uint8Array;try{bytes=canonicalBase64(e.base64);}catch{throw new ProtocolError("INVALID_SOURCE");}
          try{object=String(this.run(["hash-object","-w","--stdin"],{input:bytes,encoding:"utf8",env})).trim();}catch{throw new ProtocolError("PROVIDER_UNAVAILABLE");}
        }
        try{this.run(["update-index","--add","--cacheinfo",`${e.mode},${object},${path}`],{env});}catch{throw new ProtocolError("PROVIDER_UNAVAILABLE");}
      }
      let tree:string;try{tree=String(this.run(["write-tree"],{encoding:"utf8",env})).trim();}catch{throw new ProtocolError("PROVIDER_UNAVAILABLE");}
      try{candidateRaw=String(this.run(["commit-tree",tree,"-p",expectedRaw],{input:message,encoding:"utf8",env})).trim();}catch{throw new ProtocolError("PROVIDER_UNAVAILABLE");}
      const typed=typedGitOid(candidateRaw);const meta=await this.inspect(t,typed);if(meta.type!=="commit")throw new ProtocolError("INTEGRITY_MISMATCH");const parents=(meta as {parents?:string[]}).parents,messageRead=(meta as {message?:string}).message;if(!parents||parents.length!==1||parents[0]!==expected||messageRead!==message)throw new ProtocolError("INTEGRITY_MISMATCH");
      try{this.run(["update-ref",t.namespace,candidateRaw,expectedRaw]);}
      catch{
        try{const head=await this.resolve(t);if(head===typed)return {status:"admitted",snapshot:typed};if(head!==expected)return {status:"conflict"};throw new ProtocolError("PROVIDER_UNAVAILABLE");}
        catch(e){if(e instanceof ProtocolError&&e.code==="PROVIDER_UNAVAILABLE")throw e;throw new PublicationProviderFailure("PROVIDER_UNAVAILABLE",true);}
      }
      return {status:"admitted",snapshot:typed};
    } finally {rmSync(dir,{recursive:true,force:true});}
  }
}