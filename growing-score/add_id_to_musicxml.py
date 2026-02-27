from pathlib import Path

import click
from lxml import etree


def add_id_to_notes(tree: etree.ElementTree) -> etree.ElementTree:
    root = tree.getroot()
    id_ = 0
    for note in root.iter("note"):
        # Skip rests (the note contains a <rest> element)
        if note.find("rest") is not None:
            continue
        # Add an incremental ID
        note_id = note.get("id")
        if note_id is None:
            note.set("id", f"n{id_}")
            id_ += 1
    return tree


@click.command("Add IDs to MusicXML notes")
@click.argument("musicxml_file", type=Path)
@click.option("--output_file", "-o", type=Path, default=None, help="Output MusicXML file")
def main(musicxml_file: Path, output_file: Path = None) -> None:
    if output_file is None:
        output_file = musicxml_file.with_stem(f"{musicxml_file.stem}_with_ids")

    tree = etree.parse(musicxml_file)
    tree = add_id_to_notes(tree)
    tree.write(output_file, encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    main()
