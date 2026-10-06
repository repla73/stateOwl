import { createHash } from "node:crypto";
import { canonicalBase64 } from "../encoding.js";
import { rawOid, typedGitOid } from "../git.js";
import { ProtocolError, type ErrorCode, type InspectResult, type Target } from "../types.js";
import { PublicationProviderFailure, type AdmissionResult, type PublicationProvider, type PublicationTree } from "../publication.js";

export type GitHubRestTransport=(method:"GET"|"POST",path:string,body?:unknown)=>Promise<any>;
export type GitHubGraphQLTransport=(query:string,variables:Record<string,unknown>)=>Promise<any>;
const sameTarget=(a:Target,b:Target)=>a.kind===b.kind&&a.authority===b.authority&&a.resource===b.resource&&a.namespace===b.namespace;
const cmp=(a:string,b:string)=>{const x=new TextEncoder().encode(a),y=new TextEncoder().encode(b),n=Math.min(x.length,y.length);for(let i=0;i<n;i++)if(x[i]!==y[i])return x[i]!-y[i]!;return x.length-y.length;};
const statusCode=(status:number):ErrorCode=>status===401?"UNAUTHENTICATED":status===403?"FORBIDDEN":status===429?"RATE_LIMITED":status===404?"SNAPSHOT_UNAVAILABLE":status===409?"CONFLICT":"PROVIDER_UNAVAILABLE";

const RECEIPT_MARKER="StateOwl-Receipt:";
type CommitActor={name:string;email:string;seconds:number};
function commitActor(value:any):CommitActor {
  if(!value||typeof value.name!=="string"||typeof value.email!=="string"||typeof value.date!=="string"||/[\r\n\0]/.test(value.name)||/[\r\n\0]/.test(value.email))throw new ProtocolError("INTEGRITY_MISMATCH");
  const ms=Date.parse(value.date);if(!Number.isFinite(ms)||ms%1000!==0)throw new ProtocolError("INTEGRITY_MISMATCH");
  return {name:value.name,email:value.email,seconds:Math.trunc(ms/1000)};
}
function timezone(minutes:number):string {const sign=minutes<0?"-":"+",n=Math.abs(minutes);return `${sign}${String(Math.trunc(n/60)).padStart(2,"0")}${String(n%60).padStart(2,"0")}`;}
function commitHash(meta:any,oid:string,message:string,tz:string,author:CommitActor,committer:CommitActor):string {
  let body=`tree ${meta.tree.sha}\n`;for(const p of meta.parents)body+=`parent ${p.sha}\n`;
  body+=`author ${author.name} <${author.email}> ${author.seconds} ${tz}\ncommitter ${committer.name} <${committer.email}> ${committer.seconds} ${tz}\n\n${message}`;
  const bytes=new TextEncoder().encode(body),alg=/^[0-9a-f]{40}$/.test(oid)?"sha1":/^[0-9a-f]{64}$/.test(oid)?"sha256":null;
  if(!alg)throw new ProtocolError("INTEGRITY_MISMATCH");
  const h=createHash(alg);h.update(`commit ${bytes.byteLength}\0`);h.update(bytes);return h.digest("hex");
}
function exactMessages(meta:any,oid:string,messages:string[]):string[] {
  if(!meta||typeof meta?.tree?.sha!=="string"||!Array.isArray(meta.parents)||!meta.parents.every((p:any)=>typeof p?.sha==="string")||meta?.verification?.reason!=="unsigned"||meta?.verification?.signature!==null)throw new ProtocolError("INTEGRITY_MISMATCH");
  if(typeof meta?.sha==="string"&&meta.sha!==oid)throw new ProtocolError("INTEGRITY_MISMATCH");
  const author=commitActor(meta.author),committer=commitActor(meta.committer),unique=[...new Set(messages)],matches:string[]=[];
  // GitHub's JSON timestamp is UTC-normalized and does not retain the raw Git timezone. Search the bounded real-world offset space; only the full commit OID can admit a byte hypothesis.
  for(let minutes=-14*60;minutes<=14*60;minutes++){const tz=timezone(minutes);for(const message of unique)if(commitHash(meta,oid,message,tz,author,committer)===oid)matches.push(message);}
  return matches;
}
function proveExactCommitMessage(meta:any,oid:string,message:string):string {
  const matches=exactMessages(meta,oid,[message]);if(matches.length!==1)throw new ProtocolError("INTEGRITY_MISMATCH");return message;
}
function recoverExactReceiptMessage(meta:any,oid:string):string {
  if(typeof meta?.message!=="string")throw new ProtocolError("INVALID_SOURCE");
  // GitHub may omit one terminal LF in JSON. The LF form is only a hypothesis; the full Git object OID must prove the exact bytes.
  const matches=exactMessages(meta,oid,[meta.message,meta.message+"\n"]);if(matches.length!==1)throw new ProtocolError("INTEGRITY_MISMATCH");return matches[0]!;
}

