class RunnerError(Exception):
    """Base exception class for vibeskills-runner."""
    pass


class ValidationError(RunnerError):
    """Raised when validation fails (e.g. contract validation or schema validation)."""
    pass


class PersistenceError(RunnerError):
    """Raised when load/save operations fail or file integrity is compromised."""
    pass


class StateMachineError(RunnerError):
    """Raised when an invalid state transition is requested."""
    pass


class GitStateError(RunnerError):
    """Raised when git operations fail or repository state is invalid."""
    pass
