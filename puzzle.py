import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any
from typing import Optional
from xml.dom import minidom


Direction = str  # "Across" or "Down"
NUMBER_RE = r"-?(?:\d+e\d+|\d+(?:\.\d+)?|\.\d+)"


def svg_style_attribute(styles: list[dict[str, Any]]) -> str:
    """Convert JSON SVG style records to a CSS style attribute value."""
    return ";".join(
        f"{style['name']}:{style['value']}"
        for style in styles
        if "name" in style and "value" in style
    )


def parse_svg_style_attribute(style_attribute: str) -> list[dict[str, str]]:
    """Convert a CSS style attribute value to JSON SVG style records."""
    styles = []
    for rule in style_attribute.split(";"):
        if not rule.strip() or ":" not in rule:
            continue

        name, value = rule.split(":", 1)
        styles.append({"name": name.strip(), "value": value.strip()})

    return styles


def json_svg_to_svg(svg: dict[str, Any]) -> str:
    """Convert NYT's JSON-formatted SVG tree to an XML SVG string."""
    name = str(svg["name"])
    attributes = [
        (str(attribute["name"]), str(attribute["value"]))
        for attribute in svg.get("attributes", [])
    ]

    style = svg_style_attribute(svg.get("styles", []))
    if style:
        attributes.append(("style", style))

    rendered_attributes = "".join(
        f' {name}="{escape(value, quote=True)}"'
        for name, value in attributes
    )
    content = escape(str(svg.get("content", "")))
    children = "".join(json_svg_to_svg(child) for child in svg.get("children", []))

    if not content and not children:
        return f"<{name}{rendered_attributes}/>"

    return f"<{name}{rendered_attributes}>{content}{children}</{name}>"


def svg_to_json_svg(svg: str) -> dict[str, Any]:
    """Convert an XML SVG string to NYT-style JSON SVG data."""
    document = minidom.parseString(svg)
    return svg_element_to_json(document.documentElement)


def format_svg_number(value: str | float) -> str:
    """Format SVG numeric values like NYT's JSON SVG representation."""
    return f"{float(value):.2f}"


def normalize_svg_attribute_value(name: str, value: str) -> str:
    """Normalize XML SVG attribute values to NYT JSON SVG conventions."""
    if name == "viewBox":
        return " ".join("0" if float(part) == 0 else format_svg_number(part) for part in value.split())
    if name in {"x", "y", "width", "height", "x1", "y1", "x2", "y2", "cx", "cy", "r", "font-size", "stroke-width"}:
        return format_svg_number(value)
    if value == "#000":
        return "black"
    if value == "#d3d3d3":
        return "lightgray"
    return value


