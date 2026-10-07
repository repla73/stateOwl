"""stateOwl: focused, exact GitHub-backed state resolution."""

from .core import (
    FileObject,
    Locator,
    Reader,
    StateOwlError,
    StateStore,
    git_blob_oid,
)
from .github import GitHubStore
from .observe import (
    DEFAULT_OBSERVE_CAPABILITIES,
    HMACTokenService,
    ObserveInstrumentation,
    ObserveTokenService,
    Observer,
)

__all__ = [
    "DEFAULT_OBSERVE_CAPABILITIES",
    "FileObject",
    "GitHubStore",
    "HMACTokenService",
    "Locator",
    "ObserveInstrumentation",
    "ObserveTokenService",
    "Observer",
    "Reader",
    "StateOwlError",
    "StateStore",
    "git_blob_oid",
]

__version__ = "0.2.0"
