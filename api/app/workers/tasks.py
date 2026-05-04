"""
Raven — Background Tasks
Runs scoring, analytics, and report generation as FastAPI background tasks.
No Redis or Celery required for MVP.
"""

import threading
from typing import Callable


def run_in_thread(fn: Callable, *args, **kwargs):
    """Fire-and-forget background execution."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t
