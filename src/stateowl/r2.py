"""Read-only Python candidate for stateOwl/0.2-draft.3."""
from .r2_types import (
    PROTOCOL, ROUTER_V1, MAX_SAFE, RETRY, ReadFault, ReadProvider,
    ReadInstrumentation, fail, digest, git_blob, parse_git, typed_git, raw_git,
    path_valid, ref_valid, strict_json, request_valid,
)
from .r2_reader import DEFAULT_READ_CAPABILITIES, R2Reader

__all__ = [
    'PROTOCOL','ROUTER_V1','MAX_SAFE','RETRY','ReadFault','ReadProvider',
    'ReadInstrumentation','DEFAULT_READ_CAPABILITIES','R2Reader','fail','digest',
    'git_blob','parse_git','typed_git','raw_git','path_valid','ref_valid',
    'strict_json','request_valid',
]

from .r2_legacy import LegacyCompatibilityError, R2LegacyReader
__all__ += ['LegacyCompatibilityError','R2LegacyReader']
