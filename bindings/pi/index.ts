import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import type {
  Capabilities,
  ReadProvider,
  Target,
} from "../../typescript/src/index.js";

type StateOwlModule = typeof import("../../typescript/src/index.js");

type BindingConfig = {
  target: Target;
  token?: string;
  publishEnabled: boolean;
  singleStepContinuity: boolean;
  writePaths: ReadonlySet<string>;
};

const LIMITS = {
  request_bytes: 65536,
  record_bytes: 16384,
  mutation_bytes: 32768,
  response_bytes: 65536,
  records: 32,
  expansions: 16,
  changes: 32,
  tag_hops: 8,
  reconcile_commits: 16,
  json_depth: 64,
} as const;

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function configFromEnvironment(): BindingConfig {
  const resource = requiredEnv("STATEOWL_TARGET_REPOSITORY");
  const namespace = requiredEnv("STATEOWL_TARGET_NAMESPACE");
  const publishEnabled = process.env.STATEOWL_PUBLISH_ENABLED === "1";
  const singleStepContinuity = process.env.STATEOWL_SINGLE_STEP_CONTINUITY === "1";
  const writePaths = new Set(
    (process.env.STATEOWL_WRITE_PATHS ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean),
  );

  if (publishEnabled && !singleStepContinuity) {
    throw new Error("STATEOWL_SINGLE_STEP_CONTINUITY=1 is required when publication is enabled");
  }
  if (publishEnabled && writePaths.size === 0) {
    throw new Error("STATEOWL_WRITE_PATHS must be non-empty when publication is enabled");
  }

  return {
    target: {
      kind: "git",
      authority: "github.com",
      resource,
      namespace,
    },
    token: process.env.STATEOWL_GITHUB_TOKEN || undefined,
    publishEnabled,
    singleStepContinuity,
    writePaths,
  };
}

function sameTarget(left: Target, right: Target): boolean {
  return (
    left.kind === right.kind &&
    left.authority === right.authority &&
    left.resource === right.resource &&
    left.namespace === right.namespace
  );
}

class ExactTargetReadProvider implements ReadProvider {
  constructor(
    private readonly inner: ReadProvider,
    private readonly target: Target,
    private readonly forbidden: () => never,
  ) {}

  private check(target: Target): void {
    if (!sameTarget(target, this.target)) this.forbidden();
  }

  async access(target: Target, operation: "read") {
    this.check(target);
    return this.inner.access(target, operation);
  }

  async resolve(target: Target) {
    this.check(target);
    return this.inner.resolve(target);
  }

  async inspect(target: Target, snapshot: string) {
    this.check(target);
    return this.inner.inspect(target, snapshot);
  }

  async file(target: Target, snapshot: string, path: string) {
    this.check(target);
    return this.inner.file(target, snapshot, path);
  }
}

function capabilities(protocol: string, publishEnabled: boolean): Capabilities {
  return {
    protocol,
    operations: publishEnabled ? ["read", "publish"] : ["read"],
    formats: ["json", "text", "base64"],
    features: [],
    resolvers: [],
    limits: { ...LIMITS },
    ...(publishEnabled
      ? {
          publication: {
            continuity: "single_step_required" as const,
            receipt_format: "stateowl.git-receipt/2" as const,
            receipt_retention: "reachable_history" as const,
            authority: "mechanical" as const,
          },
        }
      : {}),
  };
}

function toolResult(result: unknown) {
  const text = JSON.stringify(result);
  return {
    content: [{ type: "text" as const, text }],
    details: { stateowl: result },
  };
}

export default async function stateOwlPiExtension(pi: ExtensionAPI) {
  const config = configFromEnvironment();

  // W4 builds the accepted nested TypeScript package first. Pi then loads the
  // compiled implementation into this process; no subprocess or remote stateOwl
  // runtime sits behind either tool.
  const stateowl = (await import("../../typescript/dist/src/index.js")) as StateOwlModule;
  const caps = capabilities(stateowl.PROTOCOL, config.publishEnabled);
  const allowed = new Set([config.target.resource]);

  pi.registerTool({
    name: "stateowl_read",
    label: "stateOwl Read",
    description: "Read a bounded stateOwl request from the configured exact target.",
    parameters: Type.Object(
      { request: Type.Any() },
      { additionalProperties: false },
    ),
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: true,
    },
    async execute(_toolCallId, params) {
      const baseProvider = new stateowl.GitHubReadProvider(
        stateowl.githubFetchTransport(config.token),
        allowed,
      );
      const provider = new ExactTargetReadProvider(baseProvider, config.target, () => { throw new stateowl.ProtocolError("FORBIDDEN"); });
      const reader = new stateowl.Reader(provider, caps);
      return toolResult(await reader.read(params.request));
    },
  });

  pi.registerTool({
    name: "stateowl_publish",
    label: "stateOwl Publish",
    description: "Run one guarded stateOwl publication or reconciliation request against the configured exact target.",
    parameters: Type.Object(
      { request: Type.Any() },
      { additionalProperties: false },
    ),
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: false,
      openWorldHint: true,
    },
    async execute(_toolCallId, params) {
      const transports = stateowl.githubPublicationFetchTransports(config.token);
      const provider = new stateowl.GitHubPublicationProvider(
        transports.rest,
        transports.graphql,
        allowed,
      );
      const validation = new stateowl.TrustedProjectValidationBoundary({
        target: config.target,
        requiredValidation: null,
        projectAuthorized: true,
        continuity: config.singleStepContinuity ? "intact" : "unknown",
        authScope: "pi-environment",
        authorizePath: (path: string) => config.writePaths.has(path),
      });
      const publisher = new stateowl.Publisher(provider, validation, caps);
      return toolResult(await publisher.publish(params.request));
    },
  });
}
