import json
import tempfile
import unittest
from pathlib import Path

from puzzle import Puzzle


class PuzzleLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def write_puzzle_json(self, data: dict) -> Path:
        path = Path(self.temp_dir.name) / "puzzle.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_loads_downloaded_puzzle_body_format(self) -> None:
        path = self.write_puzzle_json(
            {
                "body": [
                    {
                        "dimensions": {"width": 3, "height": 2},
                        "clues": [
                            {
                                "label": 1,
                                "direction": "Across",
                                "cells": [0, 1],
                                "text": [{"plain": "First "}, {"plain": "clue"}],
                            },
                            {
                                "label": "2",
                                "direction": "Down",
                                "cells": [1, 4],
                                "text": [{"plain": "Second clue"}],
                            },
                        ],
                        "cells": [
                            {"answer": "a", "label": 1, "clues": [0]},
                            {"answer": "b", "label": 2, "clues": [0, 1]},
                            {},
                            {"answer": "c", "clues": []},
                            {"answer": "d", "clues": [1]},
                            {},
                        ],
                    }
                ]
            }
        )

        puzzle = Puzzle.from_json_file(path)

        self.assertEqual(puzzle.width, 3)
        self.assertEqual(puzzle.height, 2)
        self.assertEqual(len(puzzle.cells), 6)
        self.assertEqual(len(puzzle.clues), 2)

        self.assertEqual(puzzle.clues[0].index, 0)
        self.assertEqual(puzzle.clues[0].label, "1")
        self.assertEqual(puzzle.clues[0].direction, "Across")
        self.assertEqual(puzzle.clues[0].cells, (0, 1))
        self.assertEqual(puzzle.clues[0].text, "First clue")

        self.assertEqual(puzzle.cells[0].index, 0)
        self.assertEqual(puzzle.cells[0].row, 0)
        self.assertEqual(puzzle.cells[0].col, 0)
        self.assertEqual(puzzle.cells[0].answer, "A")
        self.assertEqual(puzzle.cells[0].label, "1")
        self.assertEqual(puzzle.cells[0].clue_ids, (0,))
        self.assertFalse(puzzle.cells[0].is_block)

        self.assertEqual(puzzle.cells[2].index, 2)
        self.assertEqual(puzzle.cells[2].row, 0)
        self.assertEqual(puzzle.cells[2].col, 2)
        self.assertIsNone(puzzle.cells[2].answer)
        self.assertTrue(puzzle.cells[2].is_block)

    def test_loads_direct_puzzle_object_format(self) -> None:
        path = self.write_puzzle_json(
            {
                "dimensions": {"width": 2, "height": 2},
                "clues": [
                    {
                        "label": "1",
                        "direction": "Across",
                        "cells": ["0", "1"],
                        "text": [{"plain": "Top row"}],
                    }
                ],
                "cells": [
                    {"answer": "Y", "label": "1", "clues": ["0"]},
                    {"answer": "E", "clues": ["0"]},
                    {},
                    {"answer": "S"},
                ],
            }
        )

        puzzle = Puzzle.from_json_file(path)

        self.assertEqual((puzzle.width, puzzle.height), (2, 2))
        self.assertEqual(puzzle.clues[0].cells, (0, 1))
        self.assertEqual(puzzle.cells[0].clue_ids, (0,))
        self.assertEqual(puzzle.cells[3].answer, "S")
        self.assertEqual(puzzle.cells[3].clue_ids, ())

    def test_rejects_puzzles_with_incorrect_cell_count(self) -> None:
        path = self.write_puzzle_json(
            {
                "dimensions": {"width": 2, "height": 2},
                "clues": [],
                "cells": [
                    {"answer": "A"},
                    {"answer": "B"},
                    {"answer": "C"},
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "Expected 4 cells"):
            Puzzle.from_json_file(path)


if __name__ == "__main__":
    unittest.main()
