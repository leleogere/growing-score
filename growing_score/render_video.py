import itertools
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import click
import numpy as np
import svgelements as se
import partitura as pt
import partitura.score
import partitura.performance
from scipy.interpolate import *

from manim import *
from scipy.optimize import brentq


def get_svg_width_and_height(svg_path: Path):
    """
    Get the width and height of an SVG file.
    :param svg_path: Path to the SVG file.
    :return: Tuple of (width, height).
    """
    svg = se.SVG.parse(svg_path)
    return svg.width, svg.height


class MusicSVG(SVGMobject):
    def __init__(self, svg_path: Path, stroke_width_factor: float = 1.0):
        super().__init__(
            svg_path, height=None, width=None, use_svg_cache=False, unpack_groups=False
        )

        # Fix the stroke width as they are too small (1 stroke_width unit = 1/100 of a frame unit)
        for index, element in enumerate(self.get_family()):
            if element.stroke_width is not None:
                element.stroke_width *= 100 * stroke_width_factor

        pass

    @classmethod
    def find_recursively(cls, mobject_list: list[Mobject], filter: Callable[[Mobject], bool]):
        """
        Find all submobjects that match the filter function.
        :param filter: A function that takes a Mobject and returns True if it matches the filter.
        :return: A list of matching Mobjects.
        """
        result = []
        for mobject in mobject_list:
            if filter(mobject):
                result.append(mobject)
            if hasattr(mobject, "submobjects"):
                result.extend(cls.find_recursively(mobject.submobjects, filter))
        return result

    def get_notes(self):
        """
        Get all notes in the SVG.
        :return: A list of notes.
        """
        return self.get_by_class("note", error_on_not_found=False) + self.get_by_class(
            "chord", error_on_not_found=False
        )

    def get_rests(self):
        """
        Get all rests in the SVG.
        :return: A list of rests.
        """
        return self.get_by_class("rest", error_on_not_found=False) + self.get_by_class(
            "mRest", error_on_not_found=False
        )

    def flat_submobjects(self):
        """
        Get all submobjects of the SVG.
        :return: A list of submobjects.
        """
        return self.find_recursively(self.submobjects, lambda x: not isinstance(x, VGroup))


def get_note_head(note: VGroup):
    assert "note" in note.svg_classes
    notehead = next(filter(lambda x: "notehead" in x.svg_classes, note.submobjects))
    return notehead


@dataclass
class AlignedNote:
    score_id: str
    performance_id: str
    score: pt.score.Part = None
    performance: pt.performance.PerformedPart = None
    svg: MusicSVG = None

    @property
    def svg_note(self) -> Mobject:
        return self.svg.get_by_id(self.score_id)

    @property
    def svg_note_x(self) -> float:
        return float(get_note_head(self.svg_note).get_center()[0])

    @property
    def score_note(self) -> pt.score.Note:
        return self.score.notes[int(self.score_id[1:])]

    @property
    def performance_note(self) -> pt.performance.PerformedNote:
        return self.performance.notes[int(self.performance_id[1:])]

    @property
    def performance_time(self) -> float:
        return self.performance_note.pnote_dict["note_on"]


