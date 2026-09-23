import click

from growing_score import add_id_to_musicxml, align_score_and_performance, musicxml_to_svg, render_video


@click.group()
def main() -> None:
    """Tools to generate animated MusicXML scores aligned on MIDI performances."""


main.add_command(align_score_and_performance.main, name="align")
main.add_command(add_id_to_musicxml.main, name="add-ids")
main.add_command(musicxml_to_svg.main, name="musicxml-to-svg")
main.add_command(render_video.main, name="render-video")
