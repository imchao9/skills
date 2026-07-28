from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_basketball_highlight.py"
SPEC = importlib.util.spec_from_file_location("build_basketball_highlight", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


class FilenameContractTest(unittest.TestCase):
    def test_accepts_colon_clock(self) -> None:
        match = builder.EVENT_PATTERN.match("风暴队 30号 李天驰 2分命中 第三节 20:49.mp4")
        self.assertIsNotNone(match)

    def test_accepts_underscore_clock(self) -> None:
        match = builder.EVENT_PATTERN.match("风暴队 30号 李天驰 2分命中 第三节 20_49.mp4")
        self.assertIsNotNone(match)


if __name__ == "__main__":
    unittest.main()
