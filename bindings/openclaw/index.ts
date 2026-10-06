import { Type } from "typebox";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import type {
  Capabilities,
  PublicationProvider,
  ReadProvider,
  Target,
} from "../../typescript/src/index.js";
import {
  BindingInputError,
  MAX_TOOL_INPUT_BYTES,
  TOOL_NAMES,
  isWritePathAuthorized,
  modelVisibleBytes,
  readRequestFromHandoff,
  requestedPublicationPaths,
  sameTarget,
  unrelatedPaths,
  type BindingConfig,
  type BoundTarget,
} from "./core.js";

type StateOwlModule = typeof import("../../typescript/src/index.js");

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

type PluginConfig = {
  repository?: unknown;
  namespace?: unknown;
  githubToken?: unknown;
  publishEnabled?: unknown;
  singleStepContinuity?: unknown;
  writePaths?: unknown;
};

function bindingConfig(raw: unknown): BindingConfig {
  const value = (raw ?? {}) as PluginConfig;
  if (
    typeof value.repository !== "string" ||
    !value.repository ||
    typeof value.namespace !== "string" ||
    !value.namespace.startsWith("refs/heads/")
  ) {
    throw new Error("stateOwl OpenClaw binding requires repository and refs/heads/* namespace");
  }
  if (value.githubToken !== undefined && typeof value.githubToken !== "string") {
    throw new Error("githubToken must resolve to a string");
  }
  const publishEnabled = value.publishEnabled === true;
  const singleStepContinuity = value.singleStepContinuity === true;
  const writePaths = Array.isArray(value.writePaths)
    ? value.writePaths.filter((path): path is string => typeof path === "string" && path.length > 0)
    : [];

  if (publishEnabled && !singleStepContinuity) {
    throw new Error("singleStepContinuity=true is required when publication is enabled");
  }
  if (publishEnabled && writePaths.length === 0) {
    throw new Error("writePaths must be non-empty when publication is enabled");
  }

  return {
    target: {
      kind: "git",
      authority: "github.com",
      resource: value.repository,
      namespace: value.namespace,
    },
    githubToken: value.githubToken as string | undefined,
    publishEnabled,
    singleStepContinuity,
    writePaths: new Set(writePaths),
  };
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

class ExactTargetReadProvider implements ReadProvider {
  constructor(
    private readonly inner: ReadProvider,
    private readonly target: BoundTarget,
    private readonly observedPaths: Set<string>,
  ) {}

  private check(target: Target): void {
    if (!sameTarget(target, this.target)) {
      throw new BindingInputError("FORBIDDEN", "read target is outside configured target");
    }
  }

  access(target: Target, operation: "read") {
    this.check(target);
    return this.inner.access(target, operation);
  }

  resolve(target: Target) {
    this.check(target);
    return this.inner.resolve(target);
  }

  inspect(target: Target, snapshot: string) {
    this.check(target);
    return this.inner.inspect(target, snapshot);
  }

  file(target: Target, snapshot: string, path: string) {
    this.check(target);
    this.observedPaths.add(path);
    return this.inner.file(target, snapshot, path);
  }
}

class EvidencePublicationProvider implements PublicationProvider {
  constructor(
    private readonly inner: PublicationProvider,
    private readonly observedPaths: Set<string>,
  ) {}

  resolve(target: Target) {
    return this.inner.resolve(target);
  }

  inspect(target: Target, snapshot: string) {
    return this.inner.inspect(target, snapshot);
  }

  async tree(target: Target, snapshot: string) {
    const tree = await this.inner.tree(target, snapshot);
    for (const path of Object.keys(tree)) this.observedPaths.add(path);
    return tree;
  }

  async admit(target: Target, expected: string, candidate: Awaited<ReturnType<PublicationProvider["tree"]>>, message: string) {
    for (const path of Object.keys(candidate)) this.observedPaths.add(path);
    return this.inner.admit(target, expected, candidate, message);
  }
}

function toolResult(
  result: unknown,
  modelRequest: unknown,
  providerOperations: number,
  requestedPaths: string[],
  observedPaths: Set<string>,
) {
  const text = JSON.stringify(result);
  return {
    content: [{ type: "text" as const, text }],
    details: {
      stateowl: result,
      evidence: {
        declared_tools: [...TOOL_NAMES],
        model_visible_request_bytes: modelVisibleBytes(modelRequest),
        model_visible_result_bytes: modelVisibleBytes(result),
        provider_operations: providerOperations,
        requested_paths: [...new Set(requestedPaths)].sort(),
        unrelated_paths: unrelatedPaths(observedPaths, requestedPaths),
      },
    },
  };
}

export default definePluginEntry({
  id: "stateowl",
  name: "stateOwl",
  description: "Exact, bounded stateOwl reads and guarded publication for OpenClaw.",
  register(api) {
    const config = bindingConfig(api.pluginConfig);

    api.registerTool({
      name: "stateowl_read",
      label: "stateOwl Read",
      description: "Read the exact records identified by a stateowl.r4-handoff/1 artifact.",
      parameters: Type.Object(
        {
          handoffJson: Type.String({ minLength: 2, maxLength: MAX_TOOL_INPUT_BYTES }),
        },
        { additionalProperties: false },
      ),
      async execute(_id, params) {
        const stateowl = (await import("../../typescript/dist/src/index.js")) as StateOwlModule;
        const mapped = readRequestFromHandoff(params.handoffJson, config.target);
        const allowed = new Set([config.target.resource]);
        const observedPaths = new Set<string>();
        let providerOperations = 0;
        const transport = stateowl.githubFetchTransport(config.githubToken);
        const baseProvider = new stateowl.GitHubReadProvider(
          async (path: string) => {
            providerOperations += 1;
            return transport(path);
          },
          allowed,
        );
        const reader = new stateowl.Reader(
          new ExactTargetReadProvider(baseProvider, config.target, observedPaths),
          capabilities(stateowl.PROTOCOL, config.publishEnabled),
        );
        const result = await reader.read(mapped.request);
        return toolResult(
          result,
          { handoffJson: params.handoffJson },
          providerOperations,
          mapped.requestedPaths,
          observedPaths,
        );
      },
    });

    api.registerTool({
      name: "stateowl_publish",
      label: "stateOwl Publish",
      description: "Submit or reconcile one bounded stateOwl publication request without changing R3 semantics.",
      parameters: Type.Object(
        {
          requestJson: Type.String({ minLength: 2, maxLength: MAX_TOOL_INPUT_BYTES }),
        },
        { additionalProperties: false },
      ),
      async execute(_id, params) {
        const stateowl = (await import("../../typescript/dist/src/index.js")) as StateOwlModule;
        const caps = capabilities(stateowl.PROTOCOL, config.publishEnabled);
        const allowed = new Set([config.target.resource]);
        const observedPaths = new Set<string>();
        let providerOperations = 0;
        const transports = stateowl.githubPublicationFetchTransports(config.githubToken);
        const baseProvider = new stateowl.GitHubPublicationProvider(
          async (method, path, body) => {
            providerOperations += 1;
            return transports.rest(method, path, body);
          },
          async (query, variables) => {
            providerOperations += 1;
            return transports.graphql(query, variables);
          },
          allowed,
        );
        const provider = new EvidencePublicationProvider(baseProvider, observedPaths);
        const validation = new stateowl.TrustedProjectValidationBoundary({
          target: config.target,
          requiredValidation: null,
          projectAuthorized: true,
          continuity: config.singleStepContinuity ? "intact" : "unknown",
          authScope: "openclaw-plugin-config",
          authorizePath: (path: string) => isWritePathAuthorized(config, path),
        });
        const publisher = new stateowl.Publisher(provider, validation, caps);
        const requestedPaths = requestedPublicationPaths(params.requestJson);
        const result = await publisher.publish(params.requestJson);
        return toolResult(
          result,
          { requestJson: params.requestJson },
          providerOperations,
          requestedPaths,
          observedPaths,
        );
      },
    });
  },
});
