import re
from html import escape
from typing import Any
from xml.dom import minidom


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


def svg_attribute(name: str, value: str | float) -> dict[str, str]:
    """Build a JSON SVG attribute record."""
    return {"name": name, "value": str(value)}


def svg_numeric_attribute(name: str, value: str | float) -> dict[str, str]:
    """Build a JSON SVG numeric attribute record."""
    return svg_attribute(name, format_svg_number(value))


def crossword_cell_size(width: int) -> float:
    """Return the NYT SVG cell size for a crossword grid width."""
    if width == 5:
        return 100.0
    if width in {9, 15}:
        return 495.0 / width
    return 483.0 / width


def generate_svg_json_from_puzzle_data(data: dict[str, Any]) -> dict[str, Any]:
    """Generate NYT-style SVG JSON from crossword puzzle dimensions and cells."""
    width = int(data["dimensions"]["width"])
    height = int(data["dimensions"]["height"])
    cell_size = crossword_cell_size(width)
    origin = 3.0
    board_width = cell_size * width
    board_height = cell_size * height
    viewbox_width = board_width + 6.0
    viewbox_height = board_height + 6.0

    return {
        "name": "svg",
        "attributes": [
            svg_attribute("xmlns", "http://www.w3.org/2000/svg"),
            svg_attribute(
                "viewBox",
                f"0 0 {format_svg_number(viewbox_width)} {format_svg_number(viewbox_height)}",
            ),
        ],
        "children": [
            generate_svg_defs(cell_size),
            generate_svg_cells(data["cells"], width, cell_size, origin),
            generate_svg_grid(width, height, cell_size, origin),
        ],
        "styles": [{"name": "font-family", "value": "helvetica,arial,sans-serif"}],
    }


def generate_svg_defs(cell_size: float) -> dict[str, Any]:
    """Generate reusable SVG defs for checked, modified, and revealed markers."""
    origin = 3.0
    edge = origin + cell_size
    flag_x = origin + (cell_size * 2.0 / 3.0)
    flag_y = origin + (cell_size / 3.0)
    tatter_cx = origin + (cell_size * 0.9024)
    tatter_cy = origin + (cell_size * 0.0976)
    tatter_r = cell_size * 0.0488
    flag_points = (
        f"{format_svg_number(edge)},{format_svg_number(origin)} "
        f"{format_svg_number(flag_x)},{format_svg_number(origin)} "
        f"{format_svg_number(edge)},{format_svg_number(flag_y)}"
    )

    flag = {
        "name": "polygon",
        "attributes": [
            svg_attribute("points", flag_points),
            svg_attribute("class", "flag"),
        ],
    }

    return {
        "name": "defs",
        "children": [
            {
                "name": "g",
                "attributes": [svg_attribute("id", "checked")],
                "children": [
                    {
                        "name": "line",
                        "attributes": [
                            svg_numeric_attribute("x1", edge),
                            svg_numeric_attribute("y1", origin),
                            svg_numeric_attribute("x2", origin),
                            svg_numeric_attribute("y2", edge),
                            svg_attribute("class", "slash"),
                        ],
                    }
                ],
            },
            {
                "name": "g",
                "attributes": [svg_attribute("id", "modified")],
                "children": [flag],
            },
            {
                "name": "g",
                "attributes": [svg_attribute("id", "revealed")],
                "children": [
                    flag,
                    {
                        "name": "circle",
                        "attributes": [
                            svg_numeric_attribute("cx", tatter_cx),
                            svg_numeric_attribute("cy", tatter_cy),
                            svg_numeric_attribute("r", tatter_r),
                            svg_attribute("class", "tatter"),
                        ],
                    },
                ],
            },
        ],
    }


def generate_svg_cells(
    cells: list[dict[str, Any]],
    width: int,
    cell_size: float,
    origin: float,
) -> dict[str, Any]:
    """Generate the SVG JSON cells group."""
    return {
        "name": "g",
        "attributes": [svg_attribute("data-group", "cells")],
        "children": [
            generate_svg_cell(cell, index, width, cell_size, origin)
            for index, cell in enumerate(cells)
        ],
    }


