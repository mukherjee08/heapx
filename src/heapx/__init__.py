"""heapx: Ultra-optimized heap operations for Python."""

import importlib.metadata as _metadata

# ---------------------------------------------------------------------------
# 1. Dynamic Version Resolution
# ---------------------------------------------------------------------------
# Instead of hardcoding the version, we retrieve it from the installed package
# metadata. This ensures 'heapx.__version__' always matches 'pyproject.toml'.
try:
  __version__ = _metadata.version("heapx")
except _metadata.PackageNotFoundError:
  # Fallback if the package is not installed (e.g., local development without -e)
  __version__ = "0.0.0+unknown"

# ---------------------------------------------------------------------------
# 2. C-Extension Loading
# ---------------------------------------------------------------------------
# We attempt to import the compiled C extension. Based on your setup.py,
# the extension is named 'heapx._heapx', which appears as a relative import.
_ext = None

try:
  # Attempt to import the internal C module (usually _heapx)
  from . import _heapx as _ext
except ImportError:
  # If the direct relative import fails, the binary might not be built.
  pass

if (_ext is None):
  # Provide a professional, actionable error message if loading fails
  raise ImportError(
    "The compiled 'heapx' extension is not available. This usually means "
    "the C extension was not built correctly.\n"
    "  - If you installed from source, ensure you have a C compiler available.\n"
    "  - If you are developing, run: pip install -e ."
  )

# ---------------------------------------------------------------------------
# 3. API Exposure
# ---------------------------------------------------------------------------
# We hoist the C functions (push, pop, etc.) from the internal extension
# into the top-level namespace so users can call `heapx.push()` directly.

# Identify all public attributes (those not starting with '_') in the C module
_public_names = [name for name in dir(_ext) if not name.startswith("_")]

# Update the current module's globals to include these C functions
globals().update({name: getattr(_ext, name) for name in _public_names})

# define __all__ to control what is exported when users run 'from heapx import *'
__all__ = _public_names + ["__version__"]
