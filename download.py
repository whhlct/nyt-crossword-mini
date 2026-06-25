import asyncio
import argparse
import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import aiohttp
from tqdm.asyncio import tqdm


# Daily Crossword Date Range: 1993/11/21 - Present
# Mini Crossword Date Range:  2014/08/21 - Present
# Connections Date Range:     2023/06/12 - Present
# Midi Crossword Date Range:  2026/02/25 - Present

PUZZLE_DATA_DIR = Path("puzzle_data")
MAX_CONCURRENT_DOWNLOADS = 20

DEFAULT_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded",
    "x-games-auth-bypass": "true",  # Only necessary header for crossword requests
}


def process_crossword_puzzle_data(data: dict[str, Any]) -> dict[str, Any]:
    """Remove bulky board SVG data from a crossword-style puzzle response."""
    processed_data = data.copy()
    body = processed_data.get("body")
    if isinstance(body, list):
        processed_data["body"] = [
            {key: value for key, value in puzzle.items() if key != "board"}
            if isinstance(puzzle, dict)
            else puzzle
            for puzzle in body
        ]
    return processed_data


def process_connections_puzzle_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return Connections puzzle data unchanged."""
    return data


@dataclass(frozen=True)
class PuzzleConfig:
    """Configuration needed to fetch and store one puzzle type."""

    key: str
    name: str
    directory: str
    start_date: date
    json_url_template: str
    process_data: Callable[[dict[str, Any]], dict[str, Any]]
    requires_cookies: bool = False
    default_headers: dict[str, str] | None = None

    def json_url(self, puzzle_date: date) -> str:
        return self.json_url_template.format(date=puzzle_date.isoformat())

    def output_path(self, puzzle_date: date) -> Path:
        return PUZZLE_DATA_DIR / self.directory / f"{puzzle_date.isoformat()}.json"

    def original_path(self, puzzle_date: date, original_data_dir: Path) -> Path:
        return original_data_dir / self.directory / f"{puzzle_date.isoformat()}.json"


CONNECTIONS = PuzzleConfig(
    key="connections",
    name="connections",
    directory="connections",
    start_date=date(2023, 6, 12),
    json_url_template="https://www.nytimes.com/svc/connections/v2/{date}.json",
    process_data=process_connections_puzzle_data,
)

MINI = PuzzleConfig(
    key="mini",
    name="mini crossword",
    directory="mini",
    start_date=date(2014, 8, 21),
    json_url_template="https://www.nytimes.com/svc/crosswords/v6/puzzle/mini/{date}.json",
    process_data=process_crossword_puzzle_data,
    requires_cookies=True,
    default_headers=DEFAULT_HEADERS,
)

CROSSWORD = PuzzleConfig(
    key="crossword",
    name="daily crossword",
    directory="crossword",
    start_date=date(1993, 11, 21),
    json_url_template="https://www.nytimes.com/svc/crosswords/v6/puzzle/daily/{date}.json",
    process_data=process_crossword_puzzle_data,
    requires_cookies=True,
    default_headers=DEFAULT_HEADERS,
)

MIDI = PuzzleConfig(
    key="midi",
    name="midi crossword",
    directory="midi",
    start_date=date(2026, 2, 25),
    json_url_template="https://www.nytimes.com/svc/crosswords/v6/puzzle/midi/{date}.json",
    process_data=process_crossword_puzzle_data,
    requires_cookies=True,
    default_headers=DEFAULT_HEADERS,
)

PUZZLE_CONFIGS = (MINI, MIDI, CROSSWORD, CONNECTIONS)
PUZZLE_CONFIG_BY_KEY = {config.key: config for config in PUZZLE_CONFIGS}


def mini_page_url(puzzle_date: date) -> str:
    return f"https://www.nytimes.com/crosswords/game/mini/{puzzle_date:%Y/%m/%d}"


def iter_dates(start_date: date, end_date: date):
    """Yield dates from start_date to end_date, inclusive."""
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def save_json(path: Path, data: dict[str, Any]) -> Path:
    """Save JSON data to a file and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return path


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON data from a file."""
    return json.loads(path.read_text(encoding="utf-8"))


async def get_page_cookies(session: aiohttp.ClientSession, url: str) -> dict[str, str]:
    """Fetch a page and return its response cookies."""
    async with session.get(url) as response:
        response.raise_for_status()
        return {key: cookie.value for key, cookie in response.cookies.items()}


async def get_mini_cookies(
    session: aiohttp.ClientSession,
    puzzle_date: date | None = None,
) -> dict[str, str]:
    """Fetch the NYT Mini Crossword page to get cookies."""
    return await get_page_cookies(session, mini_page_url(puzzle_date or date.today()))


async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Fetch JSON from a URL."""
    async with session.get(url, headers=headers, cookies=cookies) as response:
        response.raise_for_status()
        return await response.json()