@dataclass
class Alignment:
    score: pt.score.Part
    performance: pt.performance.PerformedPart
    svg: MusicSVG
    alignment: list[dict[str, str]]

    def __post_init__(self):
        # Build aligned notes list
        self.aligned_notes = [
            AlignedNote(
                score_id=d["score_id"],
                performance_id=d["performance_id"],
                score=self.score,
                performance=self.performance,
                svg=self.svg,
            )
            for d in self.alignment
            if d["label"] == "match"
        ]
        self.aligned_notes.sort(key=lambda x: (x.svg_note_x, x.performance_time))

        # Check that strictly increasing performance times
        if not all(
            t1 < t2
            for (_, t1), (_, t2) in itertools.pairwise(
                [(n.svg_note_x, n.performance_time) for n in self.aligned_notes]
            )
        ):
            print(
                "Warning: Performance times are not strictly increasing, discarding pairs with non-increasing "
                "performance time."
            )
            last_ptime = 0
            to_remove = []
            for n in self.aligned_notes:
                if n.performance_time <= last_ptime:
                    to_remove.append(n)
                else:
                    last_ptime = n.performance_time
            self.aligned_notes = [n for n in self.aligned_notes if n not in to_remove]

        # Build dictionaries of IDs for fast access
        self._sid_to_note = {n.score_id for n in self.aligned_notes}
        self._pid_to_note = {n.performance_id for n in self.aligned_notes}

        # Build interpolation functions
        self._note_position_and_performance_time_keyframes = [
            (x_pos, float(np.median([n.performance_time for n in notes])))
            for x_pos, notes in itertools.groupby(
                self.aligned_notes,
                key=lambda n: n.svg_note_x,
            )
        ]
        # Remove non strictly increasing performance times
        self._note_position_and_performance_time_keyframes = [
            (x, t1)
            for (x, t1), (_, t2) in itertools.pairwise(
                self._note_position_and_performance_time_keyframes
            )
            if t1 < t2
        ]
        # Create the individual keyframes for the interpolation functions
        self._score_position_keyframes, self._performance_time_keyframes = zip(
            *self._note_position_and_performance_time_keyframes
        )
        # Create the interpolation functions
        self.score_position_to_performance_time_fn = LinearExtrapolatedPchipInterpolator(
            x=self._score_position_keyframes,
            y=self._performance_time_keyframes,
        )
        self.performance_time_to_score_position_fn = LinearExtrapolatedPchipInterpolator(
            x=self._performance_time_keyframes,
            y=self._score_position_keyframes,
        )
        self.performance_time_to_score_position_smooth_fn = make_smoothing_spline(
            x=self._performance_time_keyframes,
            y=self._score_position_keyframes,
            lam=1000,
        )

    def score_ids(self) -> list[str]:
        return [n.score_id for n in self.aligned_notes]

    def performance_ids(self) -> list[str]:
        return [n.performance_id for n in self.aligned_notes]

    def performance_times(self) -> list[float]:
        return [n.performance_time for n in self.aligned_notes]

    def svg_note_xs(self) -> list[float]:
        return [n.svg_note_x for n in self.aligned_notes]

    def get_from_score_id(self, score_id: str) -> AlignedNote | None:
        if score_id in self._sid_to_note:
            return next(n for n in self.aligned_notes if n.score_id == score_id)
        return None

    def get_from_performance_id(self, performance_id: str) -> AlignedNote | None:
        if performance_id in self._pid_to_note:
            return next(n for n in self.aligned_notes if n.performance_id == performance_id)
        return None

    @property
    def _debug_dataframe(self):
        import pandas as pd

        return pd.DataFrame(
            {
                "score_id": [n.score_id for n in self.aligned_notes],
                "performance_id": [n.performance_id for n in self.aligned_notes],
                "performance_note": [n.performance_note for n in self.aligned_notes],
                "performance_time": [n.performance_time for n in self.aligned_notes],
                "score_note": [n.score_note for n in self.aligned_notes],
                "svg_note": [n.svg_note for n in self.aligned_notes],
                "svg_x": [n.svg_note_x for n in self.aligned_notes],
            }
        )

    def plot_interpolation_functions(self, orient: Literal["p2s", "s2p"]):
        import matplotlib.pyplot as plt

        if orient == "s2p":
            x = np.linspace(
                min(self._score_position_keyframes) - 1000,
                max(self._score_position_keyframes) + 1000,
                1000,
            )
            y = self.score_position_to_performance_time_fn(x)
            plt.plot(
                self._score_position_keyframes,
                self._performance_time_keyframes,
                "x",
                label="Keyframes",
                zorder=1,
            )
            plt.plot(x, y, label="Interpolation function", zorder=2)
            plt.xlabel("Score position (x)")
            plt.ylabel("Performance time (s)")
        elif orient == "p2s":
            x = np.linspace(
                min(self._performance_time_keyframes) - 5,
                max(self._performance_time_keyframes) + 5,
                1000,
            )
            y = self.performance_time_to_score_position_fn(x)
            y2 = self.performance_time_to_score_position_smooth_fn(x)
            plt.plot(
                self._performance_time_keyframes,
                self._score_position_keyframes,
                "x",
                label="Keyframes",
                zorder=1,
            )
            plt.plot(x, y, label="Interpolation function", zorder=2)
            plt.plot(x, y2, label="Interpolation function smooth", zorder=3)
            plt.xlabel("Performance time (s)")
            plt.ylabel("Score position (x)")
        plt.legend()
        plt.show()


