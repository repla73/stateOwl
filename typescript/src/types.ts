export const PROTOCOL = "stateowl/0.2-draft.3" as const;
export const ROUTER_V1 = "urn:stateowl:binding:router-v1:1" as const;

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type Target = { kind: string; authority: string; resource: string; namespace: string };
export type Snapshot = { id: string };
export type Format = "json" | "text" | "base64";
export type Integrity = "provider" | "object_chain";
export type Source = {
  path: string;
  digest: string;
  integrity: Integrity;
  object?: string;
  origin?: { target: Target; snapshot: Snapshot };
};
export type Selection = {
  key: string;
  path?: string;
  format?: Format;
  route?: string;
  select?: string[];
  optional?: boolean;
  expand?: string[];
};
export type ReadRequest = {
  protocol: typeof PROTOCOL;
  op: "read";
  target: Target;
  at: { current: true; assert_snapshot?: Snapshot } | { snapshot: Snapshot };
  records: Selection[];
  resolver?: string;
};
export type Limits = {
  request_bytes: number;
  record_bytes: number;
  mutation_bytes: number;
  response_bytes: number;
  records: number;
  expansions: number;
  changes: number;
  tag_hops: number;
  reconcile_commits: number;
  json_depth: number;
};
export type Capabilities = {
  protocol: string;
  operations: string[];
  formats: string[];
  features: string[];
  resolvers: string[];
  limits: Limits;
};
export type ProviderFile = {
  base64: string;
  mode: string;
  digest: string;
  integrity: Integrity;
  object?: string;
};
export type InspectResult =
  | { id: string; type: "commit"; parents?: string[]; message?: string }
  | { id: string; type: "tag"; target?: string; target_type?: string }
  | { id: string; type: string; [key: string]: unknown };
export type AccessResult = { validation: string | null; validator_available: boolean; project_authorized: boolean; continuity: "intact"|"unknown"|"reset"; auth_scope: string };
export interface ReadProvider {
  access(target: Target, operation: "read"): Promise<AccessResult>;
  resolve(target: Target): Promise<string>;
  inspect(target: Target, snapshot: string): Promise<InspectResult>;
  file(target: Target, snapshot: string, path: string): Promise<ProviderFile>;
}
export type ErrorCode =
  | "INVALID_REQUEST" | "NOT_FOUND" | "EXACT_SNAPSHOT_REQUIRED" | "INVALID_SOURCE" | "NUMBER_UNREPRESENTABLE" | "LIMIT_EXCEEDED" | "VALIDATION_FAILED"
  | "UNAUTHENTICATED" | "CONFLICT" | "NAMESPACE_DISCONTINUITY" | "TOKEN_INVALID"
  | "RATE_LIMITED" | "PROVIDER_UNAVAILABLE"
  | "UNSUPPORTED_VERSION" | "UNSUPPORTED_CAPABILITY" | "FORBIDDEN" | "NOT_FOUND_OR_FORBIDDEN" | "SNAPSHOT_UNAVAILABLE" | "INTEGRITY_MISMATCH" | "NO_CHANGE" | "HISTORY_UNAVAILABLE";
export class ProtocolError extends Error {
  constructor(public code: ErrorCode) { super(code); }
}
