"""Pytest configuration with automatic build and cleanup."""
import shutil, subprocess, pytest # type: ignore
from   pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR     = PROJECT_ROOT / "dist"
BUILD_DIR    = PROJECT_ROOT / "build"
SRC_DIR      = PROJECT_ROOT / "src"

def pytest_collection_finish(session):
  """Print test cases after collection, before execution."""
  window_size = 66
  print("\n" + "="*window_size)
  print("COLLECTED TEST CASES:")
  print("="*window_size)
  for i, item in enumerate(session.items, 1):
    print(f"  {i}. {item.nodeid}")
  print("="*window_size + "\n")

@pytest.fixture(scope="session", autouse=True)
def build_distributions():
  """Build wheel and sdist before tests, cleanup after."""

  subprocess.run(
    ["python", "-m", "build", "--sdist", "--wheel"],
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
  for egg_dir in SRC_DIR.glob("**/*.egg-info"): shutil.rmtree(egg_dir)
  
  # Cleanup compiled extensions (.so, .pyd, .dll)
  for so_file in SRC_DIR.glob("**/*.so"): so_file.unlink()
  for pyd_file in SRC_DIR.glob("**/*.pyd"): pyd_file.unlink()
  for dll_file in SRC_DIR.glob("**/*.dll"): dll_file.unlink()
