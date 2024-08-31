class NetworkReplayError(Exception):
    """Base class for exceptions in this module."""

    pass


class RecordingExistsError(NetworkReplayError):
    """Exception raised when a recording already exists."""

    pass


class RecordingDisabledError(NetworkReplayError):
    """Exception raised when a recording is disabled."""

    pass