async def download_puzzle(
    session: aiohttp.ClientSession,
    config: PuzzleConfig,
    puzzle_date: date,
    *,
    original_data_dir: Path | None = None,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Path | None:
    """Fetch and save one puzzle unless it already exists."""
    output_path = config.output_path(puzzle_date)
    if output_path.is_file():
        return None

    original_path = (
        config.original_path(puzzle_date, original_data_dir)
        if original_data_dir is not None
        else None
    )

    if original_path is not None and original_path.is_file():
        # Original puzzle data found
        data = load_json(original_path)
    else:
        request_headers = headers if headers is not None else config.default_headers
        request_cookies = cookies

        if config.requires_cookies and request_cookies is None:
            request_cookies = await get_mini_cookies(session)

        try:
            data = await fetch_json(
                session,
                config.json_url(puzzle_date),
                headers=request_headers,
                cookies=request_cookies,
            )
        except aiohttp.ClientResponseError as error:
            print(f"Failed to fetch {config.name} for {puzzle_date}: {error}")
            return None

        if original_path is not None:
            # If original puzzle data path is set, save the OPD there
            save_json(original_path, data)

    return save_json(output_path, config.process_data(data))


async def download_puzzle_range(
    config: PuzzleConfig,
    start_date: date,
    end_date: date,
    *,
    original_data_dir: Path | None = None,
) -> None:
    """Download a puzzle type for every date in the inclusive range."""
    async with aiohttp.ClientSession() as session:
        cookies = None
        if config.requires_cookies:
            cookies = await get_mini_cookies(session)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

        async def download_with_limit(puzzle_date: date) -> Path | None:
            async with semaphore:
                return await download_puzzle(
                    session,
                    config,
                    puzzle_date,
                    original_data_dir=original_data_dir,
                    cookies=cookies,
                )

        tasks = [
            download_with_limit(puzzle_date)
            for puzzle_date in iter_dates(start_date, end_date)
        ]
        await tqdm.gather(*tasks)


def parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date argument."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a valid date. Use YYYY-MM-DD."
        ) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download NYT puzzle JSON files.",
        usage=(
            "download.py [--original-puzzle-data-dir PATH] "
            "[mini/midi/crossword/connections] [date YYYY-MM-DD]"
        ),
    )
    parser.add_argument(
        "puzzle_type",
        nargs="?",
        choices=PUZZLE_CONFIG_BY_KEY,
        help="Puzzle type to download. If omitted, all puzzle types are downloaded.",
    )
    parser.add_argument(
        "start_date",
        nargs="?",
        type=parse_date,
        help="Start date in YYYY-MM-DD format. Requires a puzzle type.",
    )
    parser.add_argument(
        "--original-puzzle-data-dir",
        type=Path,
        help=(
            "Optional directory containing raw downloaded puzzle JSON. "
            "Files found here are used as a cache; newly fetched raw files are also saved here."
        ),
    )

    args = parser.parse_args()

    if args.start_date is not None and args.puzzle_type is None:
        parser.error("date can only be specified after a puzzle type")

    today = date.today()
    if args.start_date is not None and args.start_date > today:
        parser.error(f"date cannot be in the future: {args.start_date}")

    if args.puzzle_type is not None and args.start_date is not None:
        config = PUZZLE_CONFIG_BY_KEY[args.puzzle_type]
        if args.start_date < config.start_date:
            parser.error(
                f"{config.name} starts on {config.start_date}; "
                f"got {args.start_date}"
            )

    return args


def download_plan(args: argparse.Namespace) -> list[tuple[PuzzleConfig, date]]:
    """Return puzzle configs and start dates implied by CLI arguments."""
    if args.puzzle_type is None:
        return [(config, config.start_date) for config in PUZZLE_CONFIGS]

    config = PUZZLE_CONFIG_BY_KEY[args.puzzle_type]
    return [(config, args.start_date or config.start_date)]


async def evaluate_unnecessary_request_headers(
    url: str,
    cookies: dict[str, str],
    delay_seconds: float = 0.5,
) -> None:
    """Print each default header's response status when omitted from a request."""
    async with aiohttp.ClientSession() as session:
        for header in DEFAULT_HEADERS:
            modified_headers = DEFAULT_HEADERS.copy()
            del modified_headers[header]

            async with session.get(url, headers=modified_headers, cookies=cookies) as response:
                print(f"{header:<30} - {response.status}")

            await asyncio.sleep(delay_seconds)


async def main() -> None:
    args = parse_args()
    end_date = date.today()

    for config, start_date in download_plan(args):
        print(f"Downloading {config.name} from {start_date} to {end_date}")
        await download_puzzle_range(
            config,
            start_date,
            end_date,
            original_data_dir=args.original_puzzle_data_dir,
        )

if __name__ == "__main__":
    start_time = time.perf_counter()
    asyncio.run(main())
    end_time = time.perf_counter()
    print(f"Total time taken: {end_time - start_time:.2f} seconds")
