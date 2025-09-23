import requests
import json
import time
import os
from datetime import date

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
# Connections
def fetch_connections(date: date, cookies: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> dict:
    """Fetch the NYT Mini Crossword connections.
    Doesn't need cookies or headers."""

    url = connections_json_url(date)

    response = requests.get(
        url,
        headers=headers,
        cookies=cookies,
    )
    response.raise_for_status()  # Raise an error for bad responses

    # Return the JSON response if needed
    try:
        connections_data = response.json()
        return connections_data
    except ValueError:
        raise Exception("Failed to parse JSON response")

# Mini Crossword
def fetch_mini(date: date, cookies: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    """Fetch the NYT Mini Crossword.
    Requires cookies from the page request.
    Request headers can be customized, otherwise defaults to HEADERS."""

    url = mini_json_url(date)

    if headers is None:
        headers = HEADERS

    response = requests.get(
        url, 
        headers=headers,
        cookies=cookies,
    )
    response.raise_for_status()  # Raise an error for bad responses

    # Return the JSON response if needed
    try:
        crossword_data = response.json()
        return crossword_data
    except ValueError:
        raise Exception("Failed to parse JSON response")


## Puzzle Fetch and Save Functions
# Connections
def fetch_and_save_connections(date: date, cookies: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> None:
    """Fetch and save the connections for a given date."""
    # Fetch the connections data
    connections_data = fetch_connections(date, cookies, headers)
    print("Connections data fetched successfully.")
    # Save the connections data to a file
    saved_file_path = save_connections_json(date.strftime("%Y-%m-%d"), connections_data)
    print(f"Connections data saved to {saved_file_path}.")

# Mini Crossword
def fetch_and_save_mini(date: date, cookies: dict[str, str] | None = None) -> None:
    """Fetch and save the mini crossword for a given date."""
    # Fetch the NYT Mini Crossword page to get cookies
    if cookies is None:
        cookies = get_mini_cookies()
    # Fetch the NYT Mini Crossword using the cookies
    mini_data = fetch_mini(date, cookies)
    print("Mini crossword fetched successfully.")
    # Save the crossword data to a file
    saved_file_path = save_mini_json(date.strftime("%Y-%m-%d"), mini_data)
    print(f"Mini crossword saved to {saved_file_path}.")


if __name__ == "__main__":
    fetch_and_save_mini(date(2025, 9, 22))
    fetch_and_save_connections(date(2025, 9, 22))
