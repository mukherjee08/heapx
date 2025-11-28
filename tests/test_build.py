#!/usr/bin/env python3
"""
tests/build.py

This script verifies three installation workflows on macOS (works on other POSIX systems):

  - Install a wheel from dist/*.whl
  - Install a source distribution (sdist) from dist/*.tar.gz
  - Install the project in editable mode (pip install -e .)

For each workflow,
  - create an isolated ephemeral venv so your conda environment remains untouched
  - install the artifact into that venv
  - run a small, deterministic smoke-test that imports the module and exercises the
    documented public API exported by the C module:
      heapify, push, pop, sort, remove, replace, merge
  - produce clear, actionable diagnostics on failure

Notes (important):
  - The C module defines PyInit__heapx and registers methods named exactly:
      "heapify", "push", "pop", "sort", "remove", "replace", "merge"
    The module name in C is "_heapx". Many projects provide a Python wrapper package named
    "heapx" that imports the compiled "_heapx" extension. This harness will try to import
    "heapx" first, then fallback to "_heapx".
  - Before running these tests ensure your build artifacts exist in dist/:
      python -m build
    This produces dist/*.whl and dist/*.tar.gz which the tests install.
  - Run under pytest (recommended) or directly:
      pytest -q tests/build.py
      python tests/build.py

TODO: Add the testing for MacOS, Windows, and Linux/Unix systems in the future
"""
from   __future__ import annotations
from   pathlib    import Path
from   typing     import List, Tuple
import json, subprocess, sys, tempfile

# -------------------- Configuration --------------------
MODULE_PREFERRED = "heapx" # Try this import first; most packages provide a python wrapper
MODULE_FALLBACK = "_heapx" # The compiled C extension's module name (from PyInit__heapx)
DIST_DIR = Path("dist")    # The directory for dist/* 
PROJECT_ROOT = Path.cwd()  # The wd for the root of the project
TIMEOUT = 300              # generous timeout for installs/builds (seconds)

# -------------------- Smoke test code --------------------
SMOKE_TEST = r'''
import sys
import importlib

for candidate in ("{preferred}", "{fallback}"):
  try:
    mod = importlib.import_module(candidate)
    module_name = candidate
    break
  except Exception as e:
    last_exc = e
else:
  print("IMPORT-FAILED:", last_exc, file=sys.stderr)
  raise SystemExit(2)

expected = ("heapify","push","pop","sort","remove","replace","merge")
missing = [name for name in expected if not hasattr(mod, name)]
if missing:
  print("MISSING-FUNCTIONS:", missing, "in", module_name, file=sys.stderr)
  raise SystemExit(3)

def pop_all(heap_list):
  out = []
  while len(heap_list) > 0:
    v = mod.pop(heap_list)
    out.append(v)
  return out

data = [10, 3, 5, 1, 7, 2, 9]
lst = list(data)
mod.heapify(lst)
popped = []
while len(lst)>0:
  popped.append(mod.pop(lst))
if popped != sorted(data):
  print("HEAPIFY/POP mismatch:", popped, "expected", sorted(data), file=sys.stderr)
  raise SystemExit(4)

h = []
mod.heapify(h)
mod.push(h, 4)
mod.push(h, [8, 1, 6])
collected = []
while len(h)>0:
  collected.append(mod.pop(h))
if collected != [1,4,6,8]:
  print("PUSH/POP mismatch:", collected, file=sys.stderr)
  raise SystemExit(5)

h2 = [5,2,3,9,7]
mod.heapify(h2)
res = mod.pop(h2, 3)
if not isinstance(res, list) or res != [2,3,5]:
  print("BULK-POP unexpected:", type(res), res, file=sys.stderr)
  raise SystemExit(6)

unsorted = [4,1,9,0,3]
sorted_out = mod.sort(unsorted, reverse=False, inplace=False)
if sorted_out != sorted(unsorted):
  print("SORT (copy) mismatch:", sorted_out, file=sys.stderr)
  raise SystemExit(7)

l = [2,8,1]
mod.sort(l, inplace=True)
if l != sorted([2,8,1]):
  print("SORT (inplace) mismatch:", l, file=sys.stderr)
  raise SystemExit(8)

rheap = [10,20,5,7]
mod.heapify(rheap)
count_and_items = mod.remove(rheap, indices=0, return_items=True)
if not (isinstance(count_and_items, tuple) and count_and_items[0] == 1):
  print("REMOVE unexpected return:", count_and_items, file=sys.stderr)
  raise SystemExit(9)

r = [1,4,3]
mod.heapify(r)
replaced = mod.replace(r, values=10, indices=0)
if not isinstance(replaced, int) or replaced < 0:
  print("REPLACE unexpected return:", replaced, file=sys.stderr)
  raise SystemExit(10)
p = mod.pop(r)
if p == 1:
  print("REPLACE failed, 1 still present", file=sys.stderr)
  raise SystemExit(11)

a = [0,5,8]
b = [3,7,9]
mod.heapify(a)
mod.heapify(b)
m = mod.merge(a, b)
if not hasattr(m, "__len__") or len(m) != len(a)+len(b):
  print("MERGE size mismatch", len(m), file=sys.stderr)
  raise SystemExit(12)
min_item = mod.pop(m)
if min_item != 0:
  print("MERGE min mismatch", min_item, file=sys.stderr)
  raise SystemExit(13)

print("SMOKE-OK")
sys.exit(0)
'''.format(preferred=MODULE_PREFERRED, fallback=MODULE_FALLBACK)

