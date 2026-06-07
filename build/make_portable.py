"""Assemble a portable, no-install Soma bundle for a target OS.

The bundle contains a relocatable CPython (from python-build-standalone) with all
dependencies installed, the built frontend, and a double-click launcher. The user
copies the folder to a USB stick and runs the launcher — no admin rights, no install.

Usage:
    python build/make_portable.py --target {windows-x64,macos-arm64,linux-x64}
                                  [--output dist]

Run AFTER building the frontend (so soma/static exists):
    cd frontend && npm ci && npm run build

Intended to run inside the matching OS runner in CI (the standalone Python is
OS-specific and cannot be cross-built).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Target -> python-build-standalone triple.
TRIPLES = {
    "windows-x64": "x86_64-pc-windows-msvc",
    "macos-arm64": "aarch64-apple-darwin",
    "linux-x64": "x86_64-unknown-linux-gnu",  # local dev/testing only, not shipped
}

PBS_API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
PY_SERIES = "3.11"

# Pinned fallback used when the GitHub API is unavailable (e.g. rate-limited).
# Direct release downloads work even where api.github.com is blocked.
PINNED_TAG = "20241016"
PINNED_PYVER = "3.11.10"
_PBS_BASE = "https://github.com/astral-sh/python-build-standalone/releases/download"


def pinned_url(triple: str) -> str:
    name = f"cpython-{PINNED_PYVER}%2B{PINNED_TAG}-{triple}-install_only.tar.gz"
    return f"{_PBS_BASE}/{PINNED_TAG}/{name}"


def _gh_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "soma-build"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return r.read()


def find_python_asset(triple: str) -> str:
    """Return the download URL of the install_only standalone CPython for the triple.

    Prefers the latest release via the GitHub API; falls back to a pinned version
    when the API is unavailable (the direct download host stays reachable)."""
    try:
        data = json.loads(_gh_get(PBS_API))
        pat = re.compile(
            rf"cpython-{re.escape(PY_SERIES)}\.\d+\+\d+-{re.escape(triple)}-install_only\.tar\.gz$"
        )
        for asset in data.get("assets", []):
            if pat.search(asset["name"]):
                return asset["browser_download_url"]
        raise RuntimeError("asset not found in latest release")
    except Exception as exc:  # API blocked/rate-limited -> use pinned fallback
        print(f"  GitHub API unavailable ({exc}); using pinned {PINNED_PYVER}")
        return pinned_url(triple)


def download(url: str, dest: Path) -> None:
    print(f"  downloading {url}")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "soma-build"})) as r:
        dest.write_bytes(r.read())


def python_exe(bundle: Path, target: str) -> Path:
    if target.startswith("windows"):
        return bundle / "python" / "python.exe"
    return bundle / "python" / "bin" / "python3"


LAUNCHER_SH = """#!/bin/bash
# Soma portable launcher (macOS / Linux). Double-click in Finder, or run in a terminal.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SOMA_DATA_DIR="$DIR/data"
# Clear the macOS "downloaded from internet" quarantine on first run, if present.
xattr -dr com.apple.quarantine "$DIR" 2>/dev/null || true
"$DIR/python/bin/python3" -m soma
"""

LAUNCHER_BAT = """@echo off
rem Soma portable launcher (Windows). Double-click to run.
set "DIR=%~dp0"
set "SOMA_DATA_DIR=%DIR%data"
"%DIR%python\\python.exe" -m soma
echo.
echo Soma has stopped. You can close this window.
pause >nul
"""

README_TXT = """Soma - portable medical recording viewer
=========================================

To run:
  - Windows: double-click  Soma.bat
  - macOS:   double-click  Soma.command
             (first time: right-click -> Open, to get past Gatekeeper)

A console window opens and your web browser launches at http://127.0.0.1:8000.
Keep the console window open while using Soma; close it to stop.

Everything runs locally on this machine. Recordings and reconstructions are
stored in the "data" folder next to this file (on the USB stick). Delete that
folder to remove all patient data.

Not for primary diagnosis.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, choices=sorted(TRIPLES))
    ap.add_argument("--output", default="dist")
    ap.add_argument("--python-url", default=os.environ.get("SOMA_PYTHON_URL"),
                    help="override the standalone CPython download URL")
    args = ap.parse_args()

    target = args.target
    triple = TRIPLES[target]
    out_root = REPO_ROOT / args.output
    bundle = out_root / "Soma"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    if not (REPO_ROOT / "soma" / "static" / "index.html").exists():
        sys.exit("Frontend not built: run `cd frontend && npm ci && npm run build` first.")

    print(f"[1/5] Locating standalone CPython for {triple}")
    url = args.python_url or find_python_asset(triple)

    with tempfile.TemporaryDirectory() as tmp:
        tarball = Path(tmp) / "python.tar.gz"
        print("[2/5] Downloading CPython")
        download(url, tarball)
        print("[3/5] Extracting CPython")
        with tarfile.open(tarball) as t:
            t.extractall(bundle)  # creates bundle/python/

    py = python_exe(bundle, target)
    if not py.exists():
        sys.exit(f"expected python at {py}, not found")

    print("[4/5] Installing Soma + dependencies into the bundle")
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(py), "-m", "pip", "install", str(REPO_ROOT)], check=True)

    # Ensure the freshly built frontend is present in the installed package.
    installed_static = next(bundle.glob("python/**/site-packages/soma/static"), None)
    if installed_static:
        shutil.rmtree(installed_static)
        shutil.copytree(REPO_ROOT / "soma" / "static", installed_static)

    print("[5/5] Writing launcher + README")
    (bundle / "README.txt").write_text(README_TXT)
    if target.startswith("windows"):
        (bundle / "Soma.bat").write_text(LAUNCHER_BAT, newline="\r\n")
    else:
        launcher = bundle / "Soma.command"
        launcher.write_text(LAUNCHER_SH)
        launcher.chmod(0o755)

    # Windows: zip (Explorer-native). macOS/Linux: gztar, which preserves the
    # launcher's executable bit so double-click works after extraction.
    fmt = "zip" if target.startswith("windows") else "gztar"
    archive = shutil.make_archive(
        str(out_root / f"Soma-{target}"), fmt, root_dir=bundle.parent, base_dir="Soma"
    )
    print(f"\nDone: {archive}")


if __name__ == "__main__":
    main()