def path_node_to_json(node: dict[str, Any]) -> dict[str, Any]:
    """Expand compact NYT SVG path nodes to their JSON SVG equivalents."""
    attributes = {
        attribute["name"]: attribute["value"]
        for attribute in node.get("attributes", [])
    }
    path = attributes.get("d", "")

    line_match = re.fullmatch(
        rf"M({NUMBER_RE}) ({NUMBER_RE}) ({NUMBER_RE}) ({NUMBER_RE})z",
        path,
    )
    if line_match:
        converted_attributes = [
            {"name": "x1", "value": format_svg_number(line_match.group(1))},
            {"name": "y1", "value": format_svg_number(line_match.group(2))},
            {"name": "x2", "value": format_svg_number(line_match.group(3))},
            {"name": "y2", "value": format_svg_number(line_match.group(4))},
        ]
        if "class" in attributes:
            converted_attributes.append({"name": "class", "value": attributes["class"]})
        return {"name": "line", "attributes": converted_attributes}

    polygon_match = re.fullmatch(
        rf"M({NUMBER_RE}) ({NUMBER_RE})H({NUMBER_RE})L({NUMBER_RE}) ({NUMBER_RE})z",
        path,
    )
    if polygon_match:
        points = (
            f"{format_svg_number(polygon_match.group(1))},{format_svg_number(polygon_match.group(2))} "
            f"{format_svg_number(polygon_match.group(3))},{format_svg_number(polygon_match.group(2))} "
            f"{format_svg_number(polygon_match.group(4))},{format_svg_number(polygon_match.group(5))}"
        )
        converted_attributes = [{"name": "points", "value": points}]
        if "class" in attributes:
            converted_attributes.append({"name": "class", "value": attributes["class"]})
        return {"name": "polygon", "attributes": converted_attributes}

    rect_match = re.fullmatch(
        rf"M({NUMBER_RE}) ({NUMBER_RE})h({NUMBER_RE})v({NUMBER_RE})H({NUMBER_RE})z",
        path,
    )
    if rect_match:
        converted_attributes = [
            {"name": "x", "value": format_svg_number(rect_match.group(1))},
            {"name": "y", "value": format_svg_number(rect_match.group(2))},
            {"name": "width", "value": format_svg_number(rect_match.group(3))},
            {"name": "height", "value": format_svg_number(rect_match.group(4))},
        ]
        for attribute in node.get("attributes", []):
            if attribute["name"] not in {"d", "class"}:
                converted_attributes.append(attribute)
        return {"name": "rect", "attributes": converted_attributes}

    if attributes.get("class") == "lines":
        compact_segments = re.findall(
            rf"M({NUMBER_RE}) ({NUMBER_RE})([hv])({NUMBER_RE})",
            path,
        )
        expanded_segments = []
        for x, y, direction, length in compact_segments:
            dx = length if direction == "h" else "0"
            dy = length if direction == "v" else "0"
            expanded_segments.append(
                f"M{format_svg_number(x)},{format_svg_number(y)} "
                f"l{format_svg_number(dx)},{format_svg_number(dy)}"
            )

        converted_attributes = [{"name": "d", "value": " ".join(expanded_segments)}]
        for attribute in node.get("attributes", []):
            if attribute["name"] not in {"d", "class"}:
                converted_attributes.append(attribute)
        return {"name": "path", "attributes": converted_attributes}

    arc_match = re.fullmatch(
        rf"M({NUMBER_RE}) ({NUMBER_RE})a({NUMBER_RE}) ({NUMBER_RE})\.?0 1 0 ({NUMBER_RE})-({NUMBER_RE})",
        path,
    )
    if attributes.get("class") == "circle" and arc_match:
        converted_attributes = [
            {
                "name": "d",
                "value": (
                    f"M{format_svg_number(arc_match.group(1))} {format_svg_number(arc_match.group(2))} "
                    f"a{format_svg_number(arc_match.group(3))} {format_svg_number(arc_match.group(4))} "
                    f"0 1 0 {format_svg_number(arc_match.group(5))} -{format_svg_number(arc_match.group(6))}"
                ),
            }
        ]
        for attribute in node.get("attributes", []):
            if attribute["name"] not in {"d", "class"}:
                converted_attributes.append(attribute)
        return {"name": "path", "attributes": converted_attributes}

    absolute_arc_match = re.fullmatch(
        rf"M({NUMBER_RE}) ({NUMBER_RE})A({NUMBER_RE}) ({NUMBER_RE})\.?0 1 0 ({NUMBER_RE}) ({NUMBER_RE})",
        path,
    )
    if attributes.get("class") == "circle" and absolute_arc_match:
        start_x = float(absolute_arc_match.group(1))
        start_y = float(absolute_arc_match.group(2))
        end_x = float(absolute_arc_match.group(5))
        end_y = float(absolute_arc_match.group(6))
        converted_attributes = [
            {
                "name": "d",
                "value": (
                    f"M{format_svg_number(start_x)} {format_svg_number(start_y)} "
                    f"a{format_svg_number(absolute_arc_match.group(3))} "
                    f"{format_svg_number(absolute_arc_match.group(4))} "
                    f"0 1 0 {format_svg_number(end_x - start_x)} {format_svg_number(end_y - start_y)}"
                ),
            }
        ]
        for attribute in node.get("attributes", []):
            if attribute["name"] not in {"d", "class"}:
                converted_attributes.append(attribute)
        return {"name": "path", "attributes": converted_attributes}

    return node


