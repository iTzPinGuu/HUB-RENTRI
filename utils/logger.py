"""
Logging utilities for RENTRI Manager.

Provides debug logging functionality for development and troubleshooting.
"""

import sys
from typing import Any


def dbg(msg: str) -> None:
    """
    Print debug message to stderr.

    Args:
        msg: Debug message to print
    """
    print(f"[DEBUG] {msg}", file=sys.stderr, flush=True)
