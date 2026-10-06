export const R4_HANDOFF_FORMAT = "stateowl.r4-handoff/1" as const;
export const STATEOWL_PROTOCOL = "stateowl/0.2-draft.3" as const;
export const R4_PROFILE_ID = "stateowl.r4-continuity/1" as const;
export const R4_PROFILE_DIGEST = "sha256:9558ad87b903f8c86da55320af7798eadc48ba794cef020f0b587c679937c75c" as const;
export const TOOL_NAMES = ["stateowl_read", "stateowl_publish"] as const;
export const MAX_TOOL_INPUT_BYTES = 65536;

export type BoundTarget = {
  kind: string;
  authority: string;
  resource: string;
  namespace: string;
};

export type BindingConfig = {
  target: BoundTarget;
  githubToken?: string;
  publishEnabled: boolean;
  singleStepContinuity: boolean;
  writePaths: ReadonlySet<string>;
};

export class BindingInputError extends Error {
  readonly code: "INVALID_HANDOFF" | "FORBIDDEN";
  constructor(code: "INVALID_HANDOFF" | "FORBIDDEN", message: string) {
    super(message);
    this.code = code;
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, allowed: readonly string[]): boolean {
  return Object.keys(value).every((key) => allowed.includes(key));
}

function bytes(value: string): number {
  return new TextEncoder().encode(value).byteLength;
}

function validPath(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    !value.startsWith("/") &&
    !value.endsWith("/") &&
    !value.includes("\\") &&
    !/[\x00-\x1f\x7f]/.test(value) &&
    value.split("/").every((part) => part !== "" && part !== "." && part !== "..")
  );
}

export function sameTarget(left: BoundTarget, right: BoundTarget): boolean {
  return (
    left.kind === right.kind &&
    left.authority === right.authority &&
    left.resource === right.resource &&
    left.namespace === right.namespace
  );
}

function parseJsonObject(raw: string, label: string): Record<string, unknown> {
  if (bytes(raw) > MAX_TOOL_INPUT_BYTES) {
    throw new BindingInputError("INVALID_HANDOFF", `${label} exceeds byte limit`);
  }
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new BindingInputError("INVALID_HANDOFF", `${label} is not valid JSON`);
  }
  if (!isObject(value)) {
    throw new BindingInputError("INVALID_HANDOFF", `${label} must be an object`);
  }
  return value;
}

function parseTarget(value: unknown): BoundTarget {
  if (
    !isObject(value) ||
    !exactKeys(value, ["kind", "authority", "resource", "namespace"]) ||
    typeof value.kind !== "string" ||
    typeof value.authority !== "string" ||
    typeof value.resource !== "string" ||
    typeof value.namespace !== "string" ||
    !value.kind ||
    !value.authority ||
    !value.resource ||
    !value.namespace
  ) {
    throw new BindingInputError("INVALID_HANDOFF", "invalid handoff target");
  }
  return {
    kind: value.kind,
    authority: value.authority,
    resource: value.resource,
    namespace: value.namespace,
  };
}

function parseAt(value: unknown): { current: true } | { snapshot: { id: string } } {
  if (!isObject(value)) {
    throw new BindingInputError("INVALID_HANDOFF", "invalid handoff locator");
  }
  if (exactKeys(value, ["current"]) && value.current === true) {
    return { current: true };
  }
  if (exactKeys(value, ["snapshot"]) && isObject(value.snapshot)) {
    const snapshot = value.snapshot;
    if (
      exactKeys(snapshot, ["id"]) &&
      typeof snapshot.id === "string" &&
      snapshot.id.length > 0
    ) {
      return { snapshot: { id: snapshot.id } };
    }
  }
  throw new BindingInputError("INVALID_HANDOFF", "invalid handoff locator");
}

function parseRecords(value: unknown): Array<{ key: string; path: string; format: "json" | "text" | "base64" }> {
  if (!Array.isArray(value) || value.length < 1 || value.length > 32) {
    throw new BindingInputError("INVALID_HANDOFF", "invalid handoff records");
  }
  const records = value.map((item) => {
    if (
      !isObject(item) ||
      !exactKeys(item, ["key", "path", "format"]) ||
      typeof item.key !== "string" ||
      !item.key ||
      !validPath(item.path) ||
      !["json", "text", "base64"].includes(String(item.format))
    ) {
      throw new BindingInputError("INVALID_HANDOFF", "invalid handoff record");
    }
    return {
      key: item.key,
      path: item.path,
      format: item.format as "json" | "text" | "base64",
    };
  });
  if (new Set(records.map((record) => record.key)).size !== records.length) {
    throw new BindingInputError("INVALID_HANDOFF", "duplicate handoff record key");
  }
  return records;
}

export function readRequestFromHandoff(
  raw: string,
  configuredTarget: BoundTarget,
): {
  request: {
    protocol: typeof STATEOWL_PROTOCOL;
    op: "read";
    target: BoundTarget;
    at: { current: true } | { snapshot: { id: string } };
    records: Array<{ key: string; path: string; format: "json" | "text" | "base64" }>;
  };
  requestedPaths: string[];
} {
  const handoff = parseJsonObject(raw, "handoff");
  if (
    !exactKeys(handoff, ["format", "protocol", "profile", "target", "at", "records", "continuation"]) ||
    handoff.format !== R4_HANDOFF_FORMAT ||
    handoff.protocol !== STATEOWL_PROTOCOL ||
    !isObject(handoff.profile) ||
    !exactKeys(handoff.profile, ["id", "digest"]) ||
    handoff.profile.id !== R4_PROFILE_ID ||
    handoff.profile.digest !== R4_PROFILE_DIGEST ||
    !("continuation" in handoff)
  ) {
    throw new BindingInputError("INVALID_HANDOFF", "handoff contract/profile mismatch");
  }

  const target = parseTarget(handoff.target);
  if (!sameTarget(target, configuredTarget)) {
    throw new BindingInputError("FORBIDDEN", "handoff target is outside configured target");
  }

  const at = parseAt(handoff.at);
  const records = parseRecords(handoff.records);
  return {
    request: {
      protocol: STATEOWL_PROTOCOL,
      op: "read",
      target,
      at,
      records,
    },
    requestedPaths: records.map((record) => record.path),
  };
}

export function requestedPublicationPaths(raw: string): string[] {
  if (bytes(raw) > MAX_TOOL_INPUT_BYTES) return [];
  try {
    const value = JSON.parse(raw);
    if (!isObject(value) || !Array.isArray(value.changes)) return [];
    return value.changes
      .map((change) => (isObject(change) && typeof change.path === "string" ? change.path : null))
      .filter((path): path is string => path !== null);
  } catch {
    return [];
  }
}

export function isWritePathAuthorized(config: BindingConfig, path: string): boolean {
  return config.publishEnabled && config.singleStepContinuity && config.writePaths.has(path);
}

export function unrelatedPaths(observed: Iterable<string>, requested: Iterable<string>): string[] {
  const wanted = new Set(requested);
  return [...new Set(observed)].filter((path) => !wanted.has(path)).sort();
}

export function modelVisibleBytes(value: unknown): number {
  return bytes(JSON.stringify(value));
}
