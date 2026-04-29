#!/usr/bin/env python3
"""Replace ${VAR} in manifest text with values from the process environment.

Uses only the Python standard library (no gettext envsubst). Patterns must be
simple shell-style names: ${NAME} where NAME is [A-Za-z_][A-Za-z0-9_]*.
Missing variables become empty strings, matching typical envsubst behaviour.
Reads stdin, writes stdout."""
from __future__ import annotations

import os
import re
import sys

_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def substitute(text: str) -> str:
    return _PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), text)


def main() -> None:
    data = sys.stdin.read()
    sys.stdout.write(substitute(data))


if __name__ == "__main__":
    main()
