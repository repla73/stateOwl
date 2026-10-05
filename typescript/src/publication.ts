import { canonicalBase64, canonicalJson, parseStrictJson, sha256 } from "./encoding.js";
import { gitAlgorithm, validateGitTarget } from "./git.js";
import { PROTOCOL, ProtocolError, type Capabilities, type ErrorCode, type InspectResult, type Json, type Target } from "./types.js";

export type PublicationFile = { base64: string; mode: string };
export type PublicationTree = Record<string, PublicationFile>;
export type PublicationChange = { path: string; put: { encoding: "utf8" | "base64"; data: string } } | { path: string; delete: true };
export type PublishRequest = {
  protocol: typeof PROTOCOL;
  op: "publish";
  target: Target;
  expected: { id: string };
  mode: "submit" | "reconcile";
  validation: string | null;
  changes: PublicationChange[];
};
export type IdentityChange = { path: string; put: { digest: string; bytes: number } } | { path: string; delete: true };
export type PublicationIdentity = {
  protocol: typeof PROTOCOL;
  target: Target;
  expected: { id: string };
  changes: IdentityChange[];
  validation: string | null;
};
export type PublicationAccess = {
  validation: string | null;
  validator_available: boolean;
  project_authorized: boolean;
  continuity: "intact" | "unknown" | "reset";
  auth_scope: string;
};
export interface ProjectValidationBoundary {
  access(target: Target, operation: "publish"): Promise<PublicationAccess>;
  authorize(target: Target, operation: "publish", paths: string[]): Promise<boolean>;
  validate(target: Target, expected: string, binding: string, oldState: PublicationTree, candidate: PublicationTree): Promise<boolean>;
}
export type AdmissionResult = { status: "conflict" } | { status: "admitted"; snapshot: string };
export interface PublicationProvider {
  resolve(target: Target): Promise<string>;
  inspect(target: Target, snapshot: string): Promise<InspectResult>;
  tree(target: Target, snapshot: string): Promise<PublicationTree>;
  admit(target: Target, expected: string, candidate: PublicationTree, message: string): Promise<AdmissionResult>;
}
export class PublicationProviderFailure extends ProtocolError {
  constructor(code: ErrorCode, public dispatched = false) { super(code); }
}

type PreparedChange = { path: string; delete: true } | { path: string; put: { bytes: Uint8Array; digest: string } };
type Prepared = { request: PublishRequest; changes: PreparedChange[]; identity: PublicationIdentity; identityBytes: Uint8Array; requestDigest: string };

const RETRY: Record<ErrorCode, "after_correction"|"after_refresh"|"after_backoff"|"never"> = {
  INVALID_REQUEST:"after_correction", NOT_FOUND:"after_correction", EXACT_SNAPSHOT_REQUIRED:"after_correction", INVALID_SOURCE:"after_correction", NUMBER_UNREPRESENTABLE:"after_correction", LIMIT_EXCEEDED:"after_correction", VALIDATION_FAILED:"after_correction",
  UNAUTHENTICATED:"after_refresh", CONFLICT:"after_refresh", NAMESPACE_DISCONTINUITY:"after_refresh", TOKEN_INVALID:"after_refresh",
  RATE_LIMITED:"after_backoff", PROVIDER_UNAVAILABLE:"after_backoff",
  UNSUPPORTED_VERSION:"never", UNSUPPORTED_CAPABILITY:"never", FORBIDDEN:"never", NOT_FOUND_OR_FORBIDDEN:"never", SNAPSHOT_UNAVAILABLE:"never", INTEGRITY_MISMATCH:"never", NO_CHANGE:"never", HISTORY_UNAVAILABLE:"never"
};

