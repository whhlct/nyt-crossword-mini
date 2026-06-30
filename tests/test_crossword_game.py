import unittest
from pathlib import Path

from crossword import GameScreen, PuzzleMenuScreen
from progress_store import PuzzleProgress
from puzzle import Cell, Clue, Puzzle


class FakeProgressStore:
    def __init__(self) -> None:
        self.progress: PuzzleProgress | None = None
        self.deleted: tuple[str, str] | None = None

    def get(self, puzzle_type: str, puzzle_date: str) -> PuzzleProgress | None:
        return self.progress

    def get_many(
        self,
        puzzle_type: str,
        puzzle_dates: list[str],
    ) -> dict[str, PuzzleProgress]:
        if self.progress is None or self.progress.puzzle_date not in puzzle_dates:
            return {}

        return {self.progress.puzzle_date: self.progress}

    def save(self, progress: PuzzleProgress) -> None:
        self.progress = progress

    def delete(self, puzzle_type: str, puzzle_date: str) -> None:
        self.deleted = (puzzle_type, puzzle_date)
        self.progress = None


class CrosswordGameTests(unittest.TestCase):
    def make_screen(self) -> GameScreen:
        puzzle = Puzzle(
            width=5,
            height=1,
            cells=[
                Cell(index=0, row=0, col=0, answer="A", label="1", clue_ids=(0,)),
                Cell(index=1, row=0, col=1, answer="B", clue_ids=(0,)),
                Cell(index=2, row=0, col=2, answer=None),
                Cell(index=3, row=0, col=3, answer="C", label="2", clue_ids=(1,)),
                Cell(index=4, row=0, col=4, answer="D", clue_ids=(1,)),
            ],
            clues=[
                Clue(index=0, label="1", direction="Across", cells=(0, 1), text="First"),
                Clue(index=1, label="2", direction="Across", cells=(3, 4), text="Second"),
            ],
        )

        screen = GameScreen.__new__(GameScreen)
        screen.puzzle_type = "mini"
        screen.puzzle_date = "2026-06-30"
        screen.progress_store = FakeProgressStore()
        screen.puzzle = puzzle
        screen.guesses = [""] * len(puzzle.cells)
        screen.correctness = [None] * len(puzzle.cells)
        screen.selected_index = 0
        screen.direction = "Across"
        screen.started_at = 0
        screen.finished_elapsed = None
        screen.checked_when_filled = False
        screen.statuses = []
        screen.notifications = []
        screen.refresh_ui = lambda status="": screen.statuses.append(status)
        screen.show_completion_message = lambda message: screen.notifications.append(message)
        screen.show_incorrect_completion_message = lambda message: screen.notifications.append(message)
        screen.elapsed_seconds = lambda: 83 if screen.finished_elapsed is None else screen.finished_elapsed
        return screen

    def test_entered_letter_advances_within_current_word(self) -> None:
        screen = self.make_screen()

        screen.enter_letter("a")

        self.assertEqual(screen.guesses[0], "A")
        self.assertEqual(screen.selected_index, 1)

    def test_entered_letter_at_end_of_word_advances_to_next_word(self) -> None:
        screen = self.make_screen()
        screen.selected_index = 1

        screen.enter_letter("b")

        self.assertEqual(screen.guesses[1], "B")
        self.assertEqual(screen.selected_index, 3)

    def test_entered_letter_does_not_overwrite_checked_correct_cell(self) -> None:
        screen = self.make_screen()
        screen.guesses[0] = "A"
        screen.correctness[0] = True

        screen.enter_letter("z")

        self.assertEqual(screen.guesses[0], "A")
        self.assertEqual(screen.selected_index, 0)

    def test_erase_does_not_clear_checked_correct_cell(self) -> None:
        screen = self.make_screen()
        screen.guesses[0] = "A"
        screen.correctness[0] = True

        screen.erase()

        self.assertEqual(screen.guesses[0], "A")
        self.assertTrue(screen.correctness[0])

    def test_backspace_from_empty_cell_does_not_clear_previous_checked_correct_cell(self) -> None:
        screen = self.make_screen()
        screen.guesses[0] = "A"
        screen.correctness[0] = True
        screen.selected_index = 1

        screen.erase()

        self.assertEqual(screen.guesses[0], "A")
        self.assertTrue(screen.correctness[0])
        self.assertEqual(screen.selected_index, 1)

    def test_entered_letter_skips_checked_correct_cell_in_current_word(self) -> None:
        screen = self.make_screen()
        screen.guesses[1] = "B"
        screen.correctness[1] = True

        screen.enter_letter("a")

        self.assertEqual(screen.selected_index, 3)

    def test_entered_letter_skips_checked_correct_cell_at_start_of_next_word(self) -> None:
        screen = self.make_screen()
        screen.selected_index = 1
        screen.guesses[3] = "C"
        screen.correctness[3] = True

        screen.enter_letter("b")

        self.assertEqual(screen.selected_index, 4)

    def test_filling_final_correct_letter_auto_completes_without_marking_cells(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", ""]
        screen.selected_index = 4

        screen.enter_letter("d")

        self.assertEqual(screen.finished_elapsed, 83)
        self.assertEqual(screen.statuses[-1], "Puzzle completed in 1:23!")
        self.assertEqual(screen.notifications, ["Puzzle completed in 1:23!"])
        self.assertTrue(all(value is None for value in screen.correctness))
        self.assertTrue(screen.checked_when_filled)

    def test_filling_final_incorrect_letter_notifies_without_marking_cells(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", ""]
        screen.selected_index = 4

        screen.enter_letter("x")

        self.assertIsNone(screen.finished_elapsed)
        self.assertEqual(screen.statuses[-1], "Some letters are incorrect.")
        self.assertEqual(screen.notifications, ["Some letters are incorrect."])
        self.assertTrue(all(value is None for value in screen.correctness))
        self.assertTrue(screen.checked_when_filled)

    def test_full_puzzle_can_complete_after_incorrect_fill_warning(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", ""]
        screen.selected_index = 4

        screen.enter_letter("x")
        screen.selected_index = 4
        screen.enter_letter("d")

        self.assertEqual(
            screen.notifications,
            ["Some letters are incorrect.", "Puzzle completed in 1:23!"],
        )
        self.assertEqual(screen.finished_elapsed, 83)

    def test_check_completed_puzzle_reports_elapsed_time(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", "D"]

        screen.action_check()

        self.assertEqual(screen.finished_elapsed, 83)
        self.assertEqual(screen.statuses[-1], "Puzzle completed in 1:23!")
        self.assertEqual(screen.notifications, ["Puzzle completed in 1:23!"])
        self.assertEqual(screen.correctness, [True, True, None, True, True])

    def test_completed_puzzle_notification_only_shows_once(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", "D"]

        screen.mark_completed()
        screen.mark_completed()

        self.assertEqual(screen.notifications, ["Puzzle completed in 1:23!"])

    def test_check_filled_incorrect_letters_reports_wrong_letters(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", "X"]

        screen.action_check()

        self.assertIsNone(screen.finished_elapsed)
        self.assertEqual(screen.statuses[-1], "1 filled letter incorrect.")
        self.assertEqual(screen.notifications, [])
        self.assertFalse(screen.correctness[4])

    def test_save_progress_persists_guesses_correctness_and_elapsed_time(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "", "", "C", ""]
        screen.correctness = [True, None, None, False, None]

        screen.save_progress()

        progress = screen.progress_store.progress
        self.assertIsNotNone(progress)
        self.assertEqual(progress.puzzle_type, "mini")
        self.assertEqual(progress.puzzle_date, "2026-06-30")
        self.assertEqual(progress.guesses, ["A", "", "", "C", ""])
        self.assertEqual(progress.correctness, [True, None, None, False, None])
        self.assertEqual(progress.elapsed_seconds, 83)
        self.assertFalse(progress.completed)

    def test_save_progress_persists_completion_status_and_time(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", "D"]
        screen.finished_elapsed = 42

        screen.save_progress()

        progress = screen.progress_store.progress
        self.assertIsNotNone(progress)
        self.assertTrue(progress.completed)
        self.assertEqual(progress.completed_seconds, 42)
        self.assertEqual(progress.elapsed_seconds, 42)

    def test_save_progress_deletes_empty_unsolved_progress(self) -> None:
        screen = self.make_screen()

        screen.save_progress()

        self.assertEqual(screen.progress_store.deleted, ("mini", "2026-06-30"))

    def test_restore_progress_loads_guesses_correctness_and_elapsed_time(self) -> None:
        screen = self.make_screen()
        screen.progress_store.progress = PuzzleProgress(
            puzzle_type="mini",
            puzzle_date="2026-06-30",
            guesses=["A", "", "", "C", ""],
            correctness=[True, None, None, False, None],
            elapsed_seconds=12,
        )

        screen.restore_progress()

        self.assertEqual(screen.guesses, ["A", "", "", "C", ""])
        self.assertEqual(screen.correctness, [True, None, None, False, None])
        self.assertIsNone(screen.finished_elapsed)

    def test_restore_completed_progress_loads_completion_time(self) -> None:
        screen = self.make_screen()
        screen.progress_store.progress = PuzzleProgress(
            puzzle_type="mini",
            puzzle_date="2026-06-30",
            guesses=["A", "B", "", "C", "D"],
            correctness=[True, True, None, True, True],
            elapsed_seconds=99,
            completed=True,
            completed_seconds=42,
        )

        screen.restore_progress()

        self.assertEqual(screen.finished_elapsed, 42)
        self.assertTrue(screen.checked_when_filled)


class PuzzleMenuTests(unittest.TestCase):
    def test_puzzle_label_shows_completed_time(self) -> None:
        store = FakeProgressStore()
        menu = PuzzleMenuScreen("mini", store)
        progress = PuzzleProgress(
            puzzle_type="mini",
            puzzle_date="2026-06-30",
            guesses=["A"],
            correctness=[True],
            elapsed_seconds=99,
            completed=True,
            completed_seconds=83,
        )

        label = menu.puzzle_label(Path("puzzle_data/mini/2026-06-30.json"), {progress.puzzle_date: progress})

        self.assertEqual(label, "2026-06-30  [Completed 1:23]")

    def test_puzzle_label_shows_in_progress_time(self) -> None:
        store = FakeProgressStore()
        menu = PuzzleMenuScreen("mini", store)
        progress = PuzzleProgress(
            puzzle_type="mini",
            puzzle_date="2026-06-30",
            guesses=["A"],
            correctness=[None],
            elapsed_seconds=42,
        )

        label = menu.puzzle_label(Path("puzzle_data/mini/2026-06-30.json"), {progress.puzzle_date: progress})

        self.assertEqual(label, "2026-06-30  [In progress 0:42]")


if __name__ == "__main__":
    unittest.main()
