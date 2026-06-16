#!/usr/bin/env python3
"""
Mini Crossword TUI

Install:
    pip install textual rich

Run:
    python mini_crossword.py

Or load one file directly:
    python mini_crossword.py 2026-06-16.json

Puzzle menu:
    The app scans puzzle_data/mini/*.json.
    Each filename stem is treated as the puzzle date.
    The menu is paginated so large puzzle collections stay responsive.

Controls:
    Arrow keys       Move within the current direction
    Perpendicular arrow
                     Switch direction without moving
                     e.g. Across + Up/Down switches to Down
    A-Z              Type a letter
    Backspace/Delete Erase
    Tab or Space     Toggle Across/Down
    Enter            Jump to next clue
    F2               Check filled answers
    F3               Reveal puzzle
    F4               Clear puzzle
    Q                Quit
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static


Direction = str  # "Across" or "Down"


@dataclass(frozen=True)
class Cell:
    index: int
    row: int
    col: int
    answer: Optional[str]
    label: str = ""
    clue_ids: tuple[int, ...] = ()

    @property
    def is_block(self) -> bool:
        return self.answer is None


@dataclass(frozen=True)
class Clue:
    index: int
    label: str
    direction: Direction
    cells: tuple[int, ...]
    text: str


@dataclass
class Puzzle:
    width: int
    height: int
    cells: list[Cell]
    clues: list[Clue]

    @classmethod
    def from_json_file(cls, path: str | Path) -> "Puzzle":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # The uploaded mini puzzle stores the actual puzzle in body[0].
        # This fallback also supports passing a puzzle object directly.
        data = raw["body"][0] if "body" in raw else raw

        width = int(data["dimensions"]["width"])
        height = int(data["dimensions"]["height"])

        clues: list[Clue] = []
        for i, clue in enumerate(data["clues"]):
            text = "".join(piece.get("plain", "") for piece in clue.get("text", []))
            clues.append(
                Clue(
                    index=i,
                    label=str(clue["label"]),
                    direction=str(clue["direction"]),
                    cells=tuple(int(c) for c in clue["cells"]),
                    text=text,
                )
            )

        cells: list[Cell] = []
        for i, cell in enumerate(data["cells"]):
            row, col = divmod(i, width)

            # In this JSON format, black squares are empty dicts.
            if not cell or "answer" not in cell:
                cells.append(Cell(index=i, row=row, col=col, answer=None))
                continue

            cells.append(
                Cell(
                    index=i,
                    row=row,
                    col=col,
                    answer=str(cell["answer"]).upper(),
                    label=str(cell.get("label", "")),
                    clue_ids=tuple(int(c) for c in cell.get("clues", [])),
                )
            )

        if len(cells) != width * height:
            raise ValueError(
                f"Expected {width * height} cells for a {width}x{height} puzzle, "
                f"but found {len(cells)}."
            )

        return cls(width=width, height=height, cells=cells, clues=clues)

    def first_open_cell(self) -> int:
        for cell in self.cells:
            if not cell.is_block:
                return cell.index
        raise ValueError("Puzzle has no playable cells.")

    def clue_for_cell(self, cell_index: int, direction: Direction) -> Optional[Clue]:
        cell = self.cells[cell_index]
        for clue_id in cell.clue_ids:
            clue = self.clues[clue_id]
            if clue.direction == direction:
                return clue
        return None

    def clue_ids_for_direction(self, direction: Direction) -> list[int]:
        return [clue.index for clue in self.clues if clue.direction == direction]


class CrosswordCell(Static):
    """One square in the crossword grid."""

    DEFAULT_CSS = """
    CrosswordCell {
        width: 7;
        height: 3;
        background: white;
        color: black;
        text-align: center;
        padding: 0;
    }

    CrosswordCell.block {
        background: black;
        color: black;
    }

    CrosswordCell.in-word {
        background: ansi_bright_cyan;
        color: black;
    }

    CrosswordCell.selected {
        background: yellow;
        color: black;
        text-style: bold;
    }

    CrosswordCell.correct {
        background: palegreen;
        color: black;
    }

    CrosswordCell.incorrect {
        background: red;
        color: white;
    }
    """

    def __init__(self, cell: Cell) -> None:
        super().__init__()
        self.cell = cell
        self.guess = ""
        self.selected = False
        self.in_word = False
        self.correct: Optional[bool] = None

    def on_mount(self) -> None:
        self.update_display()

    def set_state(
        self,
        *,
        guess: str,
        selected: bool,
        in_word: bool,
        correct: Optional[bool],
    ) -> None:
        changed = (
            self.guess != guess
            or self.selected != selected
            or self.in_word != in_word
            or self.correct != correct
        )

        if not changed:
            return

        self.guess = guess
        self.selected = selected
        self.in_word = in_word
        self.correct = correct
        self.update_display()

    def update_display(self) -> None:
        self.set_class(self.cell.is_block, "block")
        self.set_class(not self.cell.is_block and self.in_word, "in-word")
        self.set_class(not self.cell.is_block and self.selected, "selected")
        self.set_class(not self.cell.is_block and self.correct is True, "correct")
        self.set_class(not self.cell.is_block and self.correct is False, "incorrect")

        if self.cell.is_block:
            self.update("")
            return

        # Height 3 leaves three rows because cells are borderless:
        #   row 1: clue label in the top-left
        #   row 2: guessed letter centered
        #   row 3: blank spacing
        label = self.cell.label[:2]
        guess = self.guess.upper() if self.guess else " "

        content = Text()
        content.append(f"{label:<7}\n", style="dim")
        content.append(f"{guess:^7}\n", style="bold")
        content.append(" " * 7)
        self.update(content)


class CrosswordBoard(Grid):
    """Grid container that owns one widget per crossword square."""

    CELL_WIDTH = 7
    CELL_HEIGHT = 3

    def __init__(self, puzzle: Puzzle) -> None:
        super().__init__(id="board")
        self.puzzle = puzzle
        self.cell_widgets: dict[int, CrosswordCell] = {}

    def compose(self) -> ComposeResult:
        for cell in self.puzzle.cells:
            widget = CrosswordCell(cell)
            self.cell_widgets[cell.index] = widget
            yield widget

    def on_mount(self) -> None:
        self.styles.grid_size_columns = self.puzzle.width
        self.styles.grid_size_rows = self.puzzle.height

        # Give the grid a concrete size. Some Textual versions do not
        # expand an auto-sized Grid from its children, which makes the board
        # appear blank/collapsed even though the cells exist.
        self.styles.width = self.puzzle.width * self.CELL_WIDTH + 6
        self.styles.height = self.puzzle.height * self.CELL_HEIGHT + 4

    def update_state(
        self,
        *,
        guesses: list[str],
        selected_index: int,
        selected_clue: Optional[Clue],
        correctness: list[Optional[bool]],
    ) -> None:
        selected_word = set(selected_clue.cells) if selected_clue else set()

        for i, widget in self.cell_widgets.items():
            widget.set_state(
                guess=guesses[i],
                selected=i == selected_index,
                in_word=i in selected_word,
                correct=correctness[i],
            )


PUZZLE_DATA_DIR = Path("puzzle_data/mini")


def find_puzzle_files(puzzle_dir: Path = PUZZLE_DATA_DIR) -> list[Path]:
    """Return puzzle JSON files sorted by date-like filename, newest first."""
    if not puzzle_dir.exists():
        return []

    return sorted(
        puzzle_dir.glob("*.json"),
        key=lambda path: path.stem,
        reverse=True,
    )


class PuzzleMenuScreen(Screen):
    """Start screen that lets the user choose a puzzle date.

    The menu is paginated instead of rendering every puzzle file at once.
    That keeps startup and scrolling responsive even with hundreds or
    thousands of JSON files in puzzle_data/mini/.
    """

    PAGE_SIZE = 30

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("right", "next_page", "Next page"),
        ("left", "previous_page", "Previous page"),
        ("pagedown", "next_page", "Next page"),
        ("pageup", "previous_page", "Previous page"),
        ("home", "first_page", "First page"),
        ("end", "last_page", "Last page"),
        ("r", "reload", "Reload"),
    ]

    def __init__(self, puzzle_dir: Path = PUZZLE_DATA_DIR) -> None:
        super().__init__()
        self.puzzle_dir = puzzle_dir
        self.puzzle_files: list[Path] = []
        self.page = 0

    @property
    def page_count(self) -> int:
        if not self.puzzle_files:
            return 1
        return (len(self.puzzle_files) + self.PAGE_SIZE - 1) // self.PAGE_SIZE

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="menu"):
            yield Static("Mini Crossword", id="menu-title")
            yield Static(id="menu-subtitle")
            yield Static(id="menu-page")
            yield ListView(id="puzzle-list")
            yield Static(
                "Enter selects. Right/PageDown next page. Left/PageUp previous page. "
                "Home/End jump. R reloads.",
                id="menu-help",
            )

        yield Footer()

    def on_mount(self) -> None:
        self.reload_puzzles()

    def reload_puzzles(self) -> None:
        self.puzzle_files = find_puzzle_files(self.puzzle_dir)
        self.page = min(self.page, self.page_count - 1)
        self.render_current_page()

    def render_current_page(self) -> None:
        subtitle = self.query_one("#menu-subtitle", Static)
        page_label = self.query_one("#menu-page", Static)
        list_view = self.query_one("#puzzle-list", ListView)

        list_view.clear()

        subtitle.update(f"Choose a puzzle date from {self.puzzle_dir}/")

        if not self.puzzle_files:
            page_label.update(
                "No puzzle JSON files found. Add files like "
                "2026-06-16.json to puzzle_data/mini/ and press R."
            )
            return

        start = self.page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, len(self.puzzle_files))
        visible_files = self.puzzle_files[start:end]

        page_label.update(
            f"Showing {start + 1}-{end} of {len(self.puzzle_files)} "
            f"(page {self.page + 1}/{self.page_count})"
        )

        for puzzle_path in visible_files:
            list_view.append(ListItem(Label(puzzle_path.stem)))

        if visible_files:
            list_view.index = 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        selected_index = event.list_view.index
        if selected_index is None:
            return

        puzzle_index = self.page * self.PAGE_SIZE + selected_index
        if not (0 <= puzzle_index < len(self.puzzle_files)):
            return

        puzzle_path = self.puzzle_files[puzzle_index]
        self.app.push_screen(GameScreen(puzzle_path))

    def action_next_page(self) -> None:
        if self.page + 1 < self.page_count:
            self.page += 1
            self.render_current_page()

    def action_previous_page(self) -> None:
        if self.page > 0:
            self.page -= 1
            self.render_current_page()

    def action_first_page(self) -> None:
        if self.page != 0:
            self.page = 0
            self.render_current_page()

    def action_last_page(self) -> None:
        last_page = self.page_count - 1
        if self.page != last_page:
            self.page = last_page
            self.render_current_page()

    def action_reload(self) -> None:
        self.reload_puzzles()

class GameScreen(Screen):
    CSS = """
    Screen {
        layout: vertical;
    }

    #menu {
        width: 70;
        height: 1fr;
        margin: 2 4;
        padding: 1 2;
        border: round white;
    }

    #menu-title {
        text-style: bold;
        height: 3;
        content-align: center middle;
    }

    #menu-subtitle {
        height: 3;
        content-align: center middle;
    }

    #menu-page {
        height: 1;
        content-align: center middle;
    }

    #menu-help {
        height: 3;
        content-align: center middle;
    }

    #menu-empty {
        padding: 1;
        border: round red;
    }

    #puzzle-list {
        height: 1fr;
        border: round white;
        padding: 1;
    }

    #main {
        height: 1fr;
        padding: 1 2;
    }

    #board {
        width: auto;
        height: auto;
        border: solid white;
        padding: 1 2;
    }

    #sidebar {
        width: 1fr;
        padding-left: 2;
    }

    #current {
        height: auto;
        border: round yellow;
        padding: 1;
        margin-bottom: 1;
    }

    #clue-lists {
        height: 1fr;
    }

    .clue-panel {
        width: 1fr;
        height: 1fr;
        border: round white;
        padding: 1;
        overflow-y: auto;
        content-align: left top;
    }

    #across-clues {
        margin-right: 1;
    }

    #status {
        height: 3;
        padding: 0 2;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "menu", "Menu"),
        ("tab", "toggle_direction", "Toggle"),
        ("space", "toggle_direction", "Toggle"),
        ("enter", "next_clue", "Next clue"),
        ("f2", "check", "Check"),
        ("f3", "reveal", "Reveal"),
        ("f4", "clear", "Clear"),
    ]

    def __init__(self, puzzle_path: str | Path) -> None:
        super().__init__()
        self.puzzle_path = Path(puzzle_path)
        self.puzzle = Puzzle.from_json_file(self.puzzle_path)
        self.guesses = [""] * len(self.puzzle.cells)
        self.correctness: list[Optional[bool]] = [None] * len(self.puzzle.cells)
        self.selected_index = self.puzzle.first_open_cell()
        self.direction: Direction = "Across"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="main"):
            yield CrosswordBoard(self.puzzle)

            with Vertical(id="sidebar"):
                yield Static(id="current")
                with Horizontal(id="clue-lists"):
                    yield Static(id="across-clues", classes="clue-panel")
                    yield Static(id="down-clues", classes="clue-panel")

        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_ui(
            f"Loaded {self.puzzle_path.stem}. Type letters to solve. "
            "Use Tab/Space to switch direction."
        )

    def on_key(self, event) -> None:
        key = event.key

        if len(key) == 1 and key.isalpha():
            self.enter_letter(key)
            event.prevent_default()
            return

        if key in {"left", "right", "up", "down"}:
            self.move_selection(key)
            event.prevent_default()
            return

        if key in {"backspace", "delete"}:
            self.erase()
            event.prevent_default()
            return

    def action_menu(self) -> None:
        # If this game was opened from the menu, return to it. If the app was
        # started with a direct file path, switch to a fresh menu.
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_screen(PuzzleMenuScreen())

    def action_toggle_direction(self) -> None:
        other = "Down" if self.direction == "Across" else "Across"
        if self.puzzle.clue_for_cell(self.selected_index, other):
            self.direction = other
        self.refresh_ui()

    def action_next_clue(self) -> None:
        current = self.current_clue()
        clue_ids = self.puzzle.clue_ids_for_direction(self.direction)

        if not clue_ids:
            return

        if current is None:
            next_id = clue_ids[0]
        else:
            current_pos = clue_ids.index(current.index)
            next_id = clue_ids[(current_pos + 1) % len(clue_ids)]

        self.selected_index = self.puzzle.clues[next_id].cells[0]
        self.refresh_ui()

    def action_check(self) -> None:
        filled = 0
        wrong = 0

        for i, cell in enumerate(self.puzzle.cells):
            if cell.is_block:
                continue

            if not self.guesses[i]:
                self.correctness[i] = None
                continue

            filled += 1
            is_correct = self.guesses[i].upper() == cell.answer
            self.correctness[i] = is_correct
            wrong += int(not is_correct)

        if filled == 0:
            self.refresh_ui("Nothing to check yet.")
        elif wrong == 0 and self.is_complete():
            self.refresh_ui("Solved! Everything is correct.")
        elif wrong == 0:
            self.refresh_ui("All filled letters are correct so far.")
        else:
            suffix = "s" if wrong != 1 else ""
            self.refresh_ui(f"{wrong} filled letter{suffix} incorrect.")

    def action_reveal(self) -> None:
        for i, cell in enumerate(self.puzzle.cells):
            if not cell.is_block:
                self.guesses[i] = cell.answer or ""
                self.correctness[i] = True

        self.refresh_ui("Puzzle revealed.")

    def action_clear(self) -> None:
        self.guesses = [""] * len(self.puzzle.cells)
        self.correctness = [None] * len(self.puzzle.cells)
        self.selected_index = self.puzzle.first_open_cell()
        self.direction = "Across"
        self.refresh_ui("Puzzle cleared.")

    def enter_letter(self, letter: str) -> None:
        self.guesses[self.selected_index] = letter.upper()
        self.correctness[self.selected_index] = None
        self.advance_within_current_clue()
        self.refresh_ui()

    def erase(self) -> None:
        if self.guesses[self.selected_index]:
            self.guesses[self.selected_index] = ""
            self.correctness[self.selected_index] = None
        else:
            previous_index = self.previous_cell_in_current_clue()
            if previous_index is not None:
                self.selected_index = previous_index
                self.guesses[self.selected_index] = ""
                self.correctness[self.selected_index] = None

        self.refresh_ui()

    def move_selection(self, key: str) -> None:
        """
        Move NYT-style.

        If the arrow is perpendicular to the current solve direction, switch
        direction without moving the cursor. Otherwise, move in the current
        direction.
        """
        if self.direction == "Across" and key in {"up", "down"}:
            if self.puzzle.clue_for_cell(self.selected_index, "Down"):
                self.direction = "Down"
            self.refresh_ui()
            return

        if self.direction == "Down" and key in {"left", "right"}:
            if self.puzzle.clue_for_cell(self.selected_index, "Across"):
                self.direction = "Across"
            self.refresh_ui()
            return

        deltas = {
            "left": (0, -1),
            "right": (0, 1),
            "up": (-1, 0),
            "down": (1, 0),
        }

        dr, dc = deltas[key]
        row = self.puzzle.cells[self.selected_index].row
        col = self.puzzle.cells[self.selected_index].col

        while True:
            row += dr
            col += dc

            if not (0 <= row < self.puzzle.height and 0 <= col < self.puzzle.width):
                break

            idx = row * self.puzzle.width + col
            if not self.puzzle.cells[idx].is_block:
                self.selected_index = idx
                break

        self.refresh_ui()

    def advance_within_current_clue(self) -> None:
        clue = self.current_clue()
        if clue is None:
            return

        cells = list(clue.cells)
        pos = cells.index(self.selected_index)
        if pos + 1 < len(cells):
            self.selected_index = cells[pos + 1]

    def previous_cell_in_current_clue(self) -> Optional[int]:
        clue = self.current_clue()
        if clue is None:
            return None

        cells = list(clue.cells)
        pos = cells.index(self.selected_index)
        if pos > 0:
            return cells[pos - 1]

        return None

    def current_clue(self) -> Optional[Clue]:
        clue = self.puzzle.clue_for_cell(self.selected_index, self.direction)
        if clue:
            return clue

        # If this cell has no clue in the current direction, switch to the
        # other valid direction.
        other = "Down" if self.direction == "Across" else "Across"
        clue = self.puzzle.clue_for_cell(self.selected_index, other)
        if clue:
            self.direction = other

        return clue

    def is_complete(self) -> bool:
        for i, cell in enumerate(self.puzzle.cells):
            if not cell.is_block and self.guesses[i].upper() != cell.answer:
                return False
        return True

    def refresh_ui(self, status: str = "") -> None:
        clue = self.current_clue()

        board = self.query_one("#board", CrosswordBoard)
        board.update_state(
            guesses=self.guesses,
            selected_index=self.selected_index,
            selected_clue=clue,
            correctness=self.correctness,
        )

        self.query_one("#current", Static).update(self.current_clue_text(clue))
        self.query_one("#across-clues", Static).update(self.clues_text("Across", clue))
        self.query_one("#down-clues", Static).update(self.clues_text("Down", clue))
        self.query_one("#status", Static).update(status or self.progress_text())

    def current_clue_text(self, clue: Optional[Clue]) -> Text:
        text = Text()
        text.append("Current clue\n", style="bold")

        if clue is None:
            text.append("No clue selected.")
            return text

        answer_progress = "".join(self.guesses[i] or "_" for i in clue.cells)
        text.append(f"{clue.label} {clue.direction}: ", style="bold bright_cyan")
        text.append(clue.text)
        text.append(f"\n\n{answer_progress}", style="bold")
        return text

    def clues_text(self, direction: Direction, active_clue: Optional[Clue]) -> Text:
        text = Text()
        text.append(direction, style="bold underline")
        text.append("\n")

        for clue in self.puzzle.clues:
            if clue.direction != direction:
                continue

            is_active = active_clue is not None and clue.index == active_clue.index
            label_style = "bold bright_cyan" if is_active else "bold"
            clue_style = "bright_cyan" if is_active else ""

            text.append(f"{clue.label}. ", style=label_style)
            text.append(clue.text, style=clue_style)
            text.append("\n")

        return text

    def progress_text(self) -> str:
        open_cells = [cell for cell in self.puzzle.cells if not cell.is_block]
        filled = sum(1 for cell in open_cells if self.guesses[cell.index])
        total = len(open_cells)
        return (
            f"{filled}/{total} letters filled. "
            "Arrow keys move or switch direction. "
            "F2 checks, F3 reveals, F4 clears. Esc returns to puzzle menu."
        )


class MiniCrosswordApp(App):
    CSS = GameScreen.CSS

    def __init__(self, initial_puzzle_path: str | Path | None = None) -> None:
        super().__init__()
        self.initial_puzzle_path = Path(initial_puzzle_path) if initial_puzzle_path else None

    def on_mount(self) -> None:
        if self.initial_puzzle_path is not None:
            self.push_screen(GameScreen(self.initial_puzzle_path))
        else:
            self.push_screen(PuzzleMenuScreen())


def main() -> None:
    if len(sys.argv) > 2:
        print("Usage: python mini_crossword.py [path/to/puzzle.json]")
        raise SystemExit(2)

    initial_path = sys.argv[1] if len(sys.argv) == 2 else None
    app = MiniCrosswordApp(initial_path)
    app.run()


if __name__ == "__main__":
    main()
