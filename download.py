import asyncio
import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import aiohttp
from tqdm.asyncio import tqdm


# Daily Crossword Date Range: 1993/11/21 - Present
# Mini Crossword Date Range:  2014/08/21 - Present
# Connections Date Range:     2023/06/12 - Present
# Midi Crossword Date Range:  2026/02/25 - Present

PUZZLE_DATA_DIR = Path("puzzle_data")

DEFAULT_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded",
    "x-games-auth-bypass": "true",  # Only necessary header for crossword requests
}


@dataclass(frozen=True)
class PuzzleConfig:
    """Configuration needed to fetch and store one puzzle type."""

    name: str
    directory: str
    json_url_template: str
    requires_cookies: bool = False
    default_headers: dict[str, str] | None = None

    def json_url(self, puzzle_date: date) -> str:
        return self.json_url_template.format(date=puzzle_date.isoformat())

    def output_path(self, puzzle_date: date) -> Path:
        return PUZZLE_DATA_DIR / self.directory / f"{puzzle_date.isoformat()}.json"


CONNECTIONS = PuzzleConfig(
    name="connections",
    directory="connections",
    json_url_template="https://www.nytimes.com/svc/connections/v2/{date}.json",
)

MINI = PuzzleConfig(
    name="mini crossword",
    directory="mini",
    json_url_template="https://www.nytimes.com/svc/crosswords/v6/puzzle/mini/{date}.json",
    requires_cookies=True,
    default_headers=DEFAULT_HEADERS,
)

CROSSWORD = PuzzleConfig(
    name="daily crossword",
    directory="crossword",
    json_url_template="https://www.nytimes.com/svc/crosswords/v6/puzzle/daily/{date}.json",
    requires_cookies=True,
    default_headers=DEFAULT_HEADERS,
)

MIDI = PuzzleConfig(
    name="midi crossword",
    directory="midi",
    json_url_template="https://www.nytimes.com/svc/crosswords/v6/puzzle/midi/{date}.json",
    requires_cookies=True,
    default_headers=DEFAULT_HEADERS,
)


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
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Path | None:
    """Fetch and save one puzzle unless it already exists."""
    output_path = config.output_path(puzzle_date)
    if output_path.is_file():
        return None

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

    return save_json(output_path, data)


async def download_puzzle_range(
    config: PuzzleConfig,
    start_date: date,
    end_date: date,
) -> None:
    """Download a puzzle type for every date in the inclusive range."""
    async with aiohttp.ClientSession() as session:
        cookies = None
        if config.requires_cookies:
            cookies = await get_mini_cookies(session)

        tasks = [
            download_puzzle(session, config, puzzle_date, cookies=cookies)
            for puzzle_date in iter_dates(start_date, end_date)
        ]
        await tqdm.gather(*tasks)


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
    #await download_puzzle_range(CROSSWORD, date(2026, 6, 1), date.today())
    #await download_puzzle_range(MINI, date(2026, 6, 1), date.today())
    #await download_puzzle_range(CONNECTIONS, date(2026, 6, 1), date.today())
    await download_puzzle_range(MIDI, date(2026, 2, 25), date.today())

if __name__ == "__main__":
    start_time = time.perf_counter()
    asyncio.run(main())
    end_time = time.perf_counter()
    print(f"Total time taken: {end_time - start_time:.2f} seconds")
