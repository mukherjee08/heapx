'''
Pytest's configuration & testing (conftest) with automatic build and cleanup.
This file is automatically discovered by pytest.
*This is the 'configuration/infrastructure file', and not a test file*.

# Implementation Analysis

(HOOK) def pytest_configure(config):
  Runs once at 'pytest' startup, before the test collection.
  Installs heapx in editable mode so the C extension is compiled and importable.

(HOOK) def pytest_collection_finish(session):
  Runs after all tests are collected but before execution. 
  Prints a numbered list of all test cases for visibility.

(Session-scoped fixture) def build_distributions():
  Automatically runs for every test session. 
  Builds wheel/sdist before tests, cleans up all artifacts after tests complete.
'''

import shutil, subprocess, sys, pytest
from   pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent # Get the root dir
DIST_DIR     = PROJECT_ROOT / "dist"        # Get the dist distribution dir
BUILD_DIR    = PROJECT_ROOT / "build"       # Get the build distribution dir
SRC_DIR      = PROJECT_ROOT / "src"         # Get the src distribution dir

def pytest_configure(config):
  """Build and install package before test collection."""
  subprocess.run(
    [sys.executable, "-m", "pip", "install", "-e", ".", "--force-reinstall", "--no-deps", "-q"],
    cwd=PROJECT_ROOT, check=True
  )

  return None

def pytest_collection_finish(session):
  """Print test cases after collection, before execution."""
  window_size = shutil.get_terminal_size().columns
  print("\n" + "="*window_size)
  print("COLLECTED TEST CASES:")
  print("="*window_size)
  for i, item in enumerate(session.items, 1):
    print(f"  {i}. {item.nodeid}")
  print("="*window_size + "\n")

  return None

@pytest.fixture(scope="session", autouse=True)
def build_distributions():
  """Build wheel and sdist for distribution tests."""
  subprocess.run(
    [sys.executable, "-m", "build", "--sdist", "--wheel"],
    cwd=PROJECT_ROOT,
    check=True,
    capture_output=True
  )
  
  yield # Run all tests

  # Cleanup build artifacts
  if DIST_DIR.exists() : shutil.rmtree(DIST_DIR)
  if BUILD_DIR.exists(): shutil.rmtree(BUILD_DIR)
  
  # Cleanup egg-info directories
  for egg_dir in PROJECT_ROOT.glob("*.egg-info"): shutil.rmtree(egg_dir)
  for egg_dir in SRC_DIR.glob("**/*.egg-info")  : shutil.rmtree(egg_dir)
  
  # Cleanup compiled extensions (.so, .pyd, .dll)
  for so_file in SRC_DIR.glob("**/*.so")  : so_file.unlink()
  for pyd_file in SRC_DIR.glob("**/*.pyd"): pyd_file.unlink()
  for dll_file in SRC_DIR.glob("**/*.dll"): dll_file.unlink()
  
  # Cleanup __pycache__ directories
  for pycache in PROJECT_ROOT.glob("**/__pycache__"): 
    shutil.rmtree(pycache, ignore_errors=True)

  return None
