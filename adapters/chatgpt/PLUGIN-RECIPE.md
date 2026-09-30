# ChatGPT plugin recipe

**Description**

> stateOwl retrieves exact GitHub-backed project state through compact locators and expands linked detail only when needed.

**Custom instruction**

> When a repository uses stateOwl, fresh-resolve its configured Git ref, read the router and selected record at that exact commit, preserve repository/commit/path/blob provenance, and expand only explicitly required named links.

A ChatGPT integration should reuse the workspace's existing GitHub connection when it exposes the exact reads required by the stateOwl contract. Provider installation identifiers and private configuration are intentionally excluded from this public repository.
