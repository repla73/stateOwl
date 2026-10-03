# Optional compatibility binding — stateowl.router/v1

**Semantic binding:** `urn:stateowl:binding:router-v1:1`  
**Protocol:** `stateowl/0.2-draft.2`  
**Consumer:** existing 0.1.0 router/project files and their documented focused-read behavior. This is not a universal state layout or a replacement Governance router.

## L1. Router and selected route

The router is `.stateowl/router.json` at the root snapshot. It is a JSON object with exactly `schema` and `routes`; `schema` equals `stateowl.router/v1`, and `routes` is a nonempty object. Arbitrary project record properties are not closed by this binding. JSON duplicate keys are rejected before any shape checks.

A requested route is an exact, nonempty, case-sensitive name. Missing route → `NOT_FOUND`; `optional:true` does not make a missing route optional. Its entry is an object containing exactly required `path` and `select`. `path` follows protocol I4. `select` is an array of unique, nonempty strings; the array itself may be empty. Validate the selected entry only; an unrelated malformed route entry is not a reason to load or validate sibling records. The container must still be valid strict JSON.

The selected record is a JSON object. The route's `select` is the default; an explicit request `select` replaces it (protocol request selectors may include an empty property name). Only present top-level names are returned, with exact values; absent names are omitted, not null. The new response also reports effective `select` and `missing` in selection order. Empty selection returns `{}`. The unprojected record remains available to resolve requested links.

## L2. Linked detail

Interpret `links` only when a nonempty `expand` is requested. An absent `links` property means an empty object; if present it must be an object. Each expansion name is a unique, nonempty exact string; process names in request order. Missing name → `NOT_FOUND`. Each selected link must be an object with only:

| Field | Rule |
|---|---|
| `path` | Required protocol I4 path, relative to repository root, **not** to the referring file. |
| `repository` | Optional `owner/name`, ASCII letters/digits/underscore/dot/hyphen, neither component `.` nor `..`. Defaults to the root repository. |
| `commit` | Optional exact 40-character lowercase SHA-1 commit. Defaults to the root snapshot only when repository is unchanged. |
| `format` | Optional `json` or `text`; default `json`. |
| `select` | Optional unique array of nonempty top-level names; empty array allowed. Legal only with JSON. |

Compare a supplied repository spelling literally with the canonical root repository before alias mapping. A different spelling requires explicit `commit`, otherwise `EXACT_SNAPSHOT_REQUIRED`. Same-repository explicit commits are allowed. Legacy explicit commit syntax is SHA-1-only; this does **not** constrain the new core or Git binding. Supporting a different legacy syntax would require a new semantic binding. A root SHA-256 snapshot with no explicit legacy `commit` still inherits that exact snapshot.

For a changed repository, form a Git target with the root's canonical authority and namespace and the explicitly mapped canonical repository. The namespace is an addressing context only for this exact read; no ref is resolved there. Trusted mappings are required for non-Git fixture targets. Authorize the destination separately; never reuse access as authority. Emit exact `origin` when repository or snapshot differs. No mutable fallback is allowed.

JSON links can contain any protocol-supported JSON value when not projected; with `select`, the value must be an object. Text links decode exact UTF-8, including newlines. Links are **one-level only**: never interpret an expanded record's links. Unrequested malformed links and application metadata are ignored, but malformed JSON anywhere in the source still fails before projection. Direct JSON-path selections may request expansion through this binding without reading a router. Routing provenance lists the router when consulted and the parent record when its links are inspected, once each in first-use order; unrequested links add no routing source.

## L3. Failure mapping and order

The protocol's earlier framing/capability/access/integrity/serialization checks take precedence. Thereafter inspect router container → selected route name → entry fields/path/selection → selected record shape → effective projection → requested links in order. Within a link: object/unknown fields → repository → missing cross-repository commit → commit syntax → path → format → selection. A malformed container/entry, unsupported field/format, invalid path, duplicate selection name or wrong JSON value kind is `INVALID_SOURCE`. Missing selected route/link is `NOT_FOUND`. An explicit link requiring an unavailable exact commit is `SNAPSHOT_UNAVAILABLE`. Invalid UTF-8/duplicate JSON is `INVALID_SOURCE`; unrepresentable numbers use `NUMBER_UNREPRESENTABLE`. No failure returns partial records.

The schema companion describes the containers. It intentionally does not require validating every route entry or every unrequested link: the runtime selection rules above determine the addressed scope.

## L4. Existing API versus this binding

The shipped Python 0.1.0 API is not changed. Its default `refs/heads/main`, fresh resolution per call, `expected_head` assertion before file reads, default top-level projection, explicit nonrecursive expansion and repository/commit/path/blob provenance are retained in `legacy-v0.1.0.json`. Those golden cases invoke the actual old Reader and preserve its original `head/value/sources/expanded` result and legacy error codes; they are not translated to the new envelope.

This binding standardizes the supported file convention independently of Python. It does not preserve accidental acceptance of unknown router-root properties, control characters in paths, non-finite numbers, unpaired surrogates or runtime-specific exceptions. No compatibility consumer for those malformed inputs was identified by the assignment. New protocol limits, numeric rules, batching, typed IDs and errors are explicit opt-in behavior, not silently retrofitted to 0.1.0. Native Governance compatibility requires separately authorized real fixtures and is not claimed here.
