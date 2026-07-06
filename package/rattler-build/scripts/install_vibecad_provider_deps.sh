#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rattler_root="$(cd "${script_dir}/.." && pwd)"
repo_root="$(cd "${rattler_root}/../.." && pwd)"

env_root="${1:-${rattler_root}/.pixi/envs/default}"
if [[ ! -d "${env_root}" ]]; then
    echo "VibeCAD runtime environment not found: ${env_root}" >&2
    exit 1
fi
env_root="$(cd "${env_root}" && pwd)"

python_exe=""
if [[ -x "${env_root}/bin/python" ]]; then
    python_exe="${env_root}/bin/python"
elif [[ -x "${env_root}/python.exe" ]]; then
    python_exe="${env_root}/python.exe"
else
    echo "No Python executable found in VibeCAD runtime environment: ${env_root}" >&2
    exit 1
fi

requirements="${repo_root}/src/Mod/VibeCAD/requirements.txt"
if [[ ! -f "${requirements}" ]]; then
    echo "VibeCAD provider requirements file not found: ${requirements}" >&2
    exit 1
fi

echo "Installing VibeCAD provider SDK dependencies into ${env_root}"
"${python_exe}" -m pip install \
    --disable-pip-version-check \
    --upgrade \
    --prefer-binary \
    -r "${requirements}"
"${python_exe}" -m pip check
"${python_exe}" - <<'PY'
import importlib

for module_name in ("agents", "anthropic", "keyring"):
    importlib.import_module(module_name)

print("VibeCAD provider SDK and keyring imports ok")
PY