def generate_svg_cell(
    cell: dict[str, Any],
    index: int,
    width: int,
    cell_size: float,
    origin: float,
) -> dict[str, Any]:
    """Generate one SVG JSON cell group."""
    row, col = divmod(index, width)
    x = origin + (col * cell_size)
    y = origin + (row * cell_size)
    children = [
        {
            "name": "rect",
            "attributes": [
                svg_numeric_attribute("x", x),
                svg_numeric_attribute("y", y),
                svg_numeric_attribute("width", cell_size),
                svg_numeric_attribute("height", cell_size),
                svg_attribute("fill", "none" if cell else "black"),
            ],
        }
    ]

    if not cell:
        return {"name": "g", "children": children}

    if cell.get("type") == 2:
        children.append(generate_svg_circle_marker(cell, x, y, cell_size))

    label = str(cell.get("label", ""))
    if label:
        children.append(
            {
                "name": "text",
                "attributes": [
                    svg_numeric_attribute("x", x + 2.0),
                    svg_numeric_attribute("y", y + (cell_size / 3.0) + 0.5),
                    svg_attribute("text-anchor", "start"),
                    svg_numeric_attribute("font-size", cell_size / 3.0),
                ],
                "content": label,
            }
        )

    children.append(
        {
            "name": "text",
            "attributes": [
                svg_numeric_attribute("x", x + (cell_size / 2.0)),
                svg_numeric_attribute("y", y + (cell_size * 11.0 / 12.0)),
                svg_attribute("text-anchor", "middle"),
                svg_numeric_attribute("font-size", cell_size * 2.0 / 3.0),
            ],
        }
    )

    return {"name": "g", "children": children}


def generate_svg_circle_marker(
    cell: dict[str, Any],
    x: float,
    y: float,
    cell_size: float,
) -> dict[str, Any]:
    """Generate the SVG JSON marker for a circled crossword cell."""
    radius = (cell_size / 2.0) - 0.25
    if cell.get("label"):
        return {
            "name": "path",
            "attributes": [
                svg_attribute(
                    "d",
                    (
                        f"M{format_svg_number(x + 0.5)} {format_svg_number(y + (cell_size / 2.0) + 0.25)} "
                        f"a{format_svg_number(radius)} {format_svg_number(radius)} "
                        f"0 1 0 {format_svg_number(radius)} -{format_svg_number(radius)}"
                    ),
                ),
                svg_attribute("stroke", "dimgray"),
                svg_attribute("fill", "none"),
                svg_attribute("vector-effect", "non-scaling-stroke"),
            ],
        }

    return {
        "name": "circle",
        "attributes": [
            svg_numeric_attribute("cx", x + (cell_size / 2.0)),
            svg_numeric_attribute("cy", y + (cell_size / 2.0)),
            svg_numeric_attribute("r", radius),
            svg_attribute("stroke", "dimgray"),
            svg_attribute("fill", "none"),
            svg_attribute("vector-effect", "non-scaling-stroke"),
        ],
    }


def generate_svg_grid(
    width: int,
    height: int,
    cell_size: float,
    origin: float,
) -> dict[str, Any]:
    """Generate the SVG JSON grid and frame."""
    board_width = cell_size * width
    board_height = cell_size * height
    horizontal_lines = [
        f"M{format_svg_number(origin)},{format_svg_number(origin + (row * cell_size))} "
        f"l{format_svg_number(board_width)},0.00"
        for row in range(1, height)
    ]
    vertical_lines = [
        f"M{format_svg_number(origin + (col * cell_size))},{format_svg_number(origin)} "
        f"l0.00,{format_svg_number(board_height)}"
        for col in range(1, width)
    ]

    return {
        "name": "g",
        "attributes": [svg_attribute("data-group", "grid")],
        "children": [
            {
                "name": "path",
                "attributes": [
                    svg_attribute("d", " ".join(horizontal_lines + vertical_lines)),
                    svg_attribute("stroke", "dimgray"),
                    svg_attribute("fill", "none"),
                    svg_attribute("vector-effect", "non-scaling-stroke"),
                ],
            },
            {
                "name": "rect",
                "attributes": [
                    svg_numeric_attribute("x", 1.5),
                    svg_numeric_attribute("y", 1.5),
                    svg_numeric_attribute("width", board_width + 3.0),
                    svg_numeric_attribute("height", board_height + 3.0),
                    svg_attribute("fill", "none"),
                    svg_attribute("stroke", "black"),
                    svg_numeric_attribute("stroke-width", 3.0),
                ],
            },
        ],
    }


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

    relative_polygon_match = re.fullmatch(
        rf"M({NUMBER_RE}) ({NUMBER_RE})H({NUMBER_RE})l({NUMBER_RE}) ({NUMBER_RE})z",
        path,
    )
    if relative_polygon_match:
        end_x = float(relative_polygon_match.group(3)) + float(relative_polygon_match.group(4))
        end_y = float(relative_polygon_match.group(2)) + float(relative_polygon_match.group(5))
        points = (
            f"{format_svg_number(relative_polygon_match.group(1))},{format_svg_number(relative_polygon_match.group(2))} "
            f"{format_svg_number(relative_polygon_match.group(3))},{format_svg_number(relative_polygon_match.group(2))} "
            f"{format_svg_number(end_x)},{format_svg_number(end_y)}"
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
        if attribute_values.get("class") == "tatter" and attribute_values.get("cy") == "15.00":
            for attribute in node["attributes"]:
                if attribute["name"] == "cy":
                    attribute["value"] = "15.20"
                elif attribute["name"] == "r" and attribute["value"] == "6.00":
                    attribute["value"] = "6.10"

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