def svg_element_to_json(element: minidom.Element) -> dict[str, Any]:
    """Convert one SVG DOM element to a JSON SVG node."""
    node: dict[str, Any] = {"name": element.tagName}

    attributes = []
    for i in range(element.attributes.length):
        attribute = element.attributes.item(i)
        if attribute.name == "style":
            styles = parse_svg_style_attribute(attribute.value)
            if styles:
                node["styles"] = styles
            continue
        if attribute.name == "xmlns:xlink":
            continue
        if element.tagName == "g" and attribute.name == "class" and attribute.value in {"cells", "grid"}:
            attributes.append({"name": "data-group", "value": attribute.value})
            continue
        if attribute.name in {"class", "data-index"} and element.tagName in {"rect", "text", "g"}:
            continue
        if attribute.name == "class" and element.tagName == "circle" and attribute.value == "circle":
            continue

        attributes.append(
            {
                "name": attribute.name,
                "value": normalize_svg_attribute_value(attribute.name, attribute.value),
            }
        )

    if attributes:
        node["attributes"] = attributes

    if element.tagName == "circle":
        attribute_values = {
            attribute["name"]: attribute["value"]
            for attribute in node.get("attributes", [])
        }
        if attribute_values.get("class") == "tatter" and attribute_values.get("cy") == "11.00":
            for attribute in node["attributes"]:
                if attribute["name"] == "cy":
                    attribute["value"] = "11.10"
                    break

    children = []
    text = []
    for child in element.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            children.append(svg_element_to_json(child))
        elif child.nodeType == child.TEXT_NODE and child.nodeValue:
            content = child.nodeValue.strip()
            if content:
                text.append(content)

    if children:
        node["children"] = children
    if text:
        node["content"] = "".join(text)

    if node["name"] == "path":
        return path_node_to_json(node)

    return node


@dataclass(frozen=True)
class Cell:
    index: int
    row: int
    col: int
    answer: Optional[str]
    label: str = ""
    clue_ids: tuple[int, ...] = ()

    @property
    def is_block(self) -> bool:
        return self.answer is None


@dataclass(frozen=True)
class Clue:
    index: int
    label: str
    direction: Direction
    cells: tuple[int, ...]
    text: str


@dataclass
class Puzzle:
    width: int
    height: int
    cells: list[Cell]
    clues: list[Clue]

    @classmethod
    def from_json_file(cls, path: str | Path) -> "Puzzle":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # The downloaded puzzle format stores the actual puzzle in body[0].
        # This fallback also supports passing a puzzle object directly.
        data = raw["body"][0] if "body" in raw else raw

        width = int(data["dimensions"]["width"])
        height = int(data["dimensions"]["height"])

        clues: list[Clue] = []
        for i, clue in enumerate(data["clues"]):
            text = "".join(piece.get("plain", "") for piece in clue.get("text", []))
            clues.append(
                Clue(
                    index=i,
                    label=str(clue["label"]),
                    direction=str(clue["direction"]),
                    cells=tuple(int(c) for c in clue["cells"]),
                    text=text,
                )
            )

        cells: list[Cell] = []
        for i, cell in enumerate(data["cells"]):
            row, col = divmod(i, width)

            # In this JSON format, black squares are empty dicts.
            if not cell or "answer" not in cell:
                cells.append(Cell(index=i, row=row, col=col, answer=None))
                continue

            cells.append(
                Cell(
                    index=i,
                    row=row,
                    col=col,
                    answer=str(cell["answer"]).upper(),
                    label=str(cell.get("label", "")),
                    clue_ids=tuple(int(c) for c in cell.get("clues", [])),
                )
            )

        if len(cells) != width * height:
            raise ValueError(
                f"Expected {width * height} cells for a {width}x{height} puzzle, "
                f"but found {len(cells)}."
            )

        return cls(width=width, height=height, cells=cells, clues=clues)

    def first_open_cell(self) -> int:
        for cell in self.cells:
            if not cell.is_block:
                return cell.index
        raise ValueError("Puzzle has no playable cells.")

    def clue_for_cell(self, cell_index: int, direction: Direction) -> Optional[Clue]:
        cell = self.cells[cell_index]
        for clue_id in cell.clue_ids:
            clue = self.clues[clue_id]
            if clue.direction == direction:
                return clue
        return None

    def clue_ids_for_direction(self, direction: Direction) -> list[int]:
        return [clue.index for clue in self.clues if clue.direction == direction]


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
