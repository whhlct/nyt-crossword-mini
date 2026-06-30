import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  Check,
  ChevronLeft,
  ChevronRight,
  Eraser,
  Eye,
  Grid3X3,
  Home,
  RotateCcw
} from "lucide-react";
import "./styles.css";

type Direction = "Across" | "Down";
type View = "games" | "puzzles" | "crossword";

type Game = {
  key: string;
  title: string;
  kind: "crossword" | "connections";
  implemented: boolean;
};

type PuzzleListing = {
  date: string;
  status: "not_started" | "in_progress" | "completed";
  status_label: string;
};

type Cell = {
  index: number;
  row: number;
  col: number;
  is_block: boolean;
  label: string;
  clue_ids: number[];
};

type Clue = {
  index: number;
  label: string;
  direction: Direction;
  cells: number[];
  text: string;
};

type Puzzle = {
  width: number;
  height: number;
  cells: Cell[];
  clues: Clue[];
};

type Progress = {
  guesses: string[];
  correctness: Array<boolean | null>;
  elapsed_seconds: number;
  completed: boolean;
  completed_seconds: number | null;
};

const PAGE_SIZE = 30;
const CROSSWORD_TYPES = new Set(["mini", "midi", "crossword"]);
const KEYBOARD_ROWS = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"];

