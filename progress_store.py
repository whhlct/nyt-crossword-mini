from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from peewee import BooleanField, CharField, DateTimeField, IntegerField, Model, TextField
from peewee import SqliteDatabase


DEFAULT_PROGRESS_DB_PATH = Path("puzzle_progress.db")

database = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = database


class PuzzleProgressRecord(BaseModel):
    puzzle_type = CharField()
    puzzle_date = CharField()
    guesses_json = TextField()
    correctness_json = TextField()
    elapsed_seconds = IntegerField(default=0)
    completed = BooleanField(default=False)
    completed_seconds = IntegerField(null=True)
    updated_at = DateTimeField()

    class Meta:
        table_name = "puzzle_progress"
        indexes = ((("puzzle_type", "puzzle_date"), True),)


@dataclass(frozen=True)
class PuzzleProgress:
    puzzle_type: str
    puzzle_date: str
    guesses: list[str]
    correctness: list[Optional[bool]]
    elapsed_seconds: int
    completed: bool = False
    completed_seconds: Optional[int] = None


class PuzzleProgressStore(ABC):
    @abstractmethod
    def get(self, puzzle_type: str, puzzle_date: str) -> Optional[PuzzleProgress]:
        raise NotImplementedError

    @abstractmethod
    def get_many(
        self,
        puzzle_type: str,
        puzzle_dates: list[str],
    ) -> dict[str, PuzzleProgress]:
        raise NotImplementedError

    @abstractmethod
    def save(self, progress: PuzzleProgress) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, puzzle_type: str, puzzle_date: str) -> None:
        raise NotImplementedError


class SQLitePuzzleProgressStore(PuzzleProgressStore):
    def __init__(self, path: str | Path = DEFAULT_PROGRESS_DB_PATH) -> None:
        self.path = Path(path)
        self._initialized = False

    def get(self, puzzle_type: str, puzzle_date: str) -> Optional[PuzzleProgress]:
        self._initialize()

        record = PuzzleProgressRecord.get_or_none(
            PuzzleProgressRecord.puzzle_type == puzzle_type,
            PuzzleProgressRecord.puzzle_date == puzzle_date,
        )
        if record is None:
            return None

        return PuzzleProgress(
            puzzle_type=record.puzzle_type,
            puzzle_date=record.puzzle_date,
            guesses=list(json.loads(record.guesses_json)),
            correctness=list(json.loads(record.correctness_json)),
            elapsed_seconds=int(record.elapsed_seconds),
            completed=bool(record.completed),
            completed_seconds=record.completed_seconds,
        )

    def get_many(
        self,
        puzzle_type: str,
        puzzle_dates: list[str],
    ) -> dict[str, PuzzleProgress]:
        self._initialize()

        if not puzzle_dates:
            return {}

        records = PuzzleProgressRecord.select().where(
            PuzzleProgressRecord.puzzle_type == puzzle_type,
            PuzzleProgressRecord.puzzle_date.in_(puzzle_dates),
        )

        return {
            record.puzzle_date: PuzzleProgress(
                puzzle_type=record.puzzle_type,
                puzzle_date=record.puzzle_date,
                guesses=list(json.loads(record.guesses_json)),
                correctness=list(json.loads(record.correctness_json)),
                elapsed_seconds=int(record.elapsed_seconds),
                completed=bool(record.completed),
                completed_seconds=record.completed_seconds,
            )
            for record in records
        }

    def save(self, progress: PuzzleProgress) -> None:
        self._initialize()

        values = {
            "guesses_json": json.dumps(progress.guesses),
            "correctness_json": json.dumps(progress.correctness),
            "elapsed_seconds": max(0, int(progress.elapsed_seconds)),
            "completed": progress.completed,
            "completed_seconds": progress.completed_seconds,
            "updated_at": datetime.now(timezone.utc),
        }

        PuzzleProgressRecord.insert(
            puzzle_type=progress.puzzle_type,
            puzzle_date=progress.puzzle_date,
            **values,
        ).on_conflict(
            conflict_target=[
                PuzzleProgressRecord.puzzle_type,
                PuzzleProgressRecord.puzzle_date,
            ],
            update=values,
        ).execute()

    def delete(self, puzzle_type: str, puzzle_date: str) -> None:
        self._initialize()
        (
            PuzzleProgressRecord.delete()
            .where(
                PuzzleProgressRecord.puzzle_type == puzzle_type,
                PuzzleProgressRecord.puzzle_date == puzzle_date,
            )
            .execute()
        )

    def _initialize(self) -> None:
        if self._initialized:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        database.init(self.path)
        database.connect(reuse_if_open=True)
        database.create_tables([PuzzleProgressRecord])
        self._initialized = True


default_progress_store = SQLitePuzzleProgressStore()
