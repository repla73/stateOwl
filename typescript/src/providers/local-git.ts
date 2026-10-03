import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { ProtocolError, type AccessResult, type InspectResult, type ProviderFile, type ReadProvider, type Target } from "../types.js";
import { typedGitOid, rawOid } from "../git.js";
import { sha256 } from "../encoding.js";

export class LocalGitProvider implements ReadProvider {
  constructor(private repo:string,private configured:Target){}
  private check(t:Target){if(JSON.stringify(t)!==JSON.stringify(this.configured))throw new ProtocolError("FORBIDDEN")}
  private run(args:string[],encoding?:"utf8"):any{try{return execFileSync("git",["-C",this.repo,...args],{encoding:encoding??undefined,stdio:["ignore","pipe","pipe"]})}catch(e:any){throw new ProtocolError("SNAPSHOT_UNAVAILABLE")}}
  async access(t:Target,_op:"read"):Promise<AccessResult>{this.check(t);return {validation:null,validator_available:true,project_authorized:true,continuity:"unknown",auth_scope:"local"};}
  async resolve(t:Target):Promise<string>{this.check(t);try{const oid=String(this.run(["rev-parse","--verify",t.namespace],"utf8")).trim();return typedGitOid(oid)}catch{throw new ProtocolError("NOT_FOUND")}}
  async inspect(t:Target,snapshot:string):Promise<InspectResult>{this.check(t);const oid=rawOid(snapshot);let type:string;try{type=String(this.run(["cat-file","-t",oid],"utf8")).trim()}catch{throw new ProtocolError("SNAPSHOT_UNAVAILABLE")};if(type==="commit"){const raw=String(this.run(["cat-file","-p",oid],"utf8"));const parents=[...raw.matchAll(/^parent ([0-9a-f]+)$/gm)].map(m=>typedGitOid(m[1]!));return {id:snapshot,type:"commit",parents};}if(type==="tag"){const raw=String(this.run(["cat-file","-p",oid],"utf8"));const object=/^object ([0-9a-f]+)$/m.exec(raw)?.[1],targetType=/^type (\S+)$/m.exec(raw)?.[1];return {id:snapshot,type:"tag",target:object?typedGitOid(object):undefined,target_type:targetType};}return {id:snapshot,type};}
  async file(t:Target,snapshot:string,path:string):Promise<ProviderFile>{this.check(t);const oid=rawOid(snapshot);let line:string;try{line=String(this.run(["ls-tree",oid,"--",path],"utf8")).trim()}catch{throw new ProtocolError("SNAPSHOT_UNAVAILABLE")};if(!line)throw new ProtocolError("NOT_FOUND");const m=/^(\d{6}) blob ([0-9a-f]+)\t/.exec(line);if(!m)throw new ProtocolError("INVALID_SOURCE");const bytes=this.run(["cat-file","blob",m[2]!]) as Uint8Array;return {base64:Buffer.from(bytes).toString("base64"),mode:m[1]!,digest:sha256(bytes),integrity:"object_chain",object:typedGitOid(m[2]!)};}
}
