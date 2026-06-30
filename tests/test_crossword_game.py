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
        screen.refresh_ui = lambda status="": None
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


if __name__ == "__main__":
    unittest.main()