# -------------------- Utility subprocess functions --------------------

def run(cmd: List[str], *, cwd: Path = None, timeout: int = TIMEOUT) -> Tuple[int, str, str]:
  """Run subprocess, return (rc, stdout, stderr). Raise RuntimeError on timeout."""
  proc = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
  try: out, err = proc.communicate(timeout=timeout)
  except subprocess.TimeoutExpired:
    proc.kill(); out, err = proc.communicate()
    raise RuntimeError(f"Command timed out: {' '.join(cmd)}\nstdout:\n{out}\nstderr:\n{err}")
  return proc.returncode, out, err

def find_unique(pattern: str) -> Path:
  """Find exactly one artifact in DIST_DIR matching pattern or raise helpful error."""
  candidates = sorted(DIST_DIR.glob(pattern))
  if (not candidates):
    raise FileNotFoundError(f"No files match {pattern} in {DIST_DIR}. Ensure 'python -m build' was run.")
  if (len(candidates) > 1):
    raise FileExistsError(f"Multiple files match {pattern} in {DIST_DIR}: {', '.join(map(str, candidates))}")
  return candidates[0]

def create_venv(directory: Path) -> Path:
  """Create venv and return path to its python executable."""
  rc, out, err = run([sys.executable, "-m", "venv", str(directory)])
  if (rc != 0): raise RuntimeError(f"Failed to create venv: rc={rc}\nstdout:\n{out}\nstderr:\n{err}")
  if (sys.platform == "win32"): py = directory / "Scripts" / "python.exe"
  else: py = directory / "bin" / "python"
  if (not py.exists()): raise FileNotFoundError(f"Created venv but python executable not found at {py}")

  return py

def venv_pip_install(python: Path, specs: List[str], cwd: Path = None) -> None:
  """Upgrade pip/setuptools/wheel then pip install given specs inside venv python."""
  rc, out, err = run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], cwd=cwd)
  if (rc != 0): raise RuntimeError(f"Failed to upgrade pip/setuptools/wheel in venv: rc={rc}\nstdout:\n{out}\nstderr:\n{err}")
  cmd = [str(python), "-m", "pip", "install"] + specs
  rc, out, err = run(cmd, cwd=cwd)
  if (rc != 0): raise RuntimeError(f"pip install failed for {specs}: rc={rc}\nstdout:\n{out}\nstderr:\n{err}")

  return None

def run_smoke(python: Path) -> None:
  """Run the SMOKE_TEST code inside the venv's python; validate output contains SMOKE-OK."""
  rc, out, err = run([str(python), "-c", SMOKE_TEST])
  if (rc != 0): raise RuntimeError(f"Smoke test failed: rc={rc}\nstdout:\n{out}\nstderr:\n{err}")
  if ("SMOKE-OK" not in out): raise RuntimeError(f"Smoke test did not print SMOKE-OK. stdout:\n{out}\nstderr:\n{err}")

  return None

# -------------------- Test helpers --------------------

def _install_and_test(specs: List[str], cwd: Path = None) -> None:
  """Create ephemeral venv, install given package specs, run smoke test, clean up."""
  with tempfile.TemporaryDirectory(prefix="heapx-test-") as td:
    venv_dir = Path(td) / "venv"
    python = create_venv(venv_dir)
    venv_pip_install(python, specs, cwd=cwd)
    run_smoke(python)

  return None

# -------------------- Pytest-compatible tests --------------------

def test_install_wheel_and_smoke():
  if (not DIST_DIR.exists()): raise AssertionError(f"{DIST_DIR} missing; run 'python -m build' first")
  wheel = find_unique("heapx-*.whl")
  _install_and_test([str(wheel)])

  return None

def test_install_sdist_and_smoke():
  if (not DIST_DIR.exists()): raise AssertionError(f"{DIST_DIR} missing; run 'python -m build' first")
  sdist = find_unique("heapx-*.tar.gz")
  _install_and_test([str(sdist)])

  return None

def test_install_editable_and_smoke():
  _install_and_test(["-e", "."], cwd=PROJECT_ROOT)

  return None

# -------------------- Allow running as a script --------------------

def main():

  results = {}
  try:
    test_install_wheel_and_smoke()
    results["wheel"] = "ok"
  except Exception as e:
    results["wheel"] = f"error: {e}"

  try:
    test_install_sdist_and_smoke()
    results["sdist"] = "ok"
  except Exception as e:
    results["sdist"] = f"error: {e}"

  try:
    test_install_editable_and_smoke()
    results["editable"] = "ok"
  except Exception as e:
    results["editable"] = f"error: {e}"

  print(json.dumps(results, indent=2))
  if any(v != "ok" for v in results.values()): sys.exit(1)
  print("All install-and-smoke checks passed.")

if (__name__ == "__main__"): main()
