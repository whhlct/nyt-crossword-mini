from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import api
from progress_store import PuzzleProgress


class FakeProgressStore:
    def __init__(self) -> None:
        self.progress: PuzzleProgress | None = None
        self.deleted: tuple[str, str] | None = None

    def get(self, puzzle_type: str, puzzle_date: str) -> PuzzleProgress | None:
        if self.progress and self.progress.puzzle_type == puzzle_type and self.progress.puzzle_date == puzzle_date:
            return self.progress
        return None

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


def test_games_lists_connections_placeholder() -> None:
    client = TestClient(api.create_app(FakeProgressStore()))

    response = client.get("/api/games")

    assert response.status_code == 200
    connections = response.json()["games"][-1]
    assert connections["key"] == "connections"
    assert connections["implemented"] is False


def test_crossword_payload_does_not_include_answers(monkeypatch) -> None:
    use_fixture_puzzles(monkeypatch)
    client = TestClient(api.create_app(FakeProgressStore()))

    response = client.get("/api/crosswords/mini/puzzles/2026-06-24")

    assert response.status_code == 200
    cell = next(cell for cell in response.json()["puzzle"]["cells"] if not cell["is_block"])
    assert "answer" not in cell


def test_check_saves_completion_when_all_guesses_are_correct(monkeypatch) -> None:
    use_fixture_puzzles(monkeypatch)
    store = FakeProgressStore()
    client = TestClient(api.create_app(store))
    puzzle = client.get("/api/crosswords/mini/puzzles/2026-06-24").json()["puzzle"]
    guesses = [""] * len(puzzle["cells"])

    reveal = client.post(
        "/api/crosswords/mini/puzzles/2026-06-24/reveal",
        json={"guesses": guesses, "elapsed_seconds": 14},
    ).json()

    response = client.post(
        "/api/crosswords/mini/puzzles/2026-06-24/check",
        json={"guesses": reveal["progress"]["guesses"], "elapsed_seconds": 14},
    )

    assert response.status_code == 200
    assert response.json()["progress"]["completed"] is True
    assert store.progress is not None
    assert store.progress.completed_seconds == 14


def use_fixture_puzzles(monkeypatch) -> None:
    fixture_root = Path("tests/test_puzzle_data_original")
    monkeypatch.setattr(api, "puzzle_dir_for_type", lambda puzzle_type: fixture_root / puzzle_type)