class LinearExtrapolatedPchipInterpolator:
    def __init__(self, x, y):
        self.pchip = PchipInterpolator(x, y, extrapolate=False)
        self.x = np.asarray(x)
        self.y = np.asarray(y)
        self.slope_lo = self.pchip.derivative()(x[0])
        self.slope_hi = self.pchip.derivative()(x[-1])

    def __call__(self, x_new):
        x_new = np.asarray(x_new)
        y_new = np.empty_like(x_new, dtype=float)

        mask_lo = x_new < self.x[0]
        mask_hi = x_new > self.x[-1]
        mask_in = ~mask_lo & ~mask_hi

        y_new[mask_in] = self.pchip(x_new[mask_in])
        y_new[mask_lo] = self.y[0] + self.slope_lo * (x_new[mask_lo] - self.x[0])
        y_new[mask_hi] = self.y[-1] + self.slope_hi * (x_new[mask_hi] - self.x[-1])

        return y_new


def get_smooth_function(
    s: np.typing.ArrayLike,
    p: float = 0.5,
) -> Callable[[np.typing.ArrayLike], np.typing.ArrayLike]:
    """https://math.stackex change.com/a/4800509"""
    c = (1 - s) / (s - 3)

    def f(t: np.typing.ArrayLike) -> np.typing.ArrayLike:
        t = np.clip(t, 0, 1)
        return np.where(
            t < p,
            t * (t * (1 + c) / (t + p * c)) ** 2,
            1 - (1 - t) * ((1 - t) * (1 + c) / ((1 - t) + (1 - p) * c)) ** 2,
        )

    return f


