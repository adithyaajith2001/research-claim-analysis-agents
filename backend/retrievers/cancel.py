"""
Stop switch for the analysis that is running right now.

Only one analysis runs at a time, so one shared switch is enough. The
pipeline checks it before each language-model call and at every progress
step, then stops with AnalysisCancelled.

AnalysisCancelled derives from BaseException on purpose: the pipeline has
many `except Exception` blocks that keep going after a failure, and a stop
request must not be swallowed by them.
"""

import threading

_STOP = threading.Event()


class AnalysisCancelled(BaseException):
    """Raised inside the pipeline when the user stops the analysis."""


def request_stop() -> None:
    _STOP.set()


def clear_stop() -> None:
    _STOP.clear()


def stop_requested() -> bool:
    return _STOP.is_set()


def check_cancelled() -> None:
    if _STOP.is_set():
        raise AnalysisCancelled()
