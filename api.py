from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from crossword import (
    CROSSWORD_PUZZLE_TITLES,
    CROSSWORD_PUZZLE_TYPES,
    find_puzzle_files,
    format_elapsed,
    puzzle_dir_for_type,
    validate_crossword_puzzle_type,
)
from progress_store import PuzzleProgress, PuzzleProgressStore, default_progress_store
from puzzle import Cell, Clue, Puzzle


class ProgressPayload(BaseModel):
    guesses: list[str]
    correctness: list[Optional[bool]] | None = None
    elapsed_seconds: int = Field(default=0, ge=0)


class CheckPayload(BaseModel):
    guesses: list[str]
    elapsed_seconds: int = Field(default=0, ge=0)


def create_app(progress_store: PuzzleProgressStore | None = None) -> FastAPI:
    app = FastAPI(title="NYT Games Browser API")
    app.state.progress_store = progress_store or default_progress_store

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/games")
    def games() -> dict[str, object]:
        return {
            "games": [
                {
                    "key": puzzle_type,
                    "title": CROSSWORD_PUZZLE_TITLES[puzzle_type],
                    "kind": "crossword",
                    "implemented": True,
                }
                for puzzle_type in CROSSWORD_PUZZLE_TYPES
            ]
            + [
                {
                    "key": "connections",
                    "title": "Connections",
                    "kind": "connections",
                    "implemented": False,
                }
            ]
        }

    @app.get("/api/crosswords/{puzzle_type}/puzzles")
    def crossword_puzzles(
        puzzle_type: str,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> dict[str, object]:
        puzzle_type = validate_or_404(puzzle_type)
        puzzle_files = find_puzzle_files(puzzle_dir_for_type(puzzle_type))
        total = len(puzzle_files)
        start = (page - 1) * page_size
        end = min(start + page_size, total)
        visible_files = puzzle_files[start:end]
        dates = [path.stem for path in visible_files]
        progress_by_date = app.state.progress_store.get_many(puzzle_type, dates)

        return {
            "puzzle_type": puzzle_type,
            "title": CROSSWORD_PUZZLE_TITLES[puzzle_type],
            "page": page,
            "page_size": page_size,
            "total": total,
            "puzzles": [
                serialize_puzzle_listing(path, progress_by_date.get(path.stem))
                for path in visible_files
            ],
        }

    @app.get("/api/crosswords/{puzzle_type}/puzzles/{puzzle_date}")
    def crossword_puzzle(puzzle_type: str, puzzle_date: str) -> dict[str, object]:
        puzzle_type = validate_or_404(puzzle_type)
        puzzle_path = puzzle_path_or_404(puzzle_type, puzzle_date)
        puzzle = Puzzle.from_json_file(puzzle_path)
        progress = app.state.progress_store.get(puzzle_type, puzzle_date)

        return {
            "puzzle_type": puzzle_type,
            "title": CROSSWORD_PUZZLE_TITLES[puzzle_type],
            "date": puzzle_date,
            "puzzle": serialize_puzzle(puzzle),
            "progress": serialize_progress(progress, len(puzzle.cells)),
        }

    @put_or_post(app, "/api/crosswords/{puzzle_type}/puzzles/{puzzle_date}/progress")
    def save_crossword_progress(
        puzzle_type: str,
        puzzle_date: str,
        payload: ProgressPayload,
    ) -> dict[str, object]:
        puzzle_type = validate_or_404(puzzle_type)
        puzzle = Puzzle.from_json_file(puzzle_path_or_404(puzzle_type, puzzle_date))
        guesses = normalize_guesses(payload.guesses, puzzle)
        correctness = normalize_correctness(payload.correctness, puzzle)
        completed = is_complete(puzzle, guesses)
        completed_seconds = payload.elapsed_seconds if completed else None

        progress = PuzzleProgress(
            puzzle_type=puzzle_type,
            puzzle_date=puzzle_date,
            guesses=guesses,
            correctness=correctness,
            elapsed_seconds=payload.elapsed_seconds,
            completed=completed,
            completed_seconds=completed_seconds,
        )
        save_or_delete_progress(app.state.progress_store, progress)
        return {"progress": serialize_progress(progress, len(puzzle.cells))}

    @app.post("/api/crosswords/{puzzle_type}/puzzles/{puzzle_date}/check")
    def check_crossword(
        puzzle_type: str,
        puzzle_date: str,
        payload: CheckPayload,
    ) -> dict[str, object]:
        puzzle_type = validate_or_404(puzzle_type)
        puzzle = Puzzle.from_json_file(puzzle_path_or_404(puzzle_type, puzzle_date))
        guesses = normalize_guesses(payload.guesses, puzzle)
        correctness = check_filled_answers(puzzle, guesses)
        completed = is_complete(puzzle, guesses)
        completed_seconds = payload.elapsed_seconds if completed else None
        progress = PuzzleProgress(
            puzzle_type=puzzle_type,
            puzzle_date=puzzle_date,
            guesses=guesses,
            correctness=correctness,
            elapsed_seconds=payload.elapsed_seconds,
            completed=completed,
            completed_seconds=completed_seconds,
        )
        save_or_delete_progress(app.state.progress_store, progress)

        return {
            "filled": sum(1 for guess in guesses if guess),
            "total": sum(1 for cell in puzzle.cells if not cell.is_block),
            "wrong": sum(value is False for value in correctness),
            "progress": serialize_progress(progress, len(puzzle.cells)),
        }

    @app.post("/api/crosswords/{puzzle_type}/puzzles/{puzzle_date}/reveal")
    def reveal_crossword(
        puzzle_type: str,
        puzzle_date: str,
        payload: CheckPayload,
    ) -> dict[str, object]:
        puzzle_type = validate_or_404(puzzle_type)
        puzzle = Puzzle.from_json_file(puzzle_path_or_404(puzzle_type, puzzle_date))
        guesses = [cell.answer or "" for cell in puzzle.cells]
        correctness = [None if cell.is_block else True for cell in puzzle.cells]
        progress = PuzzleProgress(
            puzzle_type=puzzle_type,
            puzzle_date=puzzle_date,
            guesses=guesses,
            correctness=correctness,
            elapsed_seconds=payload.elapsed_seconds,
        )
        app.state.progress_store.save(progress)
        return {"progress": serialize_progress(progress, len(puzzle.cells))}

    @app.delete("/api/crosswords/{puzzle_type}/puzzles/{puzzle_date}/progress")
    def clear_crossword(puzzle_type: str, puzzle_date: str) -> dict[str, object]:
        puzzle_type = validate_or_404(puzzle_type)
        puzzle = Puzzle.from_json_file(puzzle_path_or_404(puzzle_type, puzzle_date))
        app.state.progress_store.delete(puzzle_type, puzzle_date)
        return {"progress": serialize_progress(None, len(puzzle.cells))}

    web_dist = Path(__file__).parent / "web" / "dist"
    if web_dist.exists():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

    return app


def put_or_post(app: FastAPI, path: str):
    def decorator(func):
        app.put(path)(func)
        app.post(path)(func)
        return func

    return decorator


def validate_or_404(puzzle_type: str) -> str:
    try:
        return validate_crossword_puzzle_type(puzzle_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def puzzle_path_or_404(puzzle_type: str, puzzle_date: str) -> Path:
    puzzle_path = puzzle_dir_for_type(puzzle_type) / f"{puzzle_date}.json"
    if not puzzle_path.exists():
        raise HTTPException(status_code=404, detail="Puzzle not found.")
    return puzzle_path


def serialize_puzzle_listing(
    puzzle_path: Path,
    progress: PuzzleProgress | None,
) -> dict[str, object]:
    result: dict[str, object] = {"date": puzzle_path.stem}
    if progress is None:
        result["status"] = "not_started"
        result["status_label"] = "Not started"
        return result

    elapsed = progress.completed_seconds or progress.elapsed_seconds
    if progress.completed:
        result["status"] = "completed"
        result["status_label"] = f"Completed {format_elapsed(elapsed)}"
    else:
        result["status"] = "in_progress"
        result["status_label"] = f"In progress {format_elapsed(elapsed)}"
    return result


def serialize_puzzle(puzzle: Puzzle) -> dict[str, object]:
    return {
        "width": puzzle.width,
        "height": puzzle.height,
        "cells": [serialize_cell(cell) for cell in puzzle.cells],
        "clues": [serialize_clue(clue) for clue in puzzle.clues],
    }


def serialize_cell(cell: Cell) -> dict[str, object]:
    return {
        "index": cell.index,
        "row": cell.row,
        "col": cell.col,
        "is_block": cell.is_block,
        "label": cell.label,
        "clue_ids": list(cell.clue_ids),
    }


def serialize_clue(clue: Clue) -> dict[str, object]:
    return {
        "index": clue.index,
        "label": clue.label,
        "direction": clue.direction,
        "cells": list(clue.cells),
        "text": clue.text,
    }


def serialize_progress(
    progress: PuzzleProgress | None,
    cell_count: int,
) -> dict[str, object]:
    if progress is None:
        return {
            "guesses": [""] * cell_count,
            "correctness": [None] * cell_count,
            "elapsed_seconds": 0,
            "completed": False,
            "completed_seconds": None,
        }

    return {
        "guesses": progress.guesses,
        "correctness": progress.correctness,
        "elapsed_seconds": progress.elapsed_seconds,
        "completed": progress.completed,
        "completed_seconds": progress.completed_seconds,
    }


def normalize_guesses(guesses: list[str], puzzle: Puzzle) -> list[str]:
    if len(guesses) != len(puzzle.cells):
        raise HTTPException(status_code=422, detail="Guess count does not match puzzle cell count.")

    return [
        "" if cell.is_block else (guess[:1].upper() if guess else "")
        for guess, cell in zip(guesses, puzzle.cells)
    ]


def normalize_correctness(
    correctness: list[Optional[bool]] | None,
    puzzle: Puzzle,
) -> list[Optional[bool]]:
    if correctness is None:
        return [None] * len(puzzle.cells)

    if len(correctness) != len(puzzle.cells):
        raise HTTPException(
            status_code=422,
            detail="Correctness count does not match puzzle cell count.",
        )

    return [None if cell.is_block else value for value, cell in zip(correctness, puzzle.cells)]


def check_filled_answers(puzzle: Puzzle, guesses: list[str]) -> list[Optional[bool]]:
    return [
        None if cell.is_block or not guesses[cell.index] else guesses[cell.index] == cell.answer
        for cell in puzzle.cells
    ]


def is_complete(puzzle: Puzzle, guesses: list[str]) -> bool:
    return all(cell.is_block or guesses[cell.index] == cell.answer for cell in puzzle.cells)


def save_or_delete_progress(
    progress_store: PuzzleProgressStore,
    progress: PuzzleProgress,
) -> None:
    if not any(progress.guesses) and not progress.completed:
        progress_store.delete(progress.puzzle_type, progress.puzzle_date)
        return

    progress_store.save(progress)


app = create_app()