def prepare_scene(
    svg_path: Path,
    alignment: Alignment,
    sound_path: Path | None = None,
    end: float | None = None,
) -> Scene:
    class ScoreFollowingScene(MovingCameraScene):
        def construct(self):
            # Add the camera to the scene
            self.add(self.camera.frame)

            # Read the SVG file and place it left edge to the center of the camera
            svg = MusicSVG(svg_path, stroke_width_factor=1.5)
            # svg.move_to(self.camera.frame.get_center(), aligned_edge=LEFT)

            # Gather all global score layout
            layout = []
            # Label (instrument)
            # layout.extend(svg.get_by_class("label", error_on_not_found=False))
            # System
            layout.extend(svg.get_by_class("grpSym", error_on_not_found=False))
            # First barline
            layout.extend(
                next(
                    path
                    for path in svg.get_by_class("system")[0]
                    if isinstance(path, VMobjectFromSVGPath)
                )
            )
            # Other barlines
            layout.extend(svg.get_by_class("barLine"))
            # Staff lines (only keep the ones in the 1st bar and extend them to the end)
            staffs = svg.get_by_class("staff")
            staff_lines = [
                element
                for staff in staffs
                for element in staff
                if isinstance(element, VMobjectFromSVGPath)
            ]
            single_staff_lines = staff_lines[:10]
            right_x = staff_lines[-1].get_right()[0]
            left_x = staff_lines[0].get_left()[0]
            for line in single_staff_lines:
                line.stretch_to_fit_width(right_x - left_x, about_point=line.get_left())
            layout.extend(single_staff_lines)
            # Octave lines
            # octaves = svg.get_by_class("octave")
            # for octave in octaves:
            #     octave[1] = DashedLine(octave[1].get_left(), octave[1].get_right(), dash_length=0.05, dashed_ratio=0.5)
            # First clefs
            clefs = svg.get_by_class("clef")
            layout.extend(clefs[:2])
            # Time signature
            ts = svg.get_by_class("meterSig")
            layout.extend(ts[:2])
            # Key signature
            ks = svg.get_by_class("keySig", error_on_not_found=False)
            layout.extend(ks[:2])
            # Combine all
            layout = VGroup(*layout)

            # Gather all elements to be animated
            animated_elements = {
                "notes": svg.get_by_class("note", error_on_not_found=False),
                "chords_elements": [
                    element
                    for chord in svg.get_by_class("chord", error_on_not_found=False)
                    for element in chord.submobjects
                    if "note" not in element.svg_classes  # notes already handled above
                ],
                "rests": svg.get_by_class("rest", error_on_not_found=False),
                "mRests": svg.get_by_class("mRest", error_on_not_found=False),
                "ties": svg.get_by_class("tie", error_on_not_found=False),
                "trills": svg.get_by_class("trill", error_on_not_found=False),
                "clefs": clefs[2:],
                "keySigs": ks[2:],
                "timeSigs": ts[2:],
                "ledgerLines": sum(
                    [
                        group.submobjects
                        for cls in ["ledgerLines below", "ledgerLines above", "ledgerLines"]
                        for group in svg.get_by_class(cls, error_on_not_found=False)
                    ],
                    [],
                ),
                "beams": [
                    obj
                    for group in svg.get_by_class("beam", error_on_not_found=False)
                    for obj in group
                    if obj.svg_id.startswith("polygon")
                ]
                + svg.get_by_class("beamSpan", error_on_not_found=False),
                "tupletBrackets": svg.get_by_class("tupletBracket", error_on_not_found=False),
                "tupletNums": svg.get_by_class("tupletNum", error_on_not_found=False),
                "hairpins": svg.get_by_class("hairpin", error_on_not_found=False),
                "dynamics": svg.get_by_class("dynam", error_on_not_found=False),
                "arpegios": svg.get_by_class("arpeg", error_on_not_found=False),
                "slurs": svg.get_by_class("slur", error_on_not_found=False),
                "directions": svg.get_by_class("dir", error_on_not_found=False),
                "fermatas": svg.get_by_class("fermata", error_on_not_found=False),
                "octaves": svg.get_by_class("octave", error_on_not_found=False),
            }
            # breakpoint()

            # Try to find the first point the SVG is out of frame at start
            try:
                start_time = brentq(
                    lambda t: alignment.performance_time_to_score_position_smooth_fn(t)
                    - svg.get_left()[0]
                    + config.frame_width / 2,
                    -30,  # Search between -30s
                    0,  # and 0s
                )
            except ValueError:
                start_time = -10  # If no start time found, start at -10 seconds

            # Setup end time
            if end is None:
                end_time = max([n.performance_time for n in alignment.aligned_notes])
                # Try to find the last point the SVG is out of frame at the end
                try:
                    end_time = brentq(
                        lambda t: alignment.performance_time_to_score_position_smooth_fn(t)
                        - svg.get_right()[0]
                        + config.frame_width / 2,
                        end_time,  # Search between the end
                        end_time + 30,  # and 30s after the end
                    )
                except ValueError:
                    end_time = end_time + 10  # If no start time found, start at -10 seconds
            else:
                end_time = end
            print(f"Time: {start_time} to {end_time} ({end_time - start_time} seconds)")

            # Setup the time tracker that will control the animations
            time = ValueTracker(start_time)

            # Setup the animation of all animated objects
            # The animation lasts twice the "temporal width" of the object (minimum 0.2s)
            # Animation delayed by the time it takes the object to reach the correct spot on screen
            min_duration = 0.2
            max_duration = 3
            for type_, objs in animated_elements.items():
                for obj in objs:
                    # Different animation for notes, as alterations change the width of the object
                    if type_ == "notes":
                        notehead = get_note_head(obj)
                        left = notehead.get_left()[0]
                        right = notehead.get_right()[0]
                    else:
                        left: float = obj.get_left()[0]
                        right: float = obj.get_right()[0]
                    # Compute the temporal difference
                    time_left = alignment.score_position_to_performance_time_fn(left)
                    time_right = alignment.score_position_to_performance_time_fn(right)
                    time_diff = float(time_right - time_left)
                    proportion_before = 1.5
                    run_time = min(max(time_diff * proportion_before, min_duration), max_duration)
                    # Add the updater, starting after the object is in the correct spot
                    turn_animation_into_updater(
                        FadeIn(obj, shift=DOWN * 5, run_time=run_time),
                        delay=time_left - run_time - start_time,
                    )
                    # The updater will:
                    #   - make the object k starts to appear at ~tk
                    #   - make the object apparition last util the end of the object is reached
                    # Actually, the object does not start at tk, but a bit before tk, controlled by `proportion_before`.
                    # That ensures that the object has started to apprear when it is played, and makes it easier for the
                    # viewer to follow along. The apparition still end at the end of the object.

            # Setup the camera updater
            def camera_updater(mob: Mobject):
                t = time.get_value()
                new_pos = alignment.performance_time_to_score_position_smooth_fn(t)
                mob.set_x(new_pos - 200)  # Shift a bit the camera to the left for larger view

            self.camera.frame.add_updater(camera_updater)

            # Add elements to the scene
            self.add(layout)
            self.add(
                *[obj for objs in animated_elements.values() for obj in objs]
            )  # If not added creation updaters do not work

            # Add the background music
            if sound_path is not None:
                self.add_sound(str(sound_path), time_offset=-start_time)

            # Animate the time tracker
            self.play(
                time.animate.set_value(end_time),
                # rate_func=get_smooth_function(s=1.05),
                rate_func=linear,
                run_time=end_time - start_time,
            )

            # Wait a bit before ending the scene
            # self.wait(5)

    return ScoreFollowingScene()


