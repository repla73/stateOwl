import { gitAlgorithm, gitBlobId } from "../git.js";
import { ProtocolError, type AccessResult, type InspectResult, type ProviderFile, type ReadProvider, type Target } from "../types.js";
import { sha256, canonicalBase64 } from "../encoding.js";

export type MemoryFile={base64:string;mode:string};
export type MemoryObject={type:string;parents?:string[];message?:string;files?:Record<string,MemoryFile>;target?:string;target_type?:string};
export type MemoryWorld={target:Target;head?:string|null;objects:Record<string,MemoryObject>;native?:boolean;algorithm?:"sha1"|"sha256";authenticated?:boolean;authorized?:boolean;conceal_absence?:boolean;external?:Record<string,MemoryWorld>;head_after_resolve?:string;faults?:Array<{method:string;at?:number;phase?:"before"|"after";code?:string;replace?:unknown;mutate?:Partial<MemoryWorld>}>};

export class MemoryProvider implements ReadProvider {
  readonly calls:Record<string,number>={access:0,resolve:0,inspect:0,file:0};
  constructor(public world:MemoryWorld){}
  private locate(target:Target):MemoryWorld {
    if(this.eq(this.world.target,target))return this.world;
    const w=this.world.external?.[target.resource]; if(w&&this.eq(w.target,target))return w;
    throw new ProtocolError("FORBIDDEN");
  }
  private eq(a:Target,b:Target){return a.kind===b.kind&&a.authority===b.authority&&a.resource===b.resource&&a.namespace===b.namespace}
  private merge(target:any,patch:any){for(const [k,v] of Object.entries(patch??{})){if(v===null)delete target[k];else if(v&&typeof v==="object"&&!Array.isArray(v)&&target[k]&&typeof target[k]==="object"&&!Array.isArray(target[k]))this.merge(target[k],v);else target[k]=v;}}
  private fault(w:MemoryWorld,method:string,phase:"before"|"after"):unknown|undefined{
    this.calls[method]=(this.calls[method]??0)+(phase==="before"?1:0); const n=this.calls[method];
    const f=w.faults?.find(x=>x.method===method&&(x.at??1)===n&&(x.phase??"before")===phase); if(!f)return undefined;
    if(f.mutate)this.merge(w,f.mutate); if(f.code)throw new ProtocolError(f.code as any); if("replace" in f)return f.replace; return undefined;
  }
  async access(target:Target,_operation:"read"):Promise<AccessResult>{const w=this.locate(target);let x=this.fault(w,"access","before");if(x!==undefined)return x as AccessResult;if(w.authenticated===false)throw new ProtocolError("UNAUTHENTICATED");if(w.authorized===false)throw new ProtocolError("FORBIDDEN");const out={validation:null,validator_available:true,project_authorized:true,continuity:"intact" as const,auth_scope:"fixture"};x=this.fault(w,"access","after");return (x??out) as AccessResult;}
  async resolve(target:Target):Promise<string>{const w=this.locate(target);let x=this.fault(w,"resolve","before");if(x!==undefined)return x as string;const h=w.head;if(!h)throw new ProtocolError("NOT_FOUND");if(w.head_after_resolve)w.head=w.head_after_resolve;x=this.fault(w,"resolve","after");return (x??h) as string;}
  async inspect(target:Target,snapshot:string):Promise<InspectResult>{const w=this.locate(target);let x=this.fault(w,"inspect","before");if(x!==undefined)return x as InspectResult;const o=w.objects[snapshot];if(!o)throw new ProtocolError("SNAPSHOT_UNAVAILABLE");const out:any={id:snapshot,type:o.type};if(o.parents)out.parents=o.parents;if(o.message!==undefined)out.message=o.message;if(o.target!==undefined)out.target=o.target;if(o.target_type!==undefined)out.target_type=o.target_type;x=this.fault(w,"inspect","after");return (x??out) as InspectResult;}
  async file(target:Target,snapshot:string,path:string):Promise<ProviderFile>{const w=this.locate(target);let x=this.fault(w,"file","before");if(x!==undefined)return x as ProviderFile;const o=w.objects[snapshot];if(!o)throw new ProtocolError("SNAPSHOT_UNAVAILABLE");if(o.type!=="commit")throw new ProtocolError("INVALID_SOURCE");const f=o.files?.[path];if(!f)throw new ProtocolError(w.conceal_absence?"NOT_FOUND_OR_FORBIDDEN":"NOT_FOUND");const bytes=canonicalBase64(f.base64);const out:ProviderFile={base64:f.base64,mode:f.mode,digest:sha256(bytes),integrity:"provider"};if(w.native!==false){const alg=w.algorithm??gitAlgorithm(snapshot);out.object=gitBlobId(bytes,alg);}x=this.fault(w,"file","after");return (x??out) as ProviderFile;}
}
