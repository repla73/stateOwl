import { ProtocolError, type Target } from "./types.js";
import type { ProjectValidationBoundary, PublicationAccess, PublicationTree } from "./publication.js";

export type TrustedProjectValidator = (input:{target:Target;expected:string;oldState:Readonly<PublicationTree>;candidate:Readonly<PublicationTree>})=>boolean|Promise<boolean>;
export type TrustedProjectValidationConfig = {
  target: Target;
  requiredValidation: string|null;
  projectAuthorized: boolean;
  continuity: "intact"|"unknown"|"reset"|(()=>"intact"|"unknown"|"reset"|Promise<"intact"|"unknown"|"reset">);
  authScope: string;
  authorizePath?: (path:string)=>boolean|Promise<boolean>;
  validators?: ReadonlyMap<string,TrustedProjectValidator>;
};

const sameTarget=(a:Target,b:Target)=>a.kind===b.kind&&a.authority===b.authority&&a.resource===b.resource&&a.namespace===b.namespace;

/**
 * Explicit trusted boundary. Validator implementations and path authority are
 * supplied by installation/configuration, never by repository/candidate data.
 */
export class TrustedProjectValidationBoundary implements ProjectValidationBoundary {
  constructor(private readonly config:TrustedProjectValidationConfig){}
  private target(t:Target):void {if(!sameTarget(t,this.config.target))throw new ProtocolError("FORBIDDEN");}
  private async continuity(){return typeof this.config.continuity==="function"?await this.config.continuity():this.config.continuity;}
  async access(target:Target,_operation:"publish"):Promise<PublicationAccess>{
    this.target(target);
    const validation=this.config.requiredValidation;
    return {validation,validator_available:validation===null||this.config.validators?.has(validation)===true,project_authorized:this.config.projectAuthorized,continuity:await this.continuity(),auth_scope:this.config.authScope};
  }
  async authorize(target:Target,_operation:"publish",paths:string[]):Promise<boolean>{
    this.target(target);
    if(!this.config.authorizePath)return true;
    for(const path of paths)if(!await this.config.authorizePath(path))return false;
    return true;
  }
  async validate(target:Target,expected:string,binding:string,oldState:PublicationTree,candidate:PublicationTree):Promise<boolean>{
    this.target(target);
    if(binding!==this.config.requiredValidation)throw new ProtocolError("VALIDATION_FAILED");
    const validator=this.config.validators?.get(binding);if(!validator)throw new ProtocolError("UNSUPPORTED_CAPABILITY");
    if(!this.config.projectAuthorized)throw new ProtocolError("FORBIDDEN");
    return await validator({target:structuredClone(target),expected,oldState:structuredClone(oldState),candidate:structuredClone(candidate)});
  }
}