"""Exception hierarchy.

Every error raised on purpose by the package derives from :class:`ERDRError`, so applications
(CLI, GUI) can report them as user-facing messages and let genuine bugs surface as tracebacks.
"""


class ERDRError(Exception):
    """Base class of all deliberate errors of the package."""


class ConfigError(ERDRError, ValueError):
    """An experiment configuration is invalid (unknown key, value out of range, bad format)."""


class DatasetError(ERDRError, ValueError):
    """A dataset cannot be loaded or does not match its schema."""


class RegistryError(ERDRError, LookupError):
    """A plug-in name is unknown or registered twice."""


class AlgorithmUndefinedError(ERDRError, RuntimeError):
    """ERDR is undefined for the given data and parameters.

    Examples: the sample has a single class (no object has an enemy, so r(Sᵢ) does not exist), or
    k exceeds the number of neighbours an object has, so z(Sᵢ, k) does not exist.
    """
