"""Write files the way a Prometheus textfile collector wants them."""
import os
import tempfile


def write_atomically(path, text):
    """Write `text` to `path` so that a reader never sees a half-written file.

    node_exporter's textfile collector reads every *.prom file in its directory on each scrape,
    so the content is written to a temporary file in the same directory and renamed over the target.
    """
    directory = os.path.dirname(os.path.abspath(path))
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", suffix=".prom", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.chmod(temporary, 0o644)  # mkstemp creates 0600 files; the exporter runs as another user
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
