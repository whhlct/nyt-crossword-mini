#!/usr/bin/env python3
"""Top-level launcher for the NYT games TUI."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from crossword import GameScreen, PuzzleMenuScreen


class GameMenuScreen(Screen):
    """Start screen that lets the user choose a game."""

    BINDINGS = [("ctrl+q", "quit", "Quit")]

    GAME_CHOICES = (
        ("mini", "Mini"),
        ("midi", "Midi"),
        ("crossword", "Crossword"),
        ("connections", "Connections"),
    )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="game-menu"):
            yield Static("NYT Games", id="game-title")
            yield Static("Choose a game", id="game-subtitle")
            yield ListView(
                *[
                    ListItem(Label(label))
                    for _game_key, label in self.GAME_CHOICES
                ],
                id="game-list",
            )
            yield Static("Enter selects. Ctrl+Q quits.", id="game-help")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#game-list", ListView).index = 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        selected_index = event.list_view.index
        if selected_index is None:
            return

        game_key = self.GAME_CHOICES[selected_index][0]
        if game_key == "connections":
            self.app.push_screen(ConnectionsPlaceholderScreen())
            return

        self.app.push_screen(PuzzleMenuScreen(game_key))


class ConnectionsPlaceholderScreen(Screen):
    """Temporary screen until a Connections TUI exists."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="game-menu"):
            yield Static("Connections", id="game-title")
            yield Static("Connections is not implemented yet.", id="game-subtitle")
            yield Static("Esc returns to game selection. Ctrl+Q quits.", id="game-help")

        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()


class NYTGamesApp(App):
    CSS = (
        GameScreen.CSS
        + """
    #game-menu {
        width: 50;
        height: auto;
        max-height: 1fr;
        margin: 1 2;
        padding: 1 2;
        border: round white;
    }

    #game-title {
        text-style: bold;
        height: 1;
        content-align: center middle;
    }

    #game-subtitle {
        height: 1;
        margin-bottom: 1;
        content-align: center middle;
    }

    #game-list {
        height: 4;
    }

    #game-help {
        height: 1;
        margin-top: 1;
        content-align: center middle;
    }
    """
    )

    def on_mount(self) -> None:
        self.push_screen(GameMenuScreen())


def main() -> None:
    NYTGamesApp().run()


if __name__ == "__main__":
    main()