def render_video(
    score_path: Path,
    svg_path: Path,
    alignment_path: Path,
    sound_path: Path | None = None,
    output_path: Path | None = None,
    frame_rate: int = 30,
    height: int = 1080,
    width: int = 3240,
    transparent: bool = False,
    end: float | None = None,
) -> None:
    if output_path is None:
        output_path = score_path.with_suffix(".mp4" if not transparent else ".mov")

    # Fix the aspect ratio of the actual frame size in pixels
    if height % 2 != 0:  # FFMPEG does not like odd dimensions
        height += 1
    if width % 2 != 0:
        width += 1

    # Get aspect ratio of SVG
    svg_width, svg_height = get_svg_width_and_height(svg_path)

    # Set up the frame size to fit the SVG
    aspect_ratio = width / height
    frame_height = int(svg_height) * 1.1  # Add a bit of margin
    frame_width = int(frame_height * aspect_ratio)

    print(f"{height = }")
    print(f"{width = }")
    print(f"{frame_height = }")
    print(f"{frame_width = }")

    # Load score
    score = pt.load_musicxml(score_path)
    assert len(score.parts) == 1
    score = score.parts[0]

    # Load SVG
    svg = MusicSVG(svg_path)

    # Load performance and alignment
    performance, alignment = pt.load_match(alignment_path)
    assert len(performance) == 1
    performance = performance[0]
    alignment = Alignment(score=score, performance=performance, svg=svg, alignment=alignment)
    # alignment.plot_interpolation_functions("p2s")
    # alignment.plot_interpolation_functions("s2p")
    # exit(0)

    # Render the scene
    with tempconfig(
        {
            "preview": True,
            "transparent": transparent,
            "background_opacity": int(transparent),
            "output_file": str(output_path),
            "pixel_height": height,
            "pixel_width": width,
            "frame_height": frame_height,
            "frame_width": frame_width,
            "frame_rate": frame_rate,
            "background_color": WHITE,
            # "disable_caching": True,
        }
    ):
        # Default colors
        VMobject.set_default(fill_color=BLACK, stroke_color=BLACK)
        scene = prepare_scene(
            svg_path=svg_path,
            alignment=alignment,
            sound_path=sound_path,
            end=end,
        )
        scene.render()


# fmt: off
@click.command("Render video")
@click.option("--score_path", "-s", type=Path, required=True, help="Path to the score MusicXML file")
@click.option("--svg_path", "-v", type=Path, required=True, help="Path to the SVG file")
@click.option("--alignment_path", "-a", type=Path, required=True, help="Path to the alignment file")
@click.option("--sound_path", "-m", type=Path, default=None, help="Path to the sound file")
@click.option("--output_path", "-o", type=Path, default=None, help="Path to the output video file")
@click.option("--frame_rate", "-f", type=int, default=30, help="Frame rate of the video")
@click.option("--height", "-h", type=int, default=1080, help="Height, in pixels, of the video")
@click.option("--width", "-w", type=int, default=3240, help="Width, in pixels, of the video")
@click.option("--transparent", "-t", is_flag=True, default=False, help="Render video with transparent background")
@click.option("--end", "-e", type=float, default=None, help="End time of the video")
# fmt: on
def main(
    score_path: Path,
    svg_path: Path,
    alignment_path: Path,
    sound_path: Path | None = None,
    output_path: Path | None = None,
    frame_rate: int = 30,
    height: int = 1080,
    width: int = 3240,
    transparent: bool = False,
    end: float | None = None,
) -> None:
    """Render an animated video of the aligned score."""
    render_video(
        score_path=score_path,
        svg_path=svg_path,
        alignment_path=alignment_path,
        sound_path=sound_path,
        output_path=output_path,
        frame_rate=frame_rate,
        height=height,
        width=width,
        transparent=transparent,
        end=end,
    )


if __name__ == "__main__":
    main()
