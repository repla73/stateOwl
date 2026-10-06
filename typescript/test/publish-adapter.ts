import { Publisher, PublicationProviderFailure, type AdmissionResult, type ProjectValidationBoundary, type PublicationAccess, type PublicationProvider, type PublicationTree } from "../src/publication.js";
import { ProtocolError, type Capabilities, type ErrorCode, type InspectResult, type Target } from "../src/types.js";

class Lines {
  private buffer="";private queue:string[]=[];private waiters:Array<(v:string)=>void>=[];private ended=false;
  constructor(){process.stdin.setEncoding("utf8");process.stdin.on("data",(chunk:string)=>{this.buffer+=chunk;while(true){const i=this.buffer.indexOf("\n");if(i<0)break;const line=this.buffer.slice(0,i);this.buffer=this.buffer.slice(i+1);this.push(line);}});process.stdin.on("end",()=>{this.ended=true;if(this.buffer)this.push(this.buffer);});}
  private push(line:string){const w=this.waiters.shift();if(w)w(line);else this.queue.push(line);}
  async next():Promise<string>{const q=this.queue.shift();if(q!==undefined)return q;if(this.ended)throw new Error("stdin ended");return new Promise(resolve=>this.waiters.push(resolve));}
}
class Rpc implements PublicationProvider,ProjectValidationBoundary {
  private id=0;constructor(private lines:Lines){}
  private async call(method:string,args:Record<string,unknown>):Promise<any>{const id=++this.id;process.stdout.write(JSON.stringify({type:"call",id,method,args})+"\n");const line=await this.lines.next();const msg=JSON.parse(line);if(msg?.type!=="return"||msg.id!==id)throw new Error("invalid harness return");if(msg.fault){const code=msg.fault.code as ErrorCode;throw new PublicationProviderFailure(code,!!msg.fault.dispatched);}return msg.value;}
  access(target:Target,operation:"publish"):Promise<PublicationAccess>{return this.call("access",{target,operation});}
  authorize(target:Target,operation:"publish",paths:string[]):Promise<boolean>{return this.call("authorize",{target,operation,paths});}
  validate(target:Target,expected:string,binding:string,oldState:PublicationTree,candidate:PublicationTree):Promise<boolean>{return this.call("validate",{target,expected,binding,old:oldState,candidate});}
  resolve(target:Target):Promise<string>{return this.call("resolve",{target});}
  inspect(target:Target,snapshot:string):Promise<InspectResult>{return this.call("inspect",{target,snapshot});}
  tree(target:Target,snapshot:string):Promise<PublicationTree>{return this.call("tree",{target,snapshot});}
  admit(target:Target,expected:string,candidate:PublicationTree,message:string):Promise<AdmissionResult>{return this.call("admit",{target,expected,candidate,message});}
}

const lines=new Lines();
while(true){
  let line:string;try{line=await lines.next();}catch{break;}if(!line)continue;
  let start:any;try{start=JSON.parse(line);}catch{process.exitCode=1;break;}
  if(start?.type!=="start"||typeof start.request_base64!=="string"||!start.capabilities){process.exitCode=1;break;}
  try{
    const rpc=new Rpc(lines);const publisher=new Publisher(rpc,rpc,start.capabilities as Capabilities);const raw=Buffer.from(start.request_base64,"base64");const response=await publisher.publish(raw);process.stdout.write(JSON.stringify({type:"result",response})+"\n");
  }catch(e){
    const code=e instanceof ProtocolError?e.code:"PROVIDER_UNAVAILABLE";process.stdout.write(JSON.stringify({type:"result",response:{protocol:"stateowl/0.2-draft.3",op:"unknown",status:"error",error:{code,retry:code==="PROVIDER_UNAVAILABLE"?"after_backoff":"after_correction"}}})+"\n");
  }
}