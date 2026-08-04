#!/usr/bin/env python
"""Validate explicitly approved small OOF probability files tracked in Git."""

from __future__ import annotations

import json
from pathlib import Path

from open_cancer.shared_oof import validate_shared_oof_repository


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(validate_shared_oof_repository(root), indent=2))


if __name__ == "__main__":
    main()