const isObj=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==="object"&&!Array.isArray(x);
const keysExact=(o:Record<string,unknown>, allowed:string[])=>Object.keys(o).every(k=>allowed.includes(k));
const scalarOk=(s:string):boolean=>{for(let i=0;i<s.length;i++){const c=s.charCodeAt(i);if(c>=0xd800&&c<=0xdbff){const d=s.charCodeAt(++i);if(!(d>=0xdc00&&d<=0xdfff))return false;}else if(c>=0xdc00&&c<=0xdfff)return false;}return true;};
const validPath=(p:unknown):p is string=>typeof p==="string"&&scalarOk(p)&&p.length>0&&!p.startsWith("/")&&!p.endsWith("/")&&!p.includes("\\")&&!/[\x00-\x1f\x7f]/.test(p)&&p.split("/").every(x=>x!==""&&x!=="."&&x!=="..");
const bindingOk=(x:unknown):x is string=>typeof x==="string"&&x.length>=1&&x.length<=256&&/^[!-~]+$/.test(x);
const bytesCmp=(a:string,b:string)=>{const x=new TextEncoder().encode(a),y=new TextEncoder().encode(b),n=Math.min(x.length,y.length);for(let i=0;i<n;i++){if(x[i]!==y[i])return x[i]!-y[i]!;}return x.length-y.length;};
const sortedPaths=(paths:string[])=>[...paths].sort(bytesCmp);
const hasCollision=(paths:string[])=>{const s=new Set(paths);if(s.size!==paths.length)return true;for(const p of paths){const a=p.split("/");for(let i=1;i<a.length;i++)if(s.has(a.slice(0,i).join("/")))return true;}return false;};
const sameTree=(a:PublicationTree,b:PublicationTree)=>{const ak=Object.keys(a).sort(bytesCmp),bk=Object.keys(b).sort(bytesCmp);if(ak.length!==bk.length||ak.some((k,i)=>k!==bk[i]))return false;return ak.every(k=>a[k]!.base64===b[k]!.base64&&a[k]!.mode===b[k]!.mode);};
const errorObject=(code:ErrorCode, uncertain=false)=>({code,retry:uncertain?"reconcile":RETRY[code]});
const operationError=(code:ErrorCode)=>({protocol:PROTOCOL,op:"unknown",status:"error",error:errorObject(code)});
const toCode=(e:unknown):ErrorCode=>e instanceof ProtocolError?e.code:"PROVIDER_UNAVAILABLE";