export class GitHubPublicationProvider implements PublicationProvider {
  private repoNode=new Map<string,string>();
  constructor(private readonly rest:GitHubRestTransport,private readonly graphql:GitHubGraphQLTransport,private readonly allowed:Set<string>){ }
  private repo(t:Target):string {if(t.kind!=="git"||t.authority!=="github.com"||!t.namespace.startsWith("refs/heads/")||!this.allowed.has(t.resource))throw new ProtocolError("FORBIDDEN");return t.resource;}
  private async get(path:string,notFound:ErrorCode="SNAPSHOT_UNAVAILABLE"):Promise<any>{try{return await this.rest("GET",path);}catch(e:any){if(e instanceof ProtocolError)throw e;if(e?.status===404)throw new ProtocolError(notFound);throw new ProtocolError(statusCode(e?.status??0));}}
  private async post(path:string,body:unknown):Promise<any>{try{return await this.rest("POST",path,body);}catch(e:any){if(e instanceof ProtocolError)throw e;throw new ProtocolError(statusCode(e?.status??0));}}
  async resolve(t:Target):Promise<string>{const repo=this.repo(t),ref=t.namespace.replace(/^refs\//,"");const r=await this.get(`/repos/${repo}/git/ref/${encodeURIComponent(ref)}`,"NOT_FOUND");if(typeof r?.object?.sha!=="string")throw new ProtocolError("INVALID_SOURCE");return typedGitOid(r.object.sha);}
  async inspect(t:Target,snapshot:string):Promise<InspectResult>{const repo=this.repo(t),oid=rawOid(snapshot),c=await this.get(`/repos/${repo}/git/commits/${oid}`);if(typeof c?.sha==="string"&&c.sha!==oid)throw new ProtocolError("INTEGRITY_MISMATCH");if(!Array.isArray(c?.parents)||typeof c?.message!=="string")throw new ProtocolError("INVALID_SOURCE");const message=c.message.includes(RECEIPT_MARKER)?recoverExactReceiptMessage(c,oid):c.message;return {id:snapshot,type:"commit",parents:c.parents.map((p:any)=>typedGitOid(p.sha)),message};}
  private async blob(repo:string,sha:string):Promise<string>{const b=await this.get(`/repos/${repo}/git/blobs/${sha}`);if(typeof b?.content!=="string"||b.encoding!=="base64")throw new ProtocolError("INVALID_SOURCE");const compact=b.content.replace(/\n/g,"");let raw:Uint8Array;try{raw=canonicalBase64(compact);}catch{throw new ProtocolError("INVALID_SOURCE");}return Buffer.from(raw).toString("base64");}
  private async walkTree(repo:string,treeSha:string,prefix:string,out:PublicationTree,depth:number):Promise<void>{
    if(depth>256)throw new ProtocolError("LIMIT_EXCEEDED");const r=await this.get(`/repos/${repo}/git/trees/${treeSha}`);if(r?.truncated===true)throw new ProtocolError("INVALID_SOURCE");if(!Array.isArray(r?.tree))throw new ProtocolError("INVALID_SOURCE");
    for(const e of r.tree){if(typeof e?.path!=="string"||typeof e?.mode!=="string"||typeof e?.type!=="string"||typeof e?.sha!=="string")throw new ProtocolError("INVALID_SOURCE");const path=prefix?`${prefix}/${e.path}`:e.path;
      if(e.type==="tree")await this.walkTree(repo,e.sha,path,out,depth+1);
      else if(e.type==="blob")out[path]={base64:await this.blob(repo,e.sha),mode:e.mode};
      else if(e.type==="commit"&&e.mode==="160000")out[path]={base64:Buffer.from(e.sha,"utf8").toString("base64"),mode:e.mode};
      else throw new ProtocolError("INVALID_SOURCE");
    }
  }
  async tree(t:Target,snapshot:string):Promise<PublicationTree>{const repo=this.repo(t),oid=rawOid(snapshot),c=await this.get(`/repos/${repo}/git/commits/${oid}`);if(typeof c?.tree?.sha!=="string")throw new ProtocolError("INVALID_SOURCE");const out:PublicationTree={};await this.walkTree(repo,c.tree.sha,"",out,0);return out;}
  private async nodeId(repo:string):Promise<string>{const cached=this.repoNode.get(repo);if(cached)return cached;const r=await this.get(`/repos/${repo}`,"NOT_FOUND");if(typeof r?.node_id!=="string"||!r.node_id)throw new ProtocolError("INVALID_SOURCE");this.repoNode.set(repo,r.node_id);return r.node_id;}
  async admit(t:Target,expected:string,candidate:PublicationTree,message:string):Promise<AdmissionResult>{
    const repo=this.repo(t),expectedRaw=rawOid(expected),entries:any[]=[];
    for(const path of Object.keys(candidate).sort(cmp)){
      const e=candidate[path]!;
      if(e.mode==="160000"){
        let bytes:Uint8Array;try{bytes=canonicalBase64(e.base64);}catch{throw new ProtocolError("INVALID_SOURCE");}let sha:string;try{sha=new TextDecoder("utf-8",{fatal:true}).decode(bytes);}catch{throw new ProtocolError("INVALID_SOURCE");}if(!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(sha))throw new ProtocolError("INVALID_SOURCE");entries.push({path,mode:e.mode,type:"commit",sha});
      } else {
        if(!["100644","100755","120000"].includes(e.mode))throw new ProtocolError("INVALID_SOURCE");let raw:Uint8Array;try{raw=canonicalBase64(e.base64);}catch{throw new ProtocolError("INVALID_SOURCE");}
        const blob=await this.post(`/repos/${repo}/git/blobs`,{content:Buffer.from(raw).toString("base64"),encoding:"base64"});if(typeof blob?.sha!=="string")throw new ProtocolError("INVALID_SOURCE");entries.push({path,mode:e.mode,type:"blob",sha:blob.sha});
      }
    }
    const tree=await this.post(`/repos/${repo}/git/trees`,{tree:entries});if(typeof tree?.sha!=="string")throw new ProtocolError("INVALID_SOURCE");
    const commit=await this.post(`/repos/${repo}/git/commits`,{message,tree:tree.sha,parents:[expectedRaw]});if(typeof commit?.sha!=="string")throw new ProtocolError("INVALID_SOURCE");const typed=typedGitOid(commit.sha);
    const check=await this.get(`/repos/${repo}/git/commits/${commit.sha}`);if(check?.tree?.sha!==tree.sha||!Array.isArray(check?.parents)||check.parents.length!==1||check.parents[0]?.sha!==expectedRaw)throw new ProtocolError("INTEGRITY_MISMATCH");proveExactCommitMessage(check,commit.sha,message);
    const repositoryId=await this.nodeId(repo);
    const query=`mutation StateOwlUpdateRefs($input: UpdateRefsInput!) { updateRefs(input: $input) { clientMutationId } }`;
    let response:any;
    try{response=await this.graphql(query,{input:{repositoryId,refUpdates:[{name:t.namespace,beforeOid:expectedRaw,afterOid:commit.sha,force:false}]}});}
    catch{throw new PublicationProviderFailure("PROVIDER_UNAVAILABLE",true);}
    if(Array.isArray(response?.errors)&&response.errors.length){
      try{const head=await this.resolve(t);if(head===typed)return {status:"admitted",snapshot:typed};if(head!==expected)return {status:"conflict"};}catch(e){if(e instanceof ProtocolError&&e.code!=="NOT_FOUND")throw new PublicationProviderFailure(e.code,true);}
      const text=JSON.stringify(response.errors);if(/FORBIDDEN|permission|Resource not accessible/i.test(text))throw new ProtocolError("FORBIDDEN");if(/rate/i.test(text))throw new ProtocolError("RATE_LIMITED");if(/expected|beforeOid|not a fast forward|head/i.test(text))return {status:"conflict"};throw new ProtocolError("PROVIDER_UNAVAILABLE");
    }
    return {status:"admitted",snapshot:typed};
  }
}

export function githubPublicationFetchTransports(token?:string):{rest:GitHubRestTransport;graphql:GitHubGraphQLTransport}{
  const headers={Accept:"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",...(token?{Authorization:`Bearer ${token}`}:{})};
  const rest:GitHubRestTransport=async(method,path,body)=>{const r=await fetch(`https://api.github.com${path}`,{method,headers:{...headers,"Content-Type":"application/json"},...(body===undefined?{}:{body:JSON.stringify(body)})});if(!r.ok){const e:any=new Error(`GitHub ${r.status}`);e.status=r.status;throw e;}return r.json();};
  const graphql:GitHubGraphQLTransport=async(query,variables)=>{const r=await fetch("https://api.github.com/graphql",{method:"POST",headers:{...headers,"Content-Type":"application/json"},body:JSON.stringify({query,variables})});if(!r.ok){const e:any=new Error(`GitHub ${r.status}`);e.status=r.status;throw e;}return r.json();};
  return {rest,graphql};
}