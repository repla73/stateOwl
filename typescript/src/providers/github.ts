import { ProtocolError, type AccessResult, type InspectResult, type ProviderFile, type ReadProvider, type Target } from "../types.js";
import { sha256 } from "../encoding.js";
import { typedGitOid, rawOid } from "../git.js";

export type GitHubTransport=(path:string)=>Promise<any>;
export class GitHubReadProvider implements ReadProvider {
  constructor(private transport:GitHubTransport,private allowed:Set<string>){ }
  private repo(t:Target){if(t.kind!=="git"||t.authority!=="github.com"||!this.allowed.has(t.resource))throw new ProtocolError("FORBIDDEN");return t.resource;}
  private async probe(path:string):Promise<any|undefined>{try{return await this.transport(path)}catch(e:any){if(e?.status===404)return undefined;if(e?.status===401)throw new ProtocolError("UNAUTHENTICATED");if(e?.status===403)throw new ProtocolError("FORBIDDEN");throw new ProtocolError("PROVIDER_UNAVAILABLE")}}
  async access(t:Target,_op:"read"):Promise<AccessResult>{this.repo(t);return {validation:null,validator_available:true,project_authorized:true,continuity:"unknown",auth_scope:"github-read"};}
  async resolve(t:Target):Promise<string>{const repo=this.repo(t),ref=t.namespace.replace(/^refs\//,"");let r;try{r=await this.transport(`/repos/${repo}/git/ref/${encodeURIComponent(ref)}`)}catch(e:any){if(e?.status===404)throw new ProtocolError("NOT_FOUND");if(e?.status===401)throw new ProtocolError("UNAUTHENTICATED");if(e?.status===403)throw new ProtocolError("FORBIDDEN");throw new ProtocolError("PROVIDER_UNAVAILABLE")};return typedGitOid(r.object?.sha);}
  async inspect(t:Target,snapshot:string):Promise<InspectResult>{const repo=this.repo(t),oid=rawOid(snapshot);
    const commit=await this.probe(`/repos/${repo}/git/commits/${oid}`);if(commit!==undefined){const parents=(commit.parents??[]).map((p:any)=>typedGitOid(p.sha));return {id:snapshot,type:"commit",parents};}
    const tag=await this.probe(`/repos/${repo}/git/tags/${oid}`);if(tag!==undefined)return {id:snapshot,type:"tag",target:typedGitOid(tag.object?.sha),target_type:tag.object?.type};
    const blob=await this.probe(`/repos/${repo}/git/blobs/${oid}`);if(blob!==undefined)return {id:snapshot,type:"blob"};
    const tree=await this.probe(`/repos/${repo}/git/trees/${oid}`);if(tree!==undefined)return {id:snapshot,type:"tree"};
    throw new ProtocolError("SNAPSHOT_UNAVAILABLE");
  }
  async file(t:Target,snapshot:string,path:string):Promise<ProviderFile>{const repo=this.repo(t),oid=rawOid(snapshot),encodedPath=path.split("/").map(x=>encodeURIComponent(x)).join("/");let c;try{c=await this.transport(`/repos/${repo}/contents/${encodedPath}?ref=${encodeURIComponent(oid)}`)}catch(e:any){if(e?.status===404)throw new ProtocolError("NOT_FOUND");if(e?.status===403)throw new ProtocolError("NOT_FOUND_OR_FORBIDDEN");throw new ProtocolError("PROVIDER_UNAVAILABLE")};if(c.type!=="file"||typeof c.content!=="string"||typeof c.sha!=="string")throw new ProtocolError("INVALID_SOURCE");const b64=c.content.replace(/\n/g,"");const bytes=Buffer.from(b64,"base64");return {base64:Buffer.from(bytes).toString("base64"),mode:c.executable?"100755":"100644",digest:sha256(bytes),integrity:"provider",object:typedGitOid(c.sha)};}
}

export function githubFetchTransport(token?:string):GitHubTransport {return async path=>{const r=await fetch(`https://api.github.com${path}`,{headers:{Accept:"application/vnd.github+json",...(token?{Authorization:`Bearer ${token}`}:{})}});if(!r.ok){const e:any=new Error(`GitHub ${r.status}`);e.status=r.status;throw e;}return r.json();};}
