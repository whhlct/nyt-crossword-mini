from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class Cell(BaseModel):
    answer: str
    clues: list[int]
    label: str
    type: int

    model_config = ConfigDict(extra="forbid")


class Direction(str, Enum):
    ACROSS = "Across"
    DOWN = "Down"


class ClueList(BaseModel):
    clues: list[int]
    # Name is either 'Across' or 'Down'
    name: Direction


class ClueText(BaseModel):
    formatted: str | None = None
    plain: str


class Clue(BaseModel):
    cells: list[int]
    direction: Direction
    label: str
    relatives: list[int] | None = None
    text: list[ClueText]


class Dimensions(BaseModel):
    height: int
    width: int


class MiniCrosswordBody(BaseModel):
    board: str
    cells: list[Cell | dict]
    clue_lists: list[ClueList] = Field(alias='clueLists')
    clues: list[Clue]
    dimensions: Dimensions
    svg: dict = Field(alias='SVG')



class MiniCrossword(BaseModel):
    body: list[MiniCrosswordBody]
    constructors: list[str]
    copyright: str
    id: int
    last_updated: str = Field(alias='lastUpdated')
    publication_date: str = Field(alias='publicationDate')
    subcategory: int
