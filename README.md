# growing-score

This tool generates animated MusicXML scores, aligned on MIDI performances.
It is used to generate the scrolling scores of my Instagram account [@le_opiano](https://www.instagram.com/le_opiano).

## Install

```bash
uv sync
```

## Usage

The four commands, in the order of a typical pipeline:

```bash
# 1. Add IDs to the notes of the score
uv run growing-score add-ids score.musicxml

# 2. Align the score with the MIDI performance
uv run growing-score align score_with_ids.musicxml performance.mid

# 3. Render the score to a clean SVG
uv run growing-score musicxml-to-svg score_with_ids.musicxml

# 4. Render the video (3240x1080 with transparent background)
uv run growing-score render-video \
    -s score_with_ids.musicxml \
    -v score_with_ids.svg \
    -a performance.match \
    -m performance.flac \
    -o output.mov \
    -h 1080 \
    -w 3240 \
    -t
```

Refer to the `--help` of each individual command for its specific options.

## Acknowledgments

This project relies on the main following components:
  - Alignment: `DualDTWNoteMatcher` from the library [Parangonar](https://github.com/sildater/parangonar) (see original [paper](https://archives.ismir.net/ismir2023/paper/000075.pdf))
  - Music score manipulation: [Partitura](https://github.com/cpjku/partitura)
  - SVG rendering: [Verovio](https://github.com/rism-digital/verovio)
  - Video rendering: [Manim](https://github.com/ManimCommunity/manim) (or more precisely, a [custom fork](https://github.com/leleogere/manim/tree/support_for_svg_hierarchy) supporting reading SVG `id` and `class` attributes)
