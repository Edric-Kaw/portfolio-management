"""Fail closed when publication files differ from the reviewed text snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "publication-manifest.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(data):
    # Git may normalize CRLF when staging on Windows.
    text = data.decode("utf-8-sig").replace("\r\n", "\n")
    if "\x00" in text:
        raise ValueError("binary content is not approved")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="verify index contents rather than working files")
    args = parser.parse_args()
    manifest_bytes = (ROOT / MANIFEST).read_bytes()
    expected = json.loads(manifest_bytes)["files"]
    if args.staged:
        paths = git("ls-files", "-z").decode().split("\0")
    else:
        paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    actual = set(filter(None, paths))
    approved = set(expected) | {MANIFEST}
    failures = []
    for path in sorted(actual - approved):
        failures.append(f"Unreviewed file: {path}")
    for path in sorted(approved - actual):
        failures.append(f"Missing reviewed file: {path}")
    for path in sorted(actual & approved):
        try:
            if args.staged:
                mode = git("ls-files", "--stage", "--", path).split(None, 1)[0]
                if mode not in (b"100644", b"100755"):
                    raise ValueError("links and submodules are not approved")
                data = git("show", f":{path}")
            else:
                source = ROOT / path
                if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
                    raise ValueError("linked files are not approved")
                data = source.read_bytes()
            target = digest(manifest_bytes) if path == MANIFEST else expected[path]
            if digest(data) != target:
                failures.append(f"Changed since review: {path}")
        except (ValueError, OSError, subprocess.CalledProcessError) as exc:
            failures.append(f"Cannot verify {path}: {type(exc).__name__}")
    if failures:
        print("PUBLICATION BLOCKED\n" + "\n".join(failures))
        return 1
    print(f"PASS: {len(actual)} reviewed text files; no additional or changed files.")
    print("This verifies the reviewed snapshot, not undiscovered sensitive content or Git commit identities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
