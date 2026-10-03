"""Test-only codecs; no storage, credentials, network or production entrypoint."""
from __future__ import annotations
import atexit
import base64
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
from typing import Any

HERE = Path(__file__).resolve().parent
VERSION = "stateowl/0.2-draft.3"
MAX_SAFE = 9007199254740991

class Fault(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

class ECMAScript:
    """Persistent local test oracle, independent of the Python number spelling."""
    def __init__(self):
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Protocol checks require Node.js for the test-only ECMAScript oracle")
        self.process = subprocess.Popen([node, str(HERE / "ecma_oracle.js")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        atexit.register(self.close)
    def call(self, **request):
        self.process.stdin.write(json.dumps(request, ensure_ascii=True, allow_nan=False) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("ECMAScript oracle stopped")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["value"]
    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()

_ORACLE = None
def oracle():
    global _ORACLE
    if _ORACLE is None: _ORACLE = ECMAScript()
    return _ORACLE

def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def git_blob(raw: bytes, algorithm="sha1") -> str:
    return "git:" + algorithm + ":" + hashlib.new(algorithm, b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def unbase64(text: str) -> bytes:
    try:
        raw = base64.b64decode(text, validate=True)
        if base64.b64encode(raw).decode() != text: raise ValueError()
        return raw
    except (ValueError, UnicodeError, TypeError):
        raise Fault("INVALID_REQUEST") from None

def byte_value(item: dict) -> bytes:
    if item["encoding"] == "base64": return unbase64(item["data"])
    try: return item["data"].encode("utf-8")
    except UnicodeError: raise Fault("INVALID_REQUEST") from None

def strict(raw: bytes, *, source=False, depth=64) -> Any:
    bad = "INVALID_SOURCE" if source else "INVALID_REQUEST"
    numeric = "NUMBER_UNREPRESENTABLE" if source else bad
    try:
        if raw.startswith(b"\xef\xbb\xbf"): raise Fault(bad)
        text = raw.decode("utf-8")
        # Guard depth before parsing/buffering nested values. Grammar still follows.
        n=0; quoted=False; escaped=False
        for c in text:
            if quoted:
                if escaped: escaped=False
                elif c == "\\": escaped=True
                elif c == '"': quoted=False
            elif c == '"': quoted=True
            elif c in "[{":
                n += 1
                if n > depth: raise Fault("LIMIT_EXCEEDED")
            elif c in "]}": n -= 1
        def pairs(items):
            out={}
            for k,v in items:
                if k in out: raise Fault(bad)
                out[k]=v
            return out
        def constant(_): raise Fault(bad)
        value=json.loads(text, object_pairs_hook=pairs, parse_int=Decimal,
                         parse_float=Decimal, parse_constant=constant)
        decimals=[]
        def collect(v):
            if isinstance(v,str): v.encode("utf-8")
            elif isinstance(v,Decimal):
                if not v.is_finite(): raise Fault(numeric)
                if v.is_zero() and v.is_signed(): raise Fault(bad)
                if v == v.to_integral_value():
                    if abs(v) > MAX_SAFE: raise Fault(numeric)
                else: decimals.append(v)
            elif isinstance(v,dict):
                for k,x in v.items(): collect(k); collect(x)
            elif isinstance(v,list):
                for x in v: collect(x)
        collect(value)
        if decimals:
            spellings=oracle().call(op="numbers", values=[str(v) for v in decimals])
            if any(s is None or Decimal(s) != v for v,s in zip(decimals,spellings)):
                raise Fault(numeric)
        def convert(v):
            if isinstance(v,Decimal): return int(v) if v == v.to_integral_value() else float(v)
            if isinstance(v,dict): return {k:convert(x) for k,x in v.items()}
            if isinstance(v,list): return [convert(x) for x in v]
            return v
        return convert(value)
    except Fault: raise
    except (ValueError, UnicodeError, OverflowError, RecursionError): raise Fault(bad) from None

def jcs(value: Any) -> bytes:
    """Full JCS serialization via the test-only ECMAScript oracle."""
    return oracle().call(op="canonical",value=value).encode("utf-8")

def restricted_jcs(value: Any) -> bytes:
    """Exact JCS restricted to scalar strings, safe integers, booleans and null.

    The PublicationIdentity schema separately closes its fixed ASCII keys.
    UTF-16 sorting is used even in this restricted implementation.
    """
    if value is None: return b"null"
    if type(value) is bool: return b"true" if value else b"false"
    if type(value) is int:
        if not 0 <= value <= MAX_SAFE: raise Fault("INVALID_REQUEST")
        return str(value).encode()
    if isinstance(value,str):
        try: return json.dumps(value,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()
        except UnicodeError: raise Fault("INVALID_REQUEST") from None
    if isinstance(value,list): return b"[" + b",".join(restricted_jcs(x) for x in value) + b"]"
    if isinstance(value,dict):
        return b"{" + b",".join(restricted_jcs(k)+b":"+restricted_jcs(value[k]) for k in sorted(value,key=lambda s:s.encode("utf-16be"))) + b"}"
    raise Fault("INVALID_REQUEST")

def identity(request: dict) -> dict:
    changes=[]
    for c in sorted(request["changes"],key=lambda x:x["path"].encode()):
        if "put" in c:
            raw=byte_value(c["put"])
            changes.append({"path":c["path"],"put":{"digest":digest(raw),"bytes":len(raw)}})
        else: changes.append({"path":c["path"],"delete":True})
    return {"protocol":request["protocol"],"target":request["target"],"expected":request["expected"],"changes":changes,"validation":request["validation"]}

def request_digest(request: dict) -> str:
    return digest(restricted_jcs(identity(request)))

def receipt_message(request: dict) -> str:
    return "stateOwl publication\n\nStateOwl-Receipt: " + base64.b64encode(restricted_jcs(identity(request))).decode() + "\n"

def receipt_identity(message: str, validate) -> dict | None:
    """Parse only G4's two complete message forms; never normalize a message."""
    marker="StateOwl-Receipt:"
    if not isinstance(message,str): raise Fault("INVALID_SOURCE")
    if marker not in message: return None
    try:
        match=re.fullmatch(r"(?:stateOwl publication\n\n)?StateOwl-Receipt: ([A-Za-z0-9+/]+={0,2})\n",message)
        if match is None: raise ValueError()
        raw=unbase64(match.group(1)); v=strict(raw)
        if not validate(v) or restricted_jcs(v)!=raw: raise ValueError()
        paths=[x["path"] for x in v["changes"]]
        if paths!=sorted(set(paths),key=lambda x:x.encode()): raise ValueError()
        return v
    except (ValueError, KeyError, TypeError): raise Fault("INVALID_SOURCE") from None
