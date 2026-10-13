#!/usr/bin/env bash
# Copies the Supertext Python SDK into PKG/_vendor/supertext (import it as
# PKG._vendor.supertext). Source: https://github.com/Supertext/Supertext-API-SDK-and-Guide
# (sdk/python).
#
#   scripts/sync-sdk.sh            # latest main
#   scripts/sync-sdk.sh v0.2.0     # a tag or commit
#   SDK_DIR=../Supertext-API-SDK-and-Guide scripts/sync-sdk.sh   # a local checkout
#
# Until the SDK is published on PyPI, the package ships this copy; then it becomes a normal
# dependency ("supertext-sdk") and this script goes away.
set -euo pipefail
cd "$(dirname "$0")/.."
pkg="wagtail_supertext"
ref="${1:-main}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
if [ -n "${SDK_DIR:-}" ]; then
  src="$(cd "$SDK_DIR" && pwd)"
else
  git clone -q https://github.com/Supertext/Supertext-API-SDK-and-Guide "$work/sdk"
  git -C "$work/sdk" checkout -q "$ref"
  src="$work/sdk"
fi
commit="$(git -C "$src" rev-parse --short HEAD)"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$src/sdk/python/pyproject.toml" | head -1)"
dest="$pkg/_vendor/supertext"
rm -rf "$dest"
mkdir -p "$dest"
cp "$src"/sdk/python/src/supertext/*.py "$src/sdk/python/src/supertext/py.typed" "$dest/"
cp "$src/sdk/python/LICENSE" "$dest/LICENSE"
[ -f "$pkg/_vendor/__init__.py" ] || printf '"""Third-party code shipped with this package (see each folder\x27s SOURCE)."""\n' > "$pkg/_vendor/__init__.py"
printf 'Supertext SDK for Python %s, commit %s\nhttps://github.com/Supertext/Supertext-API-SDK-and-Guide/tree/%s/sdk/python\nCopied by scripts/sync-sdk.sh. Do not edit: change the SDK repository and sync again.\n' "$version" "$commit" "$commit" > "$dest/SOURCE"
printf '%s\n' "$version" > "$dest/VERSION"
echo "$dest: Supertext Python SDK $version ($commit)"
