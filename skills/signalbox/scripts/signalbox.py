#!/usr/bin/env python3
"""Run signalbox from the skill folder without installing it: python3 scripts/signalbox.py <command>."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from signalbox.cli import main  # noqa: E402

sys.exit(main())