function App() {
  const [view, setView] = useState<View>("games");
  const [games, setGames] = useState<Game[]>([]);
  const [selectedGame, setSelectedGame] = useState<Game | null>(null);
  const [puzzles, setPuzzles] = useState<PuzzleListing[]>([]);
  const [puzzlePage, setPuzzlePage] = useState(1);
  const [puzzleTotal, setPuzzleTotal] = useState(0);
  const [activeDate, setActiveDate] = useState("");
  const [puzzle, setPuzzle] = useState<Puzzle | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [direction, setDirection] = useState<Direction>("Across");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const saveTimer = useRef<number | null>(null);
  const startedAt = useRef(Date.now());

  const elapsedSeconds = progress
    ? progress.completed_seconds ?? progress.elapsed_seconds + Math.floor((Date.now() - startedAt.current) / 1000)
    : 0;

  useEffect(() => {
    fetchJson<{ games: Game[] }>("/api/games").then((data) => setGames(data.games));
  }, []);

  useEffect(() => {
    if (!selectedGame || view !== "puzzles") {
      return;
    }
    setLoading(true);
    fetchJson<{
      puzzles: PuzzleListing[];
      total: number;
    }>(`/api/crosswords/${selectedGame.key}/puzzles?page=${puzzlePage}&page_size=${PAGE_SIZE}`)
      .then((data) => {
        setPuzzles(data.puzzles);
        setPuzzleTotal(data.total);
      })
      .finally(() => setLoading(false));
  }, [selectedGame, puzzlePage, view]);

  useEffect(() => {
    if (!puzzle || !progress || progress.completed) {
      return;
    }
    const interval = window.setInterval(() => {
      setProgress((current) => (current ? { ...current } : current));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [puzzle, progress?.completed]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (view !== "crossword" || !puzzle || !progress) {
        return;
      }

      if (/^[a-z]$/i.test(event.key)) {
        event.preventDefault();
        enterLetter(event.key);
      } else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
        moveSelection(event.key);
      } else if (event.key === "Backspace" || event.key === "Delete") {
        event.preventDefault();
        eraseLetter();
      } else if (event.key === "Tab" || event.key === " ") {
        event.preventDefault();
        toggleDirection();
      } else if (event.key === "Enter") {
        event.preventDefault();
        selectNextClue();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const currentClue = useMemo(() => {
    if (!puzzle) {
      return null;
    }
    return clueForCell(puzzle, selectedIndex, direction) ?? clueForCell(puzzle, selectedIndex, otherDirection(direction));
  }, [puzzle, selectedIndex, direction]);

  const activeCells = new Set(currentClue?.cells ?? []);
  const pageCount = Math.max(1, Math.ceil(puzzleTotal / PAGE_SIZE));

  async function openGame(game: Game) {
    setSelectedGame(game);
    setPuzzlePage(1);
    setStatus("");
    setView(game.implemented && CROSSWORD_TYPES.has(game.key) ? "puzzles" : "games");
    if (!game.implemented) {
      setStatus("Connections is ready in the menu; its play screen can plug in here next.");
    }
  }

  async function openPuzzle(date: string) {
    if (!selectedGame) {
      return;
    }
    setLoading(true);
    const data = await fetchJson<{
      puzzle: Puzzle;
      progress: Progress;
    }>(`/api/crosswords/${selectedGame.key}/puzzles/${date}`);
    const firstOpen = data.puzzle.cells.find((cell) => !cell.is_block)?.index ?? 0;
    setPuzzle(data.puzzle);
    setProgress(data.progress);
    setSelectedIndex(firstOpen);
    setDirection("Across");
    setActiveDate(date);
    startedAt.current = Date.now();
    setStatus(data.progress.completed ? "Puzzle completed." : "Type letters to solve.");
    setView("crossword");
    setLoading(false);
  }

  function updateProgress(mutator: (current: Progress) => Progress, message = "") {
    if (!puzzle || !progress || progress.completed) {
      return;
    }

    const next = mutator(progress);
    setProgress(next);
    setStatus(message);
    scheduleSave(next);
  }

  function scheduleSave(next: Progress) {
    if (!selectedGame || !activeDate) {
      return;
    }
    if (saveTimer.current) {
      window.clearTimeout(saveTimer.current);
    }
    saveTimer.current = window.setTimeout(() => {
      saveProgress(next);
    }, 350);
  }

  async function saveProgress(next: Progress) {
    if (!selectedGame || !activeDate) {
      return;
    }
    const response = await fetchJson<{ progress: Progress }>(
      `/api/crosswords/${selectedGame.key}/puzzles/${activeDate}/progress`,
      {
        method: "PUT",
        body: JSON.stringify({
          guesses: next.guesses,
          correctness: next.correctness,
          elapsed_seconds: elapsedSeconds
        })
      }
    );
    setProgress(response.progress);
    if (response.progress.completed) {
      setStatus(`Puzzle completed in ${formatElapsed(response.progress.completed_seconds ?? elapsedSeconds)}.`);
    }
  }

  function enterLetter(letter: string) {
    if (!puzzle || !progress || progress.correctness[selectedIndex] === true) {
      return;
    }
    const guesses = [...progress.guesses];
    const correctness = [...progress.correctness];
    guesses[selectedIndex] = letter.toUpperCase();
    correctness[selectedIndex] = null;
    const nextIndex = nextEntryTarget(puzzle, selectedIndex, direction, correctness);
    setSelectedIndex(nextIndex.index);
    setDirection(nextIndex.direction);
    updateProgress((current) => ({ ...current, guesses, correctness }), "");
  }

  function eraseLetter() {
    if (!puzzle || !progress || progress.correctness[selectedIndex] === true) {
      return;
    }
    const guesses = [...progress.guesses];
    const correctness = [...progress.correctness];
    let index = selectedIndex;
    if (guesses[index]) {
      guesses[index] = "";
      correctness[index] = null;
    } else {
      const previous = previousCellInClue(puzzle, selectedIndex, direction);
      if (previous !== null && correctness[previous] !== true) {
        index = previous;
        guesses[index] = "";
        correctness[index] = null;
        setSelectedIndex(index);
      }
    }
    updateProgress((current) => ({ ...current, guesses, correctness }), "");
  }

  function moveSelection(key: string) {
    if (!puzzle) {
      return;
    }
    if (direction === "Across" && (key === "ArrowUp" || key === "ArrowDown")) {
      if (clueForCell(puzzle, selectedIndex, "Down")) {
        setDirection("Down");
      }
      return;
    }
    if (direction === "Down" && (key === "ArrowLeft" || key === "ArrowRight")) {
      if (clueForCell(puzzle, selectedIndex, "Across")) {
        setDirection("Across");
      }
      return;
    }

    const deltas: Record<string, [number, number]> = {
      ArrowLeft: [0, -1],
      ArrowRight: [0, 1],
      ArrowUp: [-1, 0],
      ArrowDown: [1, 0]
    };
    const [dr, dc] = deltas[key];
    let row = puzzle.cells[selectedIndex].row;
    let col = puzzle.cells[selectedIndex].col;
    while (true) {
      row += dr;
      col += dc;
      if (row < 0 || col < 0 || row >= puzzle.height || col >= puzzle.width) {
        break;
      }
      const index = row * puzzle.width + col;
      if (!puzzle.cells[index].is_block) {
        setSelectedIndex(index);
        break;
      }
    }
  }

  function toggleDirection() {
    if (!puzzle) {
      return;
    }
    const next = otherDirection(direction);
    if (clueForCell(puzzle, selectedIndex, next)) {
      setDirection(next);
    }
  }

  function selectNextClue() {
    if (!puzzle) {
      return;
    }
    const clueIds = puzzle.clues.filter((clue) => clue.direction === direction).map((clue) => clue.index);
    if (!clueIds.length) {
      return;
    }
    const current = currentClue;
    const currentPosition = current ? clueIds.indexOf(current.index) : -1;
    const next = puzzle.clues[clueIds[(currentPosition + 1) % clueIds.length]];
    setSelectedIndex(next.cells[0]);
  }

  async function checkPuzzle() {
    if (!selectedGame || !activeDate || !progress) {
      return;
    }
    const response = await fetchJson<{
      filled: number;
      total: number;
      wrong: number;
      progress: Progress;
    }>(`/api/crosswords/${selectedGame.key}/puzzles/${activeDate}/check`, {
      method: "POST",
      body: JSON.stringify({ guesses: progress.guesses, elapsed_seconds: elapsedSeconds })
    });
    setProgress(response.progress);
    if (response.progress.completed) {
      setStatus(`Puzzle completed in ${formatElapsed(response.progress.completed_seconds ?? elapsedSeconds)}.`);
    } else if (response.filled === 0) {
      setStatus("Nothing to check yet.");
    } else if (response.wrong === 0) {
      setStatus("All filled letters are correct so far.");
    } else {
      setStatus(`${response.wrong} filled letter${response.wrong === 1 ? "" : "s"} incorrect.`);
    }
  }

  async function revealPuzzle() {
    if (!selectedGame || !activeDate || !progress) {
      return;
    }
    const response = await fetchJson<{ progress: Progress }>(
      `/api/crosswords/${selectedGame.key}/puzzles/${activeDate}/reveal`,
      {
        method: "POST",
        body: JSON.stringify({ guesses: progress.guesses, elapsed_seconds: elapsedSeconds })
      }
    );
    setProgress(response.progress);
    setStatus("Puzzle revealed.");
  }

  async function clearPuzzle() {
    if (!selectedGame || !activeDate || !puzzle) {
      return;
    }
    const response = await fetchJson<{ progress: Progress }>(
      `/api/crosswords/${selectedGame.key}/puzzles/${activeDate}/progress`,
      { method: "DELETE" }
    );
    setProgress(response.progress);
    setSelectedIndex(puzzle.cells.find((cell) => !cell.is_block)?.index ?? 0);
    setDirection("Across");
    startedAt.current = Date.now();
    setStatus("Puzzle cleared.");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="icon-button" onClick={() => setView("games")} aria-label="Games">
          <Home size={20} />
        </button>
        <div>
          <h1>{selectedGame?.title ?? "NYT Games"}</h1>
          <p>{view === "crossword" ? activeDate : "Browser edition"}</p>
        </div>
        {view === "crossword" && <span className="timer">{formatElapsed(elapsedSeconds)}</span>}
      </header>

      {view === "games" && (
        <section className="game-grid">
          {games.map((game) => (
            <button
              className={`game-card ${game.implemented ? "" : "disabled"}`}
              key={game.key}
              onClick={() => openGame(game)}
            >
              <Grid3X3 size={26} />
              <span>{game.title}</span>
              <small>{game.implemented ? "Play" : "Coming next"}</small>
            </button>
          ))}
        </section>
      )}

      {view === "puzzles" && selectedGame && (
        <section className="puzzle-menu">
          <div className="section-toolbar">
            <button className="ghost-button" onClick={() => setView("games")}>
              <ArrowLeft size={18} />
              Games
            </button>
            <div className="pager">
              <button
                className="icon-button"
                disabled={puzzlePage <= 1}
                onClick={() => setPuzzlePage((page) => Math.max(1, page - 1))}
                aria-label="Previous page"
              >
                <ChevronLeft size={20} />
              </button>
              <span>
                {puzzlePage} / {pageCount}
              </span>
              <button
                className="icon-button"
                disabled={puzzlePage >= pageCount}
                onClick={() => setPuzzlePage((page) => Math.min(pageCount, page + 1))}
                aria-label="Next page"
              >
                <ChevronRight size={20} />
              </button>
            </div>
          </div>
          <div className="date-list" aria-busy={loading}>
            {puzzles.map((item) => (
              <button className="date-row" key={item.date} onClick={() => openPuzzle(item.date)}>
                <span>{item.date}</span>
                <small className={item.status}>{item.status_label}</small>
              </button>
            ))}
          </div>
        </section>
      )}

      {view === "crossword" && puzzle && progress && (
        <section className="play-layout">
          <div className="board-wrap">
            <div
              className="board"
              style={{ gridTemplateColumns: `repeat(${puzzle.width}, minmax(30px, 1fr))` }}
            >
              {puzzle.cells.map((cell) => (
                <button
                  className={[
                    "cell",
                    cell.is_block ? "block" : "",
                    activeCells.has(cell.index) ? "in-word" : "",
                    selectedIndex === cell.index ? "selected" : "",
                    progress.correctness[cell.index] === true ? "correct" : "",
                    progress.correctness[cell.index] === false ? "incorrect" : ""
                  ].join(" ")}
                  key={cell.index}
                  disabled={cell.is_block}
                  onClick={() => {
                    if (!cell.is_block) {
                      if (selectedIndex === cell.index) {
                        toggleDirection();
                      }
                      setSelectedIndex(cell.index);
                    }
                  }}
                  aria-label={cell.is_block ? "Block" : `Cell ${cell.label || cell.index + 1}`}
                >
                  {!cell.is_block && (
                    <>
                      <span className="cell-label">{cell.label}</span>
                      <span className="cell-guess">{progress.guesses[cell.index]}</span>
                    </>
                  )}
                </button>
              ))}
            </div>
          </div>

          <aside className="clue-pane">
            <div className="current-clue">
              <strong>{currentClue ? `${currentClue.label} ${currentClue.direction}` : ""}</strong>
              <span>{currentClue?.text}</span>
            </div>
            <div className="actions">
              <button onClick={checkPuzzle}>
                <Check size={18} />
                Check
              </button>
              <button onClick={revealPuzzle}>
                <Eye size={18} />
                Reveal
              </button>
              <button onClick={clearPuzzle}>
                <RotateCcw size={18} />
                Clear
              </button>
            </div>
            <div className="clue-lists">
              {(["Across", "Down"] as Direction[]).map((clueDirection) => (
                <div className="clue-list" key={clueDirection}>
                  <h2>{clueDirection}</h2>
                  {puzzle.clues
                    .filter((clue) => clue.direction === clueDirection)
                    .map((clue) => (
                      <button
                        className={currentClue?.index === clue.index ? "active" : ""}
                        key={clue.index}
                        onClick={() => {
                          setDirection(clue.direction);
                          setSelectedIndex(clue.cells[0]);
                        }}
                      >
                        <b>{clue.label}.</b> {clue.text}
                      </button>
                    ))}
                </div>
              ))}
            </div>
          </aside>

          <div className="mobile-keyboard">
            {KEYBOARD_ROWS.map((row) => (
              <div className="key-row" key={row}>
                {row.split("").map((letter) => (
                  <button key={letter} onClick={() => enterLetter(letter)}>
                    {letter}
                  </button>
                ))}
              </div>
            ))}
            <div className="key-row command-row">
              <button onClick={eraseLetter}>
                <Eraser size={18} />
              </button>
              <button onClick={toggleDirection}>{direction}</button>
              <button onClick={selectNextClue}>Next</button>
            </div>
          </div>
        </section>
      )}

      <footer className="status-bar">{status || "Ready"}</footer>
    </main>
  );
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

function clueForCell(puzzle: Puzzle, cellIndex: number, direction: Direction) {
  const cell = puzzle.cells[cellIndex];
  const clueId = cell.clue_ids.find((id) => puzzle.clues[id]?.direction === direction);
  return clueId === undefined ? null : puzzle.clues[clueId];
}

function otherDirection(direction: Direction): Direction {
  return direction === "Across" ? "Down" : "Across";
}

function nextEntryTarget(
  puzzle: Puzzle,
  selectedIndex: number,
  direction: Direction,
  correctness: Array<boolean | null>
) {
  const clue = clueForCell(puzzle, selectedIndex, direction) ?? clueForCell(puzzle, selectedIndex, otherDirection(direction));
  if (!clue) {
    return { direction, index: selectedIndex };
  }
  const ids = puzzle.clues.filter((item) => item.direction === clue.direction).map((item) => item.index);
  const currentPos = ids.indexOf(clue.index);
  const otherIds = puzzle.clues.filter((item) => item.direction !== clue.direction).map((item) => item.index);
  const ordered = [...ids.slice(currentPos), ...otherIds, ...ids.slice(0, currentPos)];
  const targets = ordered.flatMap((id) => puzzle.clues[id].cells.map((index) => ({ direction: puzzle.clues[id].direction, index })));
  const start = targets.findIndex((item) => item.index === selectedIndex && item.direction === clue.direction);
  for (let offset = 1; offset < targets.length; offset += 1) {
    const candidate = targets[(start + offset) % targets.length];
    if (correctness[candidate.index] !== true) {
      return candidate;
    }
  }
  return { direction, index: selectedIndex };
}

function previousCellInClue(puzzle: Puzzle, selectedIndex: number, direction: Direction) {
  const clue = clueForCell(puzzle, selectedIndex, direction);
  if (!clue) {
    return null;
  }
  const position = clue.cells.indexOf(selectedIndex);
  return position > 0 ? clue.cells[position - 1] : null;
}

function formatElapsed(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const hours = Math.floor(mins / 60);
  const minutes = mins % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}` : `${minutes}:${String(secs).padStart(2, "0")}`;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
