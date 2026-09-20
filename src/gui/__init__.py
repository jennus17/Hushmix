"""GUI package.

Import concrete modules directly (``from gui.app import HushmixApp``) so that
importing ``gui`` never pulls in the whole widget tree - the previous eager
re-exports created circular imports between ``gui.app`` and the popup windows.
"""

__all__ = []
