from pathlib import Path

import click
import parangonar as pa
import partitura as pt


def align_score_and_performance(score_path: Path, performance_path: Path, output_path: Path | None = None) -> None:
    if output_path is None:
        output_path = performance_path.with_suffix(".match")

    score = pt.load_musicxml(score_path, force_note_ids="keep")
    performance = pt.load_performance_midi(performance_path)

    score_note_array = score.note_array(include_grace_notes=True)
    performance_note_array = performance.note_array()

    matcher = pa.DualDTWNoteMatcher()
    alignment = matcher(score_note_array, performance_note_array, process_ornaments=True, score_part=score.parts[0])
    # pa.plot_alignment(performance_note_array, score_note_array, alignment)

    pt.save_match(
        alignment=alignment,
        performance_data=performance,
        score_data=score,
        ppq=performance[0].ppq,
        mpq=performance[0].mpq,
        out=output_path,
        assume_unfolded=True,  # Avoid adding suffix to note IDs
    )


@click.command("Align score and performance")
@click.argument("score_path", type=Path)
@click.argument("performance_path", type=Path)
@click.option("--output_path", "-o", type=Path, default=None, help="Output match file")
def main(score_path: Path, performance_path: Path, output_path: Path = None) -> None:
    align_score_and_performance(score_path, performance_path, output_path)


if __name__ == "__main__":
    main()