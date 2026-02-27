import subprocess
from pathlib import Path

import click
import lxml
import verovio
from click import command
from lxml import etree


def musicxml_to_svg(
    musicxml_file: Path, output_file: Path | None = None
) -> lxml.etree._ElementTree | None:
    tk = verovio.toolkit()
    options = {
        "pageHeight": 100,
        "pageWidth": 100000,
        "scale": 100,
        "adjustPageWidth": "true",
        "adjustPageHeight": "true",
        "breaks": "none",
        "footer": "none",
        "header": "none",
        "pageMarginBottom": 0,
        "pageMarginLeft": 0,
        "pageMarginRight": 0,
        "pageMarginTop": 0,
        "svgRemoveXlink": True,
    }
    tk.setOptions(options)
    tk.loadFile(str(musicxml_file))
    tk.redoLayout()
    if output_file is not None:
        tk.renderToSVGFile(output_file.as_posix(), 1)
    else:
        svg_str = tk.renderToSVG(1)
        # Parse string into XML tree
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(svg_str, parser).getroottree()
        return tree


def expand_svg_use_tags(tree: lxml.etree.ElementTree) -> lxml.etree.ElementTree:
    ns = {"svg": "http://www.w3.org/2000/svg", "xlink": "http://www.w3.org/1999/xlink"}
    root = tree.getroot()

    # Get all symbols
    symbols = {sym.attrib["id"]: sym[0] for sym in root.findall(".//svg:defs/svg:g", namespaces=ns)}

    # Find all use elements
    for use in root.findall(".//svg:use", namespaces=ns):
        # Get the reference to the symbol
        href = use.attrib.get(f'{{{ns["xlink"]}}}href') or use.attrib.get("href")
        if not href or not href.startswith("#"):
            continue
        sym_id = href[1:]
        symbol = symbols.get(sym_id)
        if symbol is None:
            continue

        # Clone the path
        new_path = etree.Element(f"{{{ns['svg']}}}path", nsmap=ns)
        for k, v in symbol.attrib.items():
            new_path.attrib[k] = v

        # Compose transform from x, y, width, height
        x = float(use.attrib.get("x", "0"))
        y = float(use.attrib.get("y", "0"))
        width = use.attrib.get("width")
        height = use.attrib.get("height")

        # Calculate scale factors if width and height exist
        scale_x = scale_y = 1
        viewBox = symbol.attrib.get("viewBox")
        if viewBox and width and height:
            _, _, vb_w, vb_h = map(float, viewBox.split())
            scale_x = float(width.replace("px", "")) / vb_w
            scale_y = float(height.replace("px", "")) / vb_h

        # Extract symbol transform if any
        symbol_transform = symbol.attrib.get("transform", "")

        # Compose transforms from use element
        transforms = []

        # Add use translation
        if x != 0 or y != 0:
            transforms.append(f"translate({x},{y})")

        # Add use scale
        if scale_x != 1 or scale_y != 1:
            transforms.append(f"scale({scale_x},{scale_y})")

        # Add symbol's own transform last (so it applies before use transforms)
        if symbol_transform:
            transforms.append(symbol_transform)

        existing_transform = use.attrib.get("transform", "")
        combined = " ".join(transforms)
        new_path.attrib["transform"] = f"{existing_transform} {combined}".strip()

        # Replace the use element with the new path
        parent = use.getparent()
        if parent is not None:
            parent.replace(use, new_path)

    return tree


def musicxml_to_clean_svg_old(musicxml_file: Path, output_file: Path) -> None:
    svg = musicxml_to_svg(musicxml_file)
    # svg.write("/tmp/debug.svg", pretty_print=True, xml_declaration=True, encoding="UTF-8")
    svg = expand_svg_use_tags(svg)
    svg.write(output_file, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    # # Open in meld to compare
    # import subprocess
    #
    # subprocess.run(["meld", "/tmp/debug.svg", output_file], check=True)


def musicxml_to_clean_svg(musicxml_file: Path, output_file: Path) -> None:
    musicxml_to_svg(musicxml_file, output_file)
    command = [
        "inkscape",
        "--actions=select-all;object-to-path",
        "--vacuum-defs",
        "-o",
        output_file.as_posix(),
        output_file.as_posix(),
    ]
    print(f"Running command: {' '.join(command)}")
    subprocess.run(command)


@click.command("MusicXML to SVG")
@click.argument("musicxml_file", type=Path)
@click.option("--output_file", "-o", type=Path, default=None, help="Output SVG file")
def main(musicxml_file: Path, output_file: Path = None) -> None:
    if output_file is None:
        output_file = musicxml_file.with_suffix(".svg")
        print(output_file.as_posix())
    musicxml_to_clean_svg(musicxml_file, output_file)


if __name__ == "__main__":
    main()
