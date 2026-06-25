import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import cast
from unittest.mock import patch

import aiohttp
import download


class PuzzleDataProcessingTests(unittest.TestCase):
    def test_removes_board_from_crossword_style_body_without_mutating_raw_data(self) -> None:
        raw_data = {
            "body": [
                {
                    "board": "<svg>large board</svg>",
                    "cells": [{"answer": "A"}],
                    "clues": [],
                }
            ]
        }

        processed_data = download.MINI.process_data(raw_data)

        self.assertNotIn("board", processed_data["body"][0])
        self.assertEqual(processed_data["body"][0]["cells"], [{"answer": "A"}])
        self.assertEqual(raw_data["body"][0]["board"], "<svg>large board</svg>")

    def test_leaves_connections_data_unchanged(self) -> None:
        raw_data = {
            "status": "OK",
            "categories": [{"title": "GROUP", "cards": []}],
        }

        processed_data = download.CONNECTIONS.process_data(raw_data)

        self.assertIs(processed_data, raw_data)


class DownloadPuzzleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.puzzle_data_dir = self.root / "puzzle_data"
        self.original_data_dir = self.root / "puzzle_data_original"
        self.puzzle_date = date(2014, 8, 21)

    async def test_uses_original_data_dir_as_raw_cache_and_saves_processed_data(self) -> None:
        raw_path = self.original_data_dir / "mini" / "2014-08-21.json"
        download.save_json(
            raw_path,
            {
                "body": [
                    {
                        "board": "<svg>large board</svg>",
                        "dimensions": {"width": 1, "height": 1},
                        "cells": [{"answer": "A"}],
                        "clues": [],
                    }
                ]
            },
        )

        cached_data_session = cast(aiohttp.ClientSession, object())

        with patch.object(download, "PUZZLE_DATA_DIR", self.puzzle_data_dir):
            output_path = await download.download_puzzle(
                cached_data_session,
                download.MINI,
                self.puzzle_date,
                original_data_dir=self.original_data_dir,
            )

        self.assertIsNotNone(output_path)
        if output_path is None:
            return
        self.assertEqual(output_path, self.puzzle_data_dir / "mini" / "2014-08-21.json")
        self.assertTrue(output_path.is_file())

        processed_data = download.load_json(output_path)
        cached_raw_data = download.load_json(raw_path)

        self.assertNotIn("board", processed_data["body"][0])
        self.assertEqual(cached_raw_data["body"][0]["board"], "<svg>large board</svg>")


if __name__ == "__main__":
    unittest.main()
