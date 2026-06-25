import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import cast
from xml.etree import ElementTree

import aiohttp
import download
from puzzle import Puzzle, json_svg_to_svg, svg_to_json_svg


FIXTURE_ROOT = Path(__file__).parent
#CROSSWORD_FIXTURE_ROOT = FIXTURE_ROOT / "test_puzzle_data_original"
CROSSWORD_FIXTURE_ROOT = Path(__file__).parent.parent / "puzzle_data_original"


def crossword_fixture_paths() -> list[Path]:
    return [
        path
        for puzzle_type in ("mini", "midi", "crossword")
        for path in sorted((CROSSWORD_FIXTURE_ROOT / puzzle_type).glob("*01-01.json"))
    ]


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

    def test_converts_json_svg_to_svg_xml_string(self) -> None:
        raw_path = FIXTURE_ROOT / "test_puzzle_data_original" / "mini" / "2026-06-23.json"
        raw_data = download.load_json(raw_path)

        svg = json_svg_to_svg(raw_data["body"][0]["SVG"])
        root = ElementTree.fromstring(svg)
        text_content = [element.text for element in root.iter() if element.tag.endswith("text")]

        self.assertTrue(svg.startswith("<svg "))
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(root.attrib["viewBox"], "0 0 506.00 506.00")
        self.assertEqual(root.attrib["style"], "font-family:helvetica,arial,sans-serif")
        self.assertIn("1", text_content)
        self.assertIn("9", text_content)

    def test_converts_svg_xml_string_to_json_svg(self) -> None:
        for raw_path in crossword_fixture_paths():
            with self.subTest(raw_path=raw_path):
                raw_data = download.load_json(raw_path)
                original_svg_json = raw_data["body"][0]["SVG"]

                svg_json = svg_to_json_svg(raw_data["body"][0]["board"])

                self.assertEqual(svg_json, original_svg_json)

    def test_round_trips_json_svg_through_svg_xml(self) -> None:
        for raw_path in crossword_fixture_paths():
            with self.subTest(raw_path=raw_path):
                raw_data = download.load_json(raw_path)
                original_svg_json = raw_data["body"][0]["SVG"]

                svg_xml = json_svg_to_svg(original_svg_json)
                round_tripped_svg_json = svg_to_json_svg(svg_xml)

                self.assertEqual(round_tripped_svg_json, original_svg_json)


    def assert_processed_fixture_matches_original_data(
        self,
        config: download.PuzzleConfig,
        puzzle_date: date,
    ) -> None:
        raw_path = (
            FIXTURE_ROOT
            / "test_puzzle_data_original"
            / config.directory
            / f"{puzzle_date.isoformat()}.json"
        )
        raw_data = download.load_json(raw_path)
        raw_puzzle = raw_data["body"][0]

        processed_data = config.process_data(raw_data)

        with tempfile.TemporaryDirectory() as temp_dir:
            processed_path = Path(temp_dir) / f"{puzzle_date.isoformat()}.json"
            download.save_json(processed_path, processed_data)

            saved_data = download.load_json(processed_path)
            puzzle = Puzzle.from_json_file(processed_path)

        self.assertIn("body", saved_data)
        self.assertNotIn("board", saved_data["body"][0])

        self.assertEqual(puzzle.width, raw_puzzle["dimensions"]["width"])
        self.assertEqual(puzzle.height, raw_puzzle["dimensions"]["height"])
        self.assertEqual(len(puzzle.cells), len(raw_puzzle["cells"]))
        self.assertEqual(len(puzzle.clues), len(raw_puzzle["clues"]))
        self.assertEqual(puzzle.first_open_cell(), 0)

        valid_cell_indexes = set(range(len(puzzle.cells)))
        raw_cells = raw_puzzle["cells"]

        for cell, raw_cell in zip(puzzle.cells, raw_cells):
            if not raw_cell:
                self.assertTrue(cell.is_block)
                self.assertIsNone(cell.answer)
                self.assertEqual(cell.label, "")
                self.assertEqual(cell.clue_ids, ())
                continue

            self.assertFalse(cell.is_block)
            self.assertEqual(cell.answer, raw_cell["answer"].upper())
            self.assertEqual(cell.label, str(raw_cell.get("label", "")))
            self.assertEqual(
                cell.clue_ids,
                tuple(int(clue_id) for clue_id in raw_cell.get("clues", [])),
            )

        for clue, raw_clue in zip(puzzle.clues, raw_puzzle["clues"]):
            expected_cells = tuple(int(cell_index) for cell_index in raw_clue["cells"])
            expected_text = "".join(piece.get("plain", "") for piece in raw_clue["text"])
            expected_answer = "".join(raw_cells[cell_index]["answer"] for cell_index in expected_cells)
            loaded_answer = "".join(puzzle.cells[cell_index].answer or "" for cell_index in clue.cells)

            self.assertEqual(clue.label, str(raw_clue["label"]))
            self.assertEqual(clue.direction, raw_clue["direction"])
            self.assertEqual(clue.cells, expected_cells)
            self.assertEqual(clue.text, expected_text)
            self.assertEqual(loaded_answer, expected_answer)
            self.assertTrue(set(clue.cells).issubset(valid_cell_indexes))

    def test_processes_mini_fixture_into_loadable_puzzle_data(self) -> None:
        puzzle_date = date(2026, 6, 23)
        self.assert_processed_fixture_matches_original_data(download.MINI, puzzle_date)

    def test_processes_midi_fixture_into_loadable_puzzle_data(self) -> None:
        puzzle_date = date(2026, 6, 23)
        self.assert_processed_fixture_matches_original_data(download.MIDI, puzzle_date)

    def test_processes_crossword_fixture_into_loadable_puzzle_data(self) -> None:
        puzzle_date = date(2026, 6, 23)
        self.assert_processed_fixture_matches_original_data(download.CROSSWORD, puzzle_date)


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
        output_path = await download.download_and_save_puzzle(
            cached_data_session,
            download.MINI,
            self.puzzle_date,
            puzzle_data_dir=self.puzzle_data_dir,
            original_data_dir=self.original_data_dir,
        )

        self.assertEqual(output_path, self.puzzle_data_dir / "mini" / "2014-08-21.json")
        self.assertTrue(output_path.is_file())

        processed_data = download.load_json(output_path)
        cached_raw_data = download.load_json(raw_path)

        self.assertNotIn("board", processed_data["body"][0])
        self.assertEqual(cached_raw_data["body"][0]["board"], "<svg>large board</svg>")


if __name__ == "__main__":
    unittest.main()
