import tempfile
import unittest
from pathlib import Path

from progress_store import PuzzleProgress, SQLitePuzzleProgressStore, database


class ProgressStoreTests(unittest.TestCase):
    def tearDown(self) -> None:
        if not database.is_closed():
            database.close()

    def test_sqlite_store_saves_loads_updates_and_deletes_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLitePuzzleProgressStore(Path(temp_dir) / "progress.sqlite3")

            store.save(
                PuzzleProgress(
                    puzzle_type="mini",
                    puzzle_date="2026-06-30",
                    guesses=["A", "", "B"],
                    correctness=[True, None, False],
                    elapsed_seconds=37,
                )
            )

            loaded = store.get("mini", "2026-06-30")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.guesses, ["A", "", "B"])
            self.assertEqual(loaded.correctness, [True, None, False])
            self.assertEqual(loaded.elapsed_seconds, 37)
            self.assertFalse(loaded.completed)

            loaded_by_date = store.get_many("mini", ["2026-06-30", "2026-07-01"])
            self.assertEqual(list(loaded_by_date), ["2026-06-30"])
            self.assertEqual(loaded_by_date["2026-06-30"].elapsed_seconds, 37)

            store.save(
                PuzzleProgress(
                    puzzle_type="mini",
                    puzzle_date="2026-06-30",
                    guesses=["A", "C", "B"],
                    correctness=[True, True, True],
                    elapsed_seconds=42,
                    completed=True,
                    completed_seconds=42,
                )
            )

            loaded = store.get("mini", "2026-06-30")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.guesses, ["A", "C", "B"])
            self.assertTrue(loaded.completed)
            self.assertEqual(loaded.completed_seconds, 42)

            store.delete("mini", "2026-06-30")

            self.assertIsNone(store.get("mini", "2026-06-30"))


if __name__ == "__main__":
    unittest.main()
