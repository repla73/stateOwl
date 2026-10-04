declare const Buffer: {
  from(input: string | Uint8Array, encoding?: string): Uint8Array & { toString(encoding?: string): string };
  byteLength(input: string, encoding?: string): number;
  concat(chunks: Uint8Array[]): Uint8Array;
};
declare module "node:crypto" { export function createHash(algorithm:string): { update(data:string|Uint8Array): any; digest(encoding:"hex"): string } }
declare module "node:child_process" { export function execFileSync(file:string,args:string[],opts?:any): any }
declare module "node:fs" { export function readFileSync(path:string, enc?:string): any; export function writeFileSync(path:string,data:any):void; export function mkdtempSync(prefix:string):string; export function mkdirSync(path:string,opts?:any):void; export function rmSync(path:string,opts?:any):void }
declare module "node:os" { export function tmpdir():string }
declare module "node:path" { export function join(...p:string[]):string; export function resolve(...p:string[]):string; export function dirname(p:string):string }
declare module "node:url" { export function fileURLToPath(u:string):string }
declare module "node:test" { const test:any; export default test }
declare module "node:assert/strict" { const assert:any; export default assert }
declare module "node:perf_hooks" { export const performance:{now():number} }
declare const process: any;
