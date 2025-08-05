import requests
import json
import time

from mini_crossword import MiniCrossword


URL_MINI_PAGE = "https://www.nytimes.com/crosswords/game/mini/2025/08/03"
URL_MINI_JSON = "https://www.nytimes.com/svc/crosswords/v6/puzzle/mini/2025-08-03.json"

URL_CONNECTIONS_JSON = "https://www.nytimes.com/svc/connections/v2/2025-08-05.json"

HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/x-www-form-urlencoded',
    'x-games-auth-bypass': 'true', # Only necessary header for the request
}

def get_page_cookies(url: str) -> dict[str, str]:
    """Fetch the NYT Mini Crossword page."""

    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch page: {response.status_code}")

    return response.cookies.get_dict()


def get_mini(url: str, cookies: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    """Fetch the NYT Mini Crossword."""

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


def get_connections(url: str, cookies: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> None:
    """Fetch the NYT Mini Crossword connections.
    Doesn't need cookies or headers."""

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


if __name__ == "__main__":
    # Fetch the NYT Mini Crossword page to get cookies
    page_cookies = get_page_cookies(URL_MINI_PAGE)
    """
    # Print cookies
    print("Cookies:")
    for cookie_name, cookie_value in page_cookies.items():
        print(f"{cookie_name}: {cookie_value}")
    """
    # Fetch the NYT Mini Crossword using the cookies
    mini_data = get_mini(URL_MINI_JSON, page_cookies)
    # print(f"Mini Crossword Data:\n{json.dumps(mini_data)}")

    """
    # Validate the mini crossword data
    try:
        mini_crossword = MiniCrossword.model_validate(mini_data)
        print(f"Mini Crossword ID: {mini_crossword.id}")
    except Exception as e:
        print(f"Error validating Mini Crossword data: {e}")
    """

    # Evaluate unnecessary request headers
    #evaluate_unecessary_request_headers(URL_JSON, page_cookies)
    """

    # Save the crossword data to a file
    with open("mini_crossword_2.json", "w") as file:
        json.dump(mini_data, file, indent=4)
    """

    # Fetch the NYT connections data
    connections_data = get_connections(URL_CONNECTIONS_JSON)
    #print(f"Connections Data:\n{json.dumps(connections_data, indent=4)}")
    # Save the connections data to a file
    with open("connections_2025-08-05.json", "w") as file:
        json.dump(connections_data, file, indent=4)