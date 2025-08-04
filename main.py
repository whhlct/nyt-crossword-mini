import requests
import json


URL_PAGE = "https://www.nytimes.com/crosswords/game/mini/2025/08/03"
URL_JSON = "https://www.nytimes.com/svc/crosswords/v6/puzzle/mini/2025-08-03.json"


def get_page_cookies(url: str) -> dict[str, str]:
    """Fetch the NYT Mini Crossword page."""

    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch page: {response.status_code}")

    return response.cookies.get_dict()


def get_mini(url: str, cookies: dict[str, str]) -> dict:
    """Fetch the NYT Mini Crossword."""

    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded',
        'priority': 'u=1, i',
        'referer': 'https://www.nytimes.com/crosswords/game/mini/2025/08/03',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'x-games-auth-bypass': 'true',
    }

    response = requests.get(
        url, 
        headers=headers,
        cookies=cookies,
    )
    if response.status_code == 200:
        print("Successfully retrieved the crossword!")
    else:
        print("Failed to retrieve the crossword.")

    print(f"Status code: {response.status_code}")

    # Return the JSON response if needed
    try:
        crossword_data = response.json()
        return crossword_data
    except ValueError:
        raise Exception("Failed to parse JSON response")


if __name__ == "__main__":
    # Fetch the NYT Mini Crossword page to get cookies
    page_cookies = get_page_cookies(URL_PAGE)
    """
    # Print cookies
    print("Cookies:")
    for cookie_name, cookie_value in page_cookies.items():
        print(f"{cookie_name}: {cookie_value}")
    """

    # Fetch the NYT Mini Crossword using the cookies
    mini_data = get_mini(URL_JSON, page_cookies)

    # Save the crossword data to a file
    with open("mini_crossword.json", "w") as file:
        json.dump(mini_data, file, indent=4)