function targetOk(x:unknown): x is Target {
  return isObj(x)&&keysExact(x,["kind","authority","resource","namespace"])&&[x.kind,x.authority,x.resource,x.namespace].every(v=>typeof v==="string"&&v.length>0&&scalarOk(v));
}
function validateNativeJson(x:unknown): void {
  if(x===null||typeof x==="boolean")return;
  if(typeof x==="string"){if(!scalarOk(x))throw new ProtocolError("INVALID_REQUEST");return;}
  if(typeof x==="number"){if(!Number.isFinite(x)||Object.is(x,-0)||!Number.isSafeInteger(x)&&Number.isInteger(x))throw new ProtocolError(Number.isFinite(x)?"NUMBER_UNREPRESENTABLE":"INVALID_REQUEST");return;}
  if(Array.isArray(x)){for(const v of x)validateNativeJson(v);return;}
  if(isObj(x)){for(const [k,v] of Object.entries(x)){if(!scalarOk(k))throw new ProtocolError("INVALID_REQUEST");validateNativeJson(v);}return;}
  throw new ProtocolError("INVALID_REQUEST");
}
function decodePut(put:unknown):Uint8Array {
  if(!isObj(put)||!keysExact(put,["encoding","data"])||!(["utf8","base64"] as unknown[]).includes(put.encoding)||typeof put.data!=="string"||!scalarOk(put.data))throw new ProtocolError("INVALID_REQUEST");
  if(put.encoding==="utf8")return new TextEncoder().encode(put.data);
  try{return canonicalBase64(put.data);}catch(e){if(e instanceof ProtocolError)throw new ProtocolError("INVALID_REQUEST");throw e;}
}
function validateRequestObject(r:unknown): asserts r is PublishRequest {
  if(!isObj(r)||typeof r.protocol!=="string")throw new ProtocolError("INVALID_REQUEST");
  if(r.protocol!==PROTOCOL)throw new ProtocolError("UNSUPPORTED_VERSION");
  if(!keysExact(r,["protocol","op","target","expected","mode","validation","changes"])||r.op!=="publish"||!targetOk(r.target))throw new ProtocolError("INVALID_REQUEST");
  validateGitTarget(r.target);
  if(!isObj(r.expected)||!keysExact(r.expected,["id"])||typeof r.expected.id!=="string"||!r.expected.id||!scalarOk(r.expected.id))throw new ProtocolError("INVALID_REQUEST");
  if(r.mode!=="submit"&&r.mode!=="reconcile")throw new ProtocolError("INVALID_REQUEST");
  if(r.validation!==null&&!bindingOk(r.validation))throw new ProtocolError("INVALID_REQUEST");
  if(!Array.isArray(r.changes)||r.changes.length<1)throw new ProtocolError("INVALID_REQUEST");
  const paths:string[]=[];
  for(const c of r.changes){
    if(!isObj(c)||!validPath(c.path))throw new ProtocolError("INVALID_REQUEST");
    const hasPut="put" in c,hasDelete="delete" in c;if(hasPut===hasDelete)throw new ProtocolError("INVALID_REQUEST");
    if(hasPut){if(!keysExact(c,["path","put"]))throw new ProtocolError("INVALID_REQUEST");decodePut(c.put);}
    else if(!keysExact(c,["path","delete"])||c.delete!==true)throw new ProtocolError("INVALID_REQUEST");
    paths.push(c.path);
  }
  if(hasCollision(paths))throw new ProtocolError("INVALID_REQUEST");
}
function validateIdentity(x:unknown): asserts x is PublicationIdentity {
  if(!isObj(x)||!keysExact(x,["protocol","target","expected","changes","validation"])||x.protocol!==PROTOCOL||!targetOk(x.target))throw new ProtocolError("INVALID_SOURCE");
  if(!isObj(x.expected)||!keysExact(x.expected,["id"])||typeof x.expected.id!=="string"||!x.expected.id)throw new ProtocolError("INVALID_SOURCE");
  if(x.validation!==null&&!bindingOk(x.validation))throw new ProtocolError("INVALID_SOURCE");
  if(!Array.isArray(x.changes)||x.changes.length<1)throw new ProtocolError("INVALID_SOURCE");
  const paths:string[]=[];
  for(const c of x.changes){
    if(!isObj(c)||!validPath(c.path))throw new ProtocolError("INVALID_SOURCE");
    if("delete" in c){if(!keysExact(c,["path","delete"])||c.delete!==true)throw new ProtocolError("INVALID_SOURCE");}
    else if("put" in c){const p=c.put;if(!keysExact(c,["path","put"])||!isObj(p)||!keysExact(p,["digest","bytes"])||typeof p.digest!=="string"||!/^sha256:[0-9a-f]{64}$/.test(p.digest)||typeof p.bytes!=="number"||!Number.isSafeInteger(p.bytes)||p.bytes<0)throw new ProtocolError("INVALID_SOURCE");}
    else throw new ProtocolError("INVALID_SOURCE");
    paths.push(c.path);
  }
  if(hasCollision(paths)||paths.some((p,i)=>i>0&&bytesCmp(paths[i-1]!,p)>=0))throw new ProtocolError("INVALID_SOURCE");
}

