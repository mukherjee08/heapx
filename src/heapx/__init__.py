""" heapx: A Python wrapper for a C-based heap implementation. """

# Import and expose everything from the compiled extension.
from .heapx import * # imports functions implemented in heapx.c

# Public API listing
__all__ = [name for name in globals() if not name.startswith("_")]
