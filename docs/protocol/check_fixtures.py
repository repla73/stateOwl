#!/usr/bin/env python3
"""Offline corpus checks; not a new stateOwl implementation or provider qualifier.

Run from any directory. The only third-party dependency is test-only jsonschema.
Legacy vectors exercise the existing repository Reader against exact fixture bytes.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import math
from decimal import Decimal
from pathlib import Path
import re
import sys
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:
    raise SystemExit("Install docs/protocol/requirements-checks.txt in a test environment.") from exc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MAX_SAFE = 9007199254740991


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def unbase64(text: str) -> bytes:
    raw = base64.b64decode(text, validate=True)
    require(base64.b64encode(raw).decode("ascii") == text, "noncanonical base64")
    return raw


def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON key")
        value[key] = item
    return value


def reject_constant(text: str) -> None:
    raise ValueError("non-finite JSON constant: " + text)


def strict_source(raw: bytes) -> Any:
    """Check the draft's strict source-JSON vectors, preserving decimal input.

    Python's shortest binary64 repr is sufficient for these fixed vectors.
    This helper is NOT a general RFC 8785 canonicalizer or wire implementation.
    """
    require(not raw.startswith(b"\xef\xbb\xbf"), "BOM")
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs,
                        parse_constant=reject_constant, parse_int=Decimal, parse_float=Decimal)

    def visit(value: Any) -> None:
        if isinstance(value, str):
            value.encode("utf-8", errors="strict")
        elif isinstance(value, Decimal):
            require(value.is_finite(), "non-finite decimal")
            if value == value.to_integral_value():
                require(abs(value) <= MAX_SAFE, "unsafe integer")
            else:
                as_float = float(value)
                require(math.isfinite(as_float), "binary64 overflow")
                require(Decimal(repr(as_float)) == value, "rounded decimal")
        elif isinstance(value, dict):
            for key, item in value.items():
                visit(key)
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(result)
    return result


def read_json(path: Path) -> Any:
    raw = path.read_bytes()
    strict_source(raw)
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def bytes_value(value: dict[str, str]) -> bytes:
    if value["encoding"] == "utf8":
        return value["data"].encode("utf-8")
    require(value["encoding"] == "base64", "unknown byte encoding")
    return unbase64(value["data"])


def receipt_preimage(request: dict[str, Any], validation: Any) -> dict[str, Any]:
    changes = []
    for change in request["changes"]:
        if "put" in change:
            raw = bytes_value(change["put"])
            changes.append({"path": change["path"], "put": {"digest": sha256(raw), "bytes": len(raw)}})
        else:
            changes.append({"path": change["path"], "delete": True})
    return {"protocol": request["protocol"], "target": request["target"],
            "expected": request["expected"], "operation_id": request["operation_id"],
            "changes": changes, "validation": validation}


def canonical_receipt(preimage: dict[str, Any]) -> str:
    """Canonicalize only P3's fixed-ASCII-key, integer-only envelope subset."""
    keys = {"protocol", "target", "kind", "authority", "resource", "namespace",
            "expected", "id", "generation", "operation_id", "changes", "path",
            "put", "digest", "bytes", "delete", "validation"}

    def check(value: Any) -> None:
        if isinstance(value, dict):
            require(set(value) <= keys, "not a receipt-envelope object")
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, str):
            value.encode("utf-8", errors="strict")
        elif value is None or isinstance(value, bool):
            pass
        else:
            require(type(value) is int and 0 <= value <= MAX_SAFE, "not a safe receipt integer")
    check(preimage)
    return json.dumps(preimage, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def check_legacy() -> int:
    suite = read_json(HERE / "legacy-v0.1.0.json")
    spec = importlib.util.spec_from_file_location("stateowl_legacy_fixture_core", ROOT / suite["baseline"]["source"])
    require(spec is not None and spec.loader is not None, "legacy core is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    def decoded(files: dict[str, Any]) -> dict[str, bytes]:
        result = {}
        for path, item in files.items():
            raw = unbase64(item["base64"])
            require(git_blob(raw) == item["blob"], "legacy fixture blob mismatch: " + path)
            result[path] = raw
        return result

    base_files = decoded(suite["files"])
    for case in suite["cases"]:
        data = {**base_files, **decoded(case["overrides"])}

        class Store:
            def __init__(self) -> None:
                self.resolves = 0
                self.paths: list[str] = []

            def resolve_ref(self, repository: str, ref: str) -> str:
                require(repository == suite["repository"] and ref == "refs/heads/main", "legacy target")
                require(self.resolves < len(case["heads"]), "extra legacy ref resolution")
                head = case["heads"][self.resolves]
                self.resolves += 1
                return head

            def read_file(self, repository: str, commit: str, path: str) -> Any:
                require(repository == suite["repository"] and commit == suite["snapshot"], "legacy mixed snapshot")
                self.paths.append(path)
                raw = data[path]
                return module.FileObject(git_blob(raw), raw)

        store = Store()
        reader = module.Reader(store)
        actual = []
        for request in case["requests"]:
            try:
                actual.append({"result": reader.read(**request)})
            except module.StateOwlError as exc:
                actual.append({"error": exc.code})
        require(actual == case["responses"], "legacy response: " + case["id"])
        require(store.resolves == len(case["heads"]), "legacy ref count: " + case["id"])
        require(store.paths == case["file_paths"], "legacy path trace: " + case["id"])
    require(bool(suite["cases"]), "empty legacy suite")
    return len(suite["cases"])


def main() -> None:
    schema = read_json(HERE / "schema.json")
    suite = read_json(HERE / "fixtures.json")
    suite["cases"] = []
    for name in suite["scenario_files"]:
        require(Path(name).name == name and name.endswith("-cases.json"), "invalid scenario file")
        suite["cases"].extend(read_json(HERE / name))
    Draft202012Validator.check_schema(schema)
    whole = Draft202012Validator(schema)
    rule_ids = set(re.findall(r"\*\*([A-Z][0-9]+)\.\*\*", (HERE / "PROTOCOL.md").read_text()))
    files = {}
    for path, value in suite["files"].items():
        raw = bytes_value(value)
        require(sha256(raw) == value["digest"], "fixture digest: " + path)
        files[path] = raw
    for collection in ("schema_cases", "json_cases", "cases"):
        ids = [case["id"] for case in suite[collection]]
        require(bool(ids) and len(ids) == len(set(ids)), "empty/duplicate fixture IDs: " + collection)
    for case in suite["schema_cases"]:
        validator = Draft202012Validator({"$schema": schema["$schema"], "$defs": schema["$defs"],
                                         "$ref": "#/$defs/" + case["definition"]})
        require(validator.is_valid(case["instance"]) == case["valid"], "schema vector: " + case["id"])
    for case in suite["json_cases"]:
        try:
            strict_source(unbase64(case["base64"]))
            valid = True
        except (ValueError, UnicodeError, OverflowError):
            valid = False
        require(valid == case["valid"], "strict JSON vector: " + case["id"])
    require(bool(suite["receipt_vectors"]), "empty receipt suite")
    for vector in suite["receipt_vectors"]:
        whole.validate(vector["request"])
        preimage = receipt_preimage(vector["request"], vector["validation"])
        require(preimage == vector["preimage"], "receipt preimage")
        canonical = canonical_receipt(preimage)
        require(canonical == vector["canonical"] and sha256(canonical.encode()) == vector["digest"], "receipt digest")
        encoded = copy.deepcopy(vector["request"])
        for change in encoded["changes"]:
            if "put" in change:
                raw = bytes_value(change["put"])
                change["put"] = {"encoding": "base64", "data": base64.b64encode(raw).decode("ascii")}
        require(canonical_receipt(receipt_preimage(encoded, vector["validation"])) == canonical,
                "equal bytes changed receipt identity")
        if len(encoded["changes"]) > 1:
            encoded["changes"].reverse()
            require(canonical_receipt(receipt_preimage(encoded, vector["validation"])) != canonical,
                    "ordered transition lost order")
    for malformed in ("AB==", "AP8=\n", "AA"):
        try:
            unbase64(malformed)
        except (ValueError, UnicodeError):
            continue
        raise ValueError("accepted noncanonical base64")

    def check_record(record: dict[str, Any]) -> None:
        if record["status"] == "absent":
            return
        source = record["source"]
        raw = files[source["path"]]
        require(source["digest"] == sha256(raw), "scenario source digest")
        fmt = record["format"]
        value = json.loads(raw) if fmt == "json" else raw.decode("utf-8") if fmt == "text" else base64.b64encode(raw).decode("ascii")
        if "select" in record:
            require(isinstance(value, dict), "projection of non-object")
            require(record["missing"] == [key for key in record["select"] if key not in value], "missing fields")
            value = {key: value[key] for key in record["select"] if key in value}
        require(record["value"] == value, "scenario selected value")
        for child in record.get("expanded", []):
            check_record(child)

    for case in suite["cases"]:
        try:
            require(set(case["rules"]) <= rule_ids, "unknown rule ID")
            request, response = case["request"], case["response"]
            whole.validate(request)
            whole.validate(response)
            require(request["op"] == response["op"] and request["protocol"] == response["protocol"], "envelope mismatch")
            if "target" in response:
                require(request["target"] == response["target"], "target mismatch")
            if response.get("status") == "ok":
                require([x["key"] for x in request["records"]] == [x["key"] for x in response["records"]], "record order")
                for record in response["records"]:
                    check_record(record)
                if "snapshot" in request["at"]:
                    require(response["snapshot"] == request["at"]["snapshot"], "exact snapshot mismatch")
                for source in response.get("routing", {}).get("sources", []):
                    require(source["digest"] == sha256(files[source["path"]]), "routing digest")
            if request["op"] == "publish":
                require(response["expected"] == request["expected"] and response["operation_id"] == request["operation_id"], "publication identity")
                receipt = response.get("receipt")
                if receipt:
                    canonical = canonical_receipt(receipt_preimage(request, receipt["validation"]))
                    require(receipt["request_digest"] == sha256(canonical.encode()), "scenario receipt digest")
                    require(receipt["expected"] == request["expected"] and receipt["operation_id"] == request["operation_id"], "receipt identity")
                given = case["given"]
                outcome = response["outcome"]
                if outcome == "committed":
                    require(given.get("admission") == "established" and given.get("verification") == "complete", "unsupported committed expectation")
                elif outcome == "verification_pending":
                    require(given.get("admission") == "established", "unsupported admitted expectation")
                elif outcome == "indeterminate":
                    require(given.get("admission") == "unknown", "unsupported uncertain expectation")
                else:
                    require(given.get("admission", given.get("admission_of_this_payload")) == "excluded", "unsupported rejected expectation")
        except Exception as exc:
            raise ValueError(case["id"] + ": " + str(exc)) from exc
    legacy = check_legacy()
    print(json.dumps({"status": "passed", "schema_vectors": len(suite["schema_cases"]),
                      "scenario_pairs": len(suite["cases"]), "strict_json_vectors": len(suite["json_cases"]),
                      "receipt_vectors": len(suite["receipt_vectors"]), "legacy_reader_cases": legacy,
                      "scope": "corpus consistency and legacy behavior only; no new adapter qualification"}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Fixture check failed: " + str(exc), file=sys.stderr)
        sys.exit(1)
