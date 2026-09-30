"""Read a stateOwl-enabled public repository without a checkout."""
from stateowl import GitHubStore, Reader

reader = Reader(GitHubStore())
result = reader.read(
    "OWNER/REPOSITORY",
    "release",
    ref="refs/heads/main",
)
print(result)