export function publicationIdentity(request: PublishRequest): { identity: PublicationIdentity; bytes: Uint8Array; digest: string } {
  validateRequestObject(request);
  const normalized:IdentityChange[]=request.changes.map((c):IdentityChange=>{
    if("delete" in c)return {path:c.path,delete:true};
    const b=decodePut(c.put);return {path:c.path,put:{digest:sha256(b),bytes:b.byteLength}};
  }).sort((a,b)=>bytesCmp(a.path,b.path));
  const identity:PublicationIdentity={protocol:PROTOCOL,target:structuredClone(request.target),expected:{id:request.expected.id},changes:normalized,validation:request.validation};
  const bytes=new TextEncoder().encode(canonicalJson(identity as unknown as Json));
  return {identity,bytes,digest:sha256(bytes)};
}
export function receiptMessage(identity:PublicationIdentity, heading=true):string {
  validateIdentity(identity);
  const bytes=new TextEncoder().encode(canonicalJson(identity as unknown as Json));
  const b64=Buffer.from(bytes).toString("base64");
  return `${heading?"stateOwl publication\n\n":""}StateOwl-Receipt: ${b64}\n`;
}
export function parseReceipt(message:string):PublicationIdentity|null {
  if(typeof message!=="string")throw new ProtocolError("INVALID_SOURCE");
  const marker="StateOwl-Receipt:";
  if(!message.includes(marker))return null;
  const m=/^(?:stateOwl publication\n\n)?StateOwl-Receipt: ([A-Za-z0-9+/]+={0,2})\n$/.exec(message);
  if(!m)throw new ProtocolError("INVALID_SOURCE");
  let bytes:Uint8Array;try{bytes=canonicalBase64(m[1]!);}catch{throw new ProtocolError("INVALID_SOURCE");}
  let parsed:Json;try{parsed=parseStrictJson(bytes,64);}catch{throw new ProtocolError("INVALID_SOURCE");}
  try{validateIdentity(parsed);}catch{throw new ProtocolError("INVALID_SOURCE");}
  const canonical=new TextEncoder().encode(canonicalJson(parsed));
  if(canonical.byteLength!==bytes.byteLength||canonical.some((v,i)=>v!==bytes[i]))throw new ProtocolError("INVALID_SOURCE");
  return parsed as PublicationIdentity;
}

export class Publisher {
  private prepared:Prepared|null=null;
  private admitted:string|null=null;
  private wasDispatched=false;
  private accessResult:PublicationAccess|null=null;
  constructor(private provider:PublicationProvider, private validation:ProjectValidationBoundary, public capabilities:Capabilities){}

  async publish(input:PublishRequest|string|Uint8Array):Promise<any>{
    this.prepared=null;this.admitted=null;this.wasDispatched=false;this.accessResult=null;
    let request:unknown, raw:Uint8Array;
    try{
      if(typeof input==="string")raw=new TextEncoder().encode(input);
      else if(input instanceof Uint8Array)raw=input;
      else {validateNativeJson(input);raw=new TextEncoder().encode(canonicalJson(input as unknown as Json));}
      if(raw.byteLength>this.capabilities.limits.request_bytes)throw new ProtocolError("LIMIT_EXCEEDED");
      try{request=parseStrictJson(raw,this.capabilities.limits.json_depth);}catch(e){if(e instanceof ProtocolError&&e.code==="INVALID_SOURCE")throw new ProtocolError("INVALID_REQUEST");throw e;}
      validateRequestObject(request);
      const r=request as PublishRequest;
      if(r.changes.length>this.capabilities.limits.changes)throw new ProtocolError("LIMIT_EXCEEDED");
      const changes:PreparedChange[]=[];let mutation=0;
      for(const c of r.changes){if("delete" in c)changes.push({path:c.path,delete:true});else{const bytes=decodePut(c.put);if(bytes.byteLength>this.capabilities.limits.record_bytes)throw new ProtocolError("LIMIT_EXCEEDED");mutation+=bytes.byteLength;changes.push({path:c.path,put:{bytes,digest:sha256(bytes)}});}}
      if(mutation>this.capabilities.limits.mutation_bytes)throw new ProtocolError("LIMIT_EXCEEDED");
      changes.sort((a,b)=>bytesCmp(a.path,b.path));
      const pi=publicationIdentity(r);
      this.prepared={request:r,changes,identity:pi.identity,identityBytes:pi.bytes,requestDigest:pi.digest};
    }catch(e){return operationError(toCode(e));}

    try{
      const r=this.prepared.request;
      if(!this.capabilities.operations.includes("publish")||!this.capabilities.publication||this.capabilities.publication.continuity!=="single_step_required"||this.capabilities.publication.receipt_format!=="stateowl.git-receipt/2"||this.capabilities.publication.receipt_retention!=="reachable_history"||!["mechanical","project_validated"].includes(this.capabilities.publication.authority))throw new ProtocolError("UNSUPPORTED_CAPABILITY");
      this.accessResult=await this.access(r.target);
      if(r.target.kind==="git"&&!r.target.namespace.startsWith("refs/heads/"))throw new ProtocolError("UNSUPPORTED_CAPABILITY");
      await this.authorize(r.target,this.prepared.changes.map(c=>c.path));
      if(this.accessResult.continuity!=="intact")throw new ProtocolError("NAMESPACE_DISCONTINUITY");
      let result:any;
      if(r.mode==="reconcile")result=await this.reconcile();
      else result=await this.submit();
      return this.finalize(result);
    }catch(e){
      if(e instanceof PublicationProviderFailure&&e.dispatched)this.wasDispatched=true;
      return this.finalize(this.failure(toCode(e)));
    }
  }

