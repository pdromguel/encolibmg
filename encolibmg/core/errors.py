class Cancelled(Exception):
    """The user pressed Cancel."""


class AlreadyExists(Exception):
    """A track with this base name is already in the library."""


class NoAudioMatch(Exception):
    """No YouTube audio has a duration close enough to the synced lyrics."""
