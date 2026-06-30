import unittest

from crossword import GameScreen
from puzzle import Cell, Clue, Puzzle


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
        screen.puzzle = puzzle
        screen.guesses = [""] * len(puzzle.cells)
        screen.correctness = [None] * len(puzzle.cells)
        screen.selected_index = 0
        screen.direction = "Across"
        screen.started_at = 0
        screen.finished_elapsed = None
        screen.statuses = []
        screen.notifications = []
        screen.refresh_ui = lambda status="": screen.statuses.append(status)
        screen.show_completion_message = lambda message: screen.notifications.append(message)
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

    def test_filling_final_correct_letter_completes_puzzle_with_elapsed_time(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", ""]
        screen.selected_index = 4

        screen.enter_letter("d")

        self.assertEqual(screen.finished_elapsed, 83)
        self.assertEqual(screen.statuses[-1], "Puzzle completed in 1:23!")
        self.assertEqual(screen.notifications, ["Puzzle completed in 1:23!"])
        self.assertTrue(all(value is True for value in screen.correctness if value is not None))

    def test_completed_puzzle_notification_only_shows_once(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", "D"]

        screen.mark_completed()
        screen.mark_completed()

        self.assertEqual(screen.notifications, ["Puzzle completed in 1:23!"])

    def test_filling_final_incorrect_letter_reports_wrong_letters(self) -> None:
        screen = self.make_screen()
        screen.guesses = ["A", "B", "", "C", ""]
        screen.selected_index = 4

        screen.enter_letter("x")

        self.assertIsNone(screen.finished_elapsed)
        self.assertEqual(screen.statuses[-1], "All letters are filled, but 1 letter incorrect.")
        self.assertEqual(screen.notifications, [])
        self.assertFalse(screen.correctness[4])


if __name__ == "__main__":
    unittest.main()
