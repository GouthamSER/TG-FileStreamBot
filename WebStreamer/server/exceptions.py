
class InvalidHash(Exception):
    message = "Invalid hash"

class FIleNotFound(Exception):
    message = "File not found"


class StreamError(Exception):
    """Raised when a part of the file could not be fetched after all retries.

    Never swallowed: the HTTP layer aborts the connection so the downloader
    sees an incomplete body and can resume with a Range request, instead of
    getting a silently truncated (corrupt) file.
    """