  private failure(code:ErrorCode):any {
    if(!this.prepared)return operationError(code);
    const r=this.prepared.request;
    const uncertain=!!this.admitted||this.wasDispatched||r.mode==="reconcile";
    if(this.admitted)return {protocol:PROTOCOL,op:"publish",outcome:"verification_pending",request_digest:this.prepared.requestDigest,snapshot:{id:this.admitted},error:errorObject(code,true)};
    if(uncertain)return {protocol:PROTOCOL,op:"publish",outcome:"indeterminate",request_digest:this.prepared.requestDigest,error:errorObject(code,true)};
    return {protocol:PROTOCOL,op:"publish",outcome:"not_committed",request_digest:this.prepared.requestDigest,error:errorObject(code,false)};
  }
  private finalize(result:any):any {
    try{if(Buffer.byteLength(canonicalJson(result as Json),"utf8")>this.capabilities.limits.response_bytes)return this.failure("LIMIT_EXCEEDED");}catch{return this.failure("INVALID_SOURCE");}
    return result;
  }
  private metadataLimit(value:unknown):void {let s:string;try{s=canonicalJson(value as Json);}catch{throw new ProtocolError("INVALID_SOURCE");}if(Buffer.byteLength(s,"utf8")>this.capabilities.limits.record_bytes)throw new ProtocolError("LIMIT_EXCEEDED");}
  private async access(target:Target):Promise<PublicationAccess>{
    const a=await this.validation.access(target,"publish");
    if(!isObj(a)||!keysExact(a,["validation","validator_available","project_authorized","continuity","auth_scope"])||(a.validation!==null&&!bindingOk(a.validation))||typeof a.validator_available!=="boolean"||typeof a.project_authorized!=="boolean"||!(a.continuity==="intact"||a.continuity==="unknown"||a.continuity==="reset")||typeof a.auth_scope!=="string"||!a.auth_scope||!scalarOk(a.auth_scope))throw new ProtocolError("INVALID_SOURCE");
    this.metadataLimit(a);return a;
  }
  private async authorize(target:Target,paths:string[]):Promise<void>{const ok=await this.validation.authorize(target,"publish",sortedPaths(paths));if(ok!==true)throw new ProtocolError("FORBIDDEN");}
  private async inspect(target:Target,snapshot:string):Promise<{id:string;type:string;parents?:string[];message?:string}>{
    if(target.kind==="git")gitAlgorithm(snapshot);
    const m=await this.provider.inspect(target,snapshot);
    if(!isObj(m)||typeof m.id!=="string"||m.id!==snapshot||typeof m.type!=="string"||!m.type)throw new ProtocolError(m&&isObj(m)&&m.id!==snapshot?"INTEGRITY_MISMATCH":"INVALID_SOURCE");
    if(m.type==="commit"){
      if(!keysExact(m,["id","type","parents","message"])||!Array.isArray(m.parents)||!m.parents.every(p=>typeof p==="string")||("message" in m&&typeof m.message!=="string"))throw new ProtocolError("INVALID_SOURCE");
      if(target.kind==="git")for(const p of m.parents)gitAlgorithm(p);
    } else if(!keysExact(m,["id","type"]))throw new ProtocolError("INVALID_SOURCE");
    this.metadataLimit(m);return m as any;
  }
  private async exactExpected():Promise<void>{const r=this.prepared!.request;const m=await this.inspect(r.target,r.expected.id);if(m.type!=="commit")throw new ProtocolError("INVALID_SOURCE");}
  private normalizeTree(value:unknown):PublicationTree {
    if(!isObj(value))throw new ProtocolError("INVALID_SOURCE");const out:PublicationTree={};
    for(const [path,v] of Object.entries(value)){
      if(!validPath(path)||!isObj(v)||!keysExact(v,["base64","mode"])||typeof v.base64!=="string"||typeof v.mode!=="string")throw new ProtocolError("INVALID_SOURCE");
      let bytes:Uint8Array;try{bytes=canonicalBase64(v.base64);}catch{throw new ProtocolError("INVALID_SOURCE");}
      if(bytes.byteLength>this.capabilities.limits.record_bytes)throw new ProtocolError("LIMIT_EXCEEDED");
      out[path]={base64:v.base64,mode:v.mode};
    }
    return out;
  }
  private async tree(target:Target,snapshot:string):Promise<PublicationTree>{return this.normalizeTree(await this.provider.tree(target,snapshot));}
  private candidate(oldState:PublicationTree):PublicationTree {
    const out:PublicationTree=structuredClone(oldState);
    for(const c of this.prepared!.changes){
      const existing=oldState[c.path];if(existing&&existing.mode!=="100644"&&existing.mode!=="100755")throw new ProtocolError("INVALID_SOURCE");
      if("delete" in c){if(existing===undefined)throw new ProtocolError("NOT_FOUND");delete out[c.path];}
      else out[c.path]={base64:Buffer.from(c.put.bytes).toString("base64"),mode:existing?.mode??"100644"};
    }
    if(hasCollision(Object.keys(out)))throw new ProtocolError("INVALID_SOURCE");
    if(sameTree(oldState,out))throw new ProtocolError("NO_CHANGE");
    return out;
  }
  private async submit():Promise<any>{
    const r=this.prepared!.request,a=this.accessResult!;
    await this.exactExpected();
    if(r.validation!==a.validation)throw new ProtocolError("VALIDATION_FAILED");
    if(r.validation!==null&&!a.validator_available)throw new ProtocolError("UNSUPPORTED_CAPABILITY");
    if(!a.project_authorized)throw new ProtocolError("FORBIDDEN");
    const oldState=await this.tree(r.target,r.expected.id);const candidate=this.candidate(oldState);
    if(r.validation!==null){const ok=await this.validation.validate(r.target,r.expected.id,r.validation,structuredClone(oldState),structuredClone(candidate));if(ok!==true)throw new ProtocolError("VALIDATION_FAILED");}
    let ack:AdmissionResult;
    try{ack=await this.provider.admit(r.target,r.expected.id,structuredClone(candidate),receiptMessage(this.prepared!.identity));}
    catch(e){if(e instanceof PublicationProviderFailure&&e.dispatched)this.wasDispatched=true;throw e;}
    this.wasDispatched=true;
    if(!isObj(ack)||!(ack.status==="conflict"||ack.status==="admitted"))throw new ProtocolError("INVALID_SOURCE");
    if(ack.status==="conflict")return this.reconcile();
    if(!keysExact(ack,["status","snapshot"])||typeof ack.snapshot!=="string"||!ack.snapshot)throw new ProtocolError("INVALID_SOURCE");
    if(r.target.kind==="git")gitAlgorithm(ack.snapshot);
    this.admitted=ack.snapshot;
    return this.verify(ack.snapshot);
  }
  private committed(snapshot:string,head:string):any{return {protocol:PROTOCOL,op:"publish",outcome:"committed",request_digest:this.prepared!.requestDigest,snapshot:{id:snapshot},observed_head:{id:head}};}
  private async verify(snapshot:string,observedHead?:string):Promise<any>{
    const r=this.prepared!.request;
    const m=await this.inspect(r.target,snapshot);
    if(m.type!=="commit"||!Array.isArray(m.parents)||m.parents.length!==1||m.parents[0]!==r.expected.id)throw new ProtocolError("INTEGRITY_MISMATCH");
    let receipt:PublicationIdentity|null;try{receipt=parseReceipt(m.message??"");}catch(e){throw e;}
    if(receipt===null||canonicalJson(receipt as unknown as Json)!==canonicalJson(this.prepared!.identity as unknown as Json))throw new ProtocolError("INTEGRITY_MISMATCH");
    const oldState=await this.tree(r.target,r.expected.id);const wanted=this.candidate(oldState);const actual=await this.tree(r.target,snapshot);if(!sameTree(wanted,actual))throw new ProtocolError("INTEGRITY_MISMATCH");
    let head=observedHead;
    if(head===undefined){head=await this.resolve(r.target);const a=await this.access(r.target);if(a.continuity!=="intact")throw new ProtocolError("NAMESPACE_DISCONTINUITY");if(head!==snapshot)await this.walk(r.target,head,snapshot,true);}
    return this.committed(snapshot,head);
  }
  private async resolve(target:Target):Promise<string>{const h=await this.provider.resolve(target);if(typeof h!=="string"||!h)throw new ProtocolError("INVALID_SOURCE");if(Buffer.byteLength(h,"utf8")>this.capabilities.limits.record_bytes)throw new ProtocolError("LIMIT_EXCEEDED");if(target.kind==="git")gitAlgorithm(h);return h;}
  private async walk(target:Target,head:string,expected:string,ancestorOnly=false):Promise<{oid:string;meta:{id:string;type:string;parents?:string[];message?:string}}|null>{
    let oid=head;const seen=new Set<string>();
    for(let i=0;i<this.capabilities.limits.reconcile_commits;i++){
      if(oid===expected)return null;if(seen.has(oid))throw new ProtocolError("NAMESPACE_DISCONTINUITY");seen.add(oid);
      let m;try{m=await this.inspect(target,oid);}catch(e){if(e instanceof ProtocolError&&e.code==="SNAPSHOT_UNAVAILABLE")throw new ProtocolError("HISTORY_UNAVAILABLE");throw e;}
      if(m.type!=="commit"||!Array.isArray(m.parents)||m.parents.length!==1)throw new ProtocolError("NAMESPACE_DISCONTINUITY");
      const parent=m.parents[0]!;if(parent===expected)return ancestorOnly?null:{oid,meta:m};oid=parent;
    }
    throw new ProtocolError("HISTORY_UNAVAILABLE");
  }
  private async reconcile():Promise<any>{
    this.wasDispatched=true;
    const r=this.prepared!.request,t=r.target;const head=await this.resolve(t);
    if((await this.access(t)).continuity!=="intact")throw new ProtocolError("NAMESPACE_DISCONTINUITY");
    if(head===r.expected.id)throw new ProtocolError("PROVIDER_UNAVAILABLE");
    const match=await this.walk(t,head,r.expected.id,false);if(match===null)throw new ProtocolError("PROVIDER_UNAVAILABLE");
    if((await this.access(t)).continuity!=="intact")throw new ProtocolError("NAMESPACE_DISCONTINUITY");
    const receipt=parseReceipt(match.meta.message??"");
    if(receipt===null||canonicalJson(receipt as unknown as Json)!==canonicalJson(this.prepared!.identity as unknown as Json))return {protocol:PROTOCOL,op:"publish",outcome:"not_committed",request_digest:this.prepared!.requestDigest,error:errorObject("CONFLICT")};
    this.admitted=match.oid;
    return this.verify(match.oid,head);
  }
}