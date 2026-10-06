from .transport import HTTPResponse, GitHubTransport, UrllibGitHubTransport
from .base import GitHubBase
from .read import GitHubReadMixin
from .write import GitHubWriteMixin
from .admit import GitHubAdmitMixin

class GitHubPublicationStorage(GitHubAdmitMixin, GitHubWriteMixin, GitHubReadMixin, GitHubBase):
    pass

__all__ = ["GitHubPublicationStorage", "GitHubTransport", "HTTPResponse", "UrllibGitHubTransport"]
