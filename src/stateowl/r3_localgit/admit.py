from __future__ import annotations

import base64
from pathlib import Path
import tempfile
from typing import Any, Mapping

from ..r3_publish import PublicationFault

class LocalGitAdmitMixin:
        def admit(
            self,
            target: Mapping[str, Any],
            expected: str,
            candidate: Mapping[str, Any],
            message: str,
        ) -> Mapping[str, Any]:
            self._target(target)
            expected_raw = self._raw(expected)
            old = self.tree(target, expected)
            with tempfile.TemporaryDirectory(prefix="stateowl-r3-index-") as directory:
                index_path = str(Path(directory) / "index")
                env = {"GIT_INDEX_FILE": index_path}
                read_tree = self._run(["read-tree", expected_raw], env=env, check=False)
                if read_tree.returncode != 0:
                    raise PublicationFault("SNAPSHOT_UNAVAILABLE")
                for path in sorted(set(old) | set(candidate), key=lambda value: value.encode("utf-8")):
                    before = old.get(path)
                    after = candidate.get(path)
                    if before == after:
                        continue
                    if after is None:
                        result = self._run(["update-index", "--force-remove", "--", path], env=env, check=False)
                        if result.returncode != 0:
                            raise PublicationFault("PROVIDER_UNAVAILABLE")
                        continue
                    mode = after.get("mode") if isinstance(after, Mapping) else None
                    encoded = after.get("base64") if isinstance(after, Mapping) else None
                    if mode not in {"100644", "100755"} or not isinstance(encoded, str):
                        raise PublicationFault("INVALID_SOURCE")
                    try:
                        contents = base64.b64decode(encoded, validate=True)
                        if base64.b64encode(contents).decode("ascii") != encoded:
                            raise ValueError
                    except (ValueError, UnicodeError):
                        raise PublicationFault("INVALID_SOURCE") from None
                    blob = self._run(["hash-object", "-w", "--stdin"], input_bytes=contents, check=False)
                    if blob.returncode != 0:
                        raise PublicationFault("PROVIDER_UNAVAILABLE")
                    oid = blob.stdout.decode("ascii").strip()
                    updated = self._run(
                        ["update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}"],
                        env=env,
                        check=False,
                    )
                    if updated.returncode != 0:
                        raise PublicationFault("PROVIDER_UNAVAILABLE")
                written = self._run(["write-tree"], env=env, check=False)
                if written.returncode != 0:
                    raise PublicationFault("PROVIDER_UNAVAILABLE")
                tree_oid = written.stdout.decode("ascii").strip()

            commit_env = {
                "GIT_AUTHOR_NAME": self.author_name,
                "GIT_AUTHOR_EMAIL": self.author_email,
                "GIT_COMMITTER_NAME": self.author_name,
                "GIT_COMMITTER_EMAIL": self.author_email,
            }
            commit = self._run(
                ["commit-tree", tree_oid, "-p", expected_raw],
                input_bytes=message.encode("utf-8"),
                env=commit_env,
                check=False,
            )
            if commit.returncode != 0:
                raise PublicationFault("PROVIDER_UNAVAILABLE")
            candidate_raw = commit.stdout.decode("ascii").strip()
            candidate_typed = self._typed(candidate_raw)

            # Object creation above is not admission. This is the sole ref mutation.
            update = self._run(
                ["update-ref", target["namespace"], candidate_raw, expected_raw],
                check=False,
            )
            if update.returncode != 0:
                try:
                    current = self.resolve(target)
                except PublicationFault as exc:
                    if exc.code == "NOT_FOUND":
                        return {"status": "conflict"}
                    raise PublicationFault("PROVIDER_UNAVAILABLE") from None
                if current != expected:
                    return {"status": "conflict"}
                raise PublicationFault("PROVIDER_UNAVAILABLE")
            return {"status": "admitted", "snapshot": candidate_typed}
