"""Domain error types (pure; no framework dependency).

``AuthorizationError`` is raised when a verified principal is not entitled to the requested
resource. The API layer maps it to 403 (authorise against the verified principal, and return 403
rather than a 404 that would leak whether the resource exists).
"""

from __future__ import annotations


class AuthorizationError(Exception):
    """The verified principal is not entitled to the requested object (mapped to HTTP 403)."""


class ScopeError(Exception):
    """The requested scope resolved to nothing usable (e.g. no dependencies in scope)."""
