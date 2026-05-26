"""Top-level compatibility package used by tests.

Re-exports selected symbols from backend.app.services so tests can import
`app.services` as a convenience during local test runs.
"""

from . import services  # expose app.services

__all__ = ["services"]
