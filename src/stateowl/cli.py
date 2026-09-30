"""Command-line interface for direct GitHub reads."""
from __future__ import annotations

import argparse
import json
import sys

from .core import Reader, StateOwlError
from .github import GitHubStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stateowl",
        description="Read only the GitHub-backed state needed for one route.",
    )
    parser.add_argument("repository", help="GitHub repository in owner/name form")
    parser.add_argument("route", help="route name from the stateOwl router")
    parser.add_argument("--ref", default="refs/heads/main", help="fully qualified Git ref")
    parser.add_argument("--router", default=".stateowl/router.json", help="router path")
    parser.add_argument("--expand", action="append", default=[], metavar="LINK", help="expand one named link; repeatable")
    parser.add_argument("--expected-head", help="refuse the read if the mutable ref no longer points to this exact commit")
    parser.add_argument("--api-base", default="https://api.github.com", help="GitHub API base, including GitHub Enterprise")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = Reader(GitHubStore(api_base=args.api_base)).read(
            args.repository,
            args.route,
            ref=args.ref,
            router_path=args.router,
            expand=args.expand,
            expected_head=args.expected_head,
        )
    except StateOwlError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc)}}, separators=(",", ":")))
        return 2
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
