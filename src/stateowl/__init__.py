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

__all__ = [
    "FileObject",
    "GitHubStore",
    "Locator",
    "Reader",
    "StateOwlError",
    "StateStore",
    "git_blob_oid",
]

__version__ = "0.1.0"
