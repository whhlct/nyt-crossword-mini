import aiohttp
import asyncio

import requests
import json
import time
import os
from datetime import date, timedelta
from typing import Optional

from mini_crossword import MiniCrossword


URL_MINI_PAGE = "https://www.nytimes.com/crosswords/game/mini/2025/08/03"
URL_MINI_JSON = "https://www.nytimes.com/svc/crosswords/v6/puzzle/mini/2025-08-03.json"
PUZZLE_DATA_DIR = "puzzle_data"
CONNECTIONS_DIR = "connections"
MINI_DIR = "mini"


HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/x-www-form-urlencoded',
    'x-games-auth-bypass': 'true', # Only necessary header for the request
}


## URL Generators
# Connections JSON
def connections_json_url_str(date: str) -> str:
    return f"https://www.nytimes.com/svc/connections/v2/{date}.json"

def connections_json_url(date: date) -> str:
    return connections_json_url_str(date.strftime("%Y-%m-%d"))


# Mini JSON
def mini_json_url_str(date: str) -> str:
    return f"https://www.nytimes.com/svc/crosswords/v6/puzzle/mini/{date}.json"

def mini_json_url(date: date) -> str:
    return mini_json_url_str(date.strftime("%Y-%m-%d"))


# Mini Page
def mini_page_url_str(date: str) -> str:
    return f"https://www.nytimes.com/crosswords/game/mini/{date}"

def mini_page_url(date: date) -> str:
    return mini_page_url_str(date.strftime("%Y/%m/%d"))


## File Operations
# Path Generators
def connections_json_path(date: str) -> str:
    return os.path.join(PUZZLE_DATA_DIR, CONNECTIONS_DIR, f"{date}.json")

def mini_json_path(date: str) -> str:
    return os.path.join(PUZZLE_DATA_DIR, MINI_DIR, f"{date}.json")

# File Save
def save_json_to_file(path: str, data: dict) -> str:
    """Save JSON data to a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as file:
        json.dump(data, file, indent=4)
    return path

# Connections JSON
def save_connections_json(date: str, data: dict) -> str:
    """Save connections JSON data to a file."""
    return save_json_to_file(connections_json_path(date), data)

# Mini JSON
def save_mini_json(date: str, data: dict) -> str:
    """Save mini JSON data to a file."""
    return save_json_to_file(mini_json_path(date), data)


def get_page_cookies(url: str) -> dict[str, str]:
    """Fetch a page and return its cookies."""

    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch page: {response.status_code}")

    return response.cookies.get_dict()


def get_mini_cookies(puzzle_date: date | None = None) -> dict[str, str]:
    """Fetch the NYT Mini Crossword page to get cookies."""
    if puzzle_date is None:
        puzzle_date = date.today()
    url = mini_page_url(puzzle_date)

    return get_page_cookies(url)


def evaluate_unecessary_request_headers(url: str, cookies: dict[str, str]) -> None:
    """Evaluate which request headers are unecessary.
    Loops through each item in HEADERS, and tries a request without it."""
    for header in HEADERS:
        modified_headers = HEADERS.copy()
        del modified_headers[header]

        response = requests.get(
            url,
            headers=modified_headers,
            cookies=cookies,
        )
        
        print(f"{header:<30} - {response.status_code}")
        
        time.sleep(0.5)


## Puzzle HTTP Request Functions
async def fetch_data(session: aiohttp.ClientSession, url: str, headers: Optional[dict[str, str]], cookies: Optional[dict[str, str]]) -> dict:
    async with session.get(url, headers=headers, cookies=cookies) as response:
        response.raise_for_status()  # Raise an error for bad responses
        return await response.json()

# Connections
async def fetch_connections(session: aiohttp.ClientSession, date: date, cookies: Optional[dict[str, str]] = None, headers: Optional[dict[str, str]] = None) -> dict:
    """Fetch the NYT Mini Crossword connections.
    Doesn't need cookies or headers."""

    url = connections_json_url(date)

    response = await fetch_data(session, url, headers=headers, cookies=cookies)

    return response

# Mini Crossword
async def fetch_mini(session: aiohttp.ClientSession, date: date, cookies: dict[str, str], headers: Optional[dict[str, str]] = None) -> dict:
    """Fetch the NYT Mini Crossword.
    Requires cookies from the page request.
    Request headers can be customized, otherwise defaults to HEADERS."""

    url = mini_json_url(date)

    if headers is None:
        headers = HEADERS

    response = await fetch_data(session, url, headers=headers, cookies=cookies)

    return response


## Puzzle Fetch and Save Functions
# Connections
async def fetch_and_save_connections(session: aiohttp.ClientSession, date: date, cookies: Optional[dict[str, str]] = None, headers: Optional[dict[str, str]] = None) -> None:
    """Fetch and save the connections for a given date."""
    # Fetch the connections data
    connections_data = await fetch_connections(session, date, cookies, headers)
    print("Connections data fetched successfully.")
    # Save the connections data to a file
    saved_file_path = save_connections_json(date.strftime("%Y-%m-%d"), connections_data)
    print(f"Connections data saved to {saved_file_path}.")

# Mini Crossword
async def fetch_and_save_mini(session: aiohttp.ClientSession, date: date, cookies: dict[str, str] | None = None) -> None:
    """Fetch and save the mini crossword for a given date."""
    # Fetch the NYT Mini Crossword page to get cookies
    if cookies is None:
        cookies = get_mini_cookies()
    # Fetch the NYT Mini Crossword using the cookies
    mini_data = await fetch_mini(session, date, cookies)
    print("Mini crossword fetched successfully.")
    # Save the crossword data to a file
    saved_file_path = save_mini_json(date.strftime("%Y-%m-%d"), mini_data)
    print(f"Mini crossword saved to {saved_file_path}.")


## Mass Fetch and Save
# Date Range
def date_range(start_date: date, end_date: date) -> list[date]:
    """Generate a list of dates from start_date to end_date (inclusive)."""
    current_date = start_date
    dates = []
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    return dates

async def fetch_and_save_connections_range(start_date: date, end_date: date) -> None:
    dates = date_range(start_date, end_date)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_and_save_connections(session, d) for d in dates]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(fetch_and_save_connections_range(date(2025, 9, 1), date(2025, 9, 23)))
    end_time = time.time()
    print(f"Total time taken: {end_time - start_time} seconds")
