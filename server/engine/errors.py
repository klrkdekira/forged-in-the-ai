class EngineError(Exception):
    """Base class for errors raised when a caller asks the engine to do
    something illegal. The engine refuses; it never guesses (CLAUDE.md)."""


class ClockFullError(EngineError):
    """Raised when ticking a clock that has no remaining segments."""


class ClockEmptyError(EngineError):
    """Raised when ticking a tug-of-war clock down past zero segments."""
