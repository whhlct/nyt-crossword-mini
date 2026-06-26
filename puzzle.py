import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Optional


Direction = str  # "Across" or "Down"
CROSSWORD_BODY_FIELDS = ("cells", "clueLists", "clues", "dimensions")


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

        # The downloaded puzzle format stores the actual puzzle in body[0].
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


def process_crossword_puzzle_data(data: dict[str, Any]) -> dict[str, Any]:
    """Keep only puzzle fields needed to load crossword-style puzzle data."""
    processed_data = data.copy()
    body = processed_data.get("body")
    if isinstance(body, list):
        processed_data["body"] = [
            {key: puzzle[key] for key in CROSSWORD_BODY_FIELDS if key in puzzle}
            if isinstance(puzzle, dict)
            else puzzle
            for puzzle in body
        ]
    return processed_data


def process_connections_puzzle_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return Connections puzzle data unchanged."""
    return data
