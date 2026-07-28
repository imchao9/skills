from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "xiaoqiumi_download.py"
SPEC = importlib.util.spec_from_file_location("xiaoqiumi_download", SCRIPT)
assert SPEC and SPEC.loader
download = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = download
SPEC.loader.exec_module(download)


class XiaoqiumiDownloadTest(unittest.TestCase):
    def test_split_ranges_cover_every_byte_once(self) -> None:
        ranges = download.split_ranges(10, 3)
        self.assertEqual(ranges, [(0, 3), (4, 7), (8, 9)])
        covered = [byte for start, end in ranges for byte in range(start, end + 1)]
        self.assertEqual(covered, list(range(10)))

    def test_more_connections_than_bytes_are_capped(self) -> None:
        self.assertEqual(download.split_ranges(2, 8), [(0, 0), (1, 1)])


if __name__ == "__main__":
    unittest.main()
