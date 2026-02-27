from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Callable

import svgelements as se

from manim import *

# path = Path("/home/leo/Documents/LiveNotes/data/2024-11-03_18-35-05_2737-notes_629-seconds_3measures_as_paths.svg")
# path = Path("/home/leo/Documents/LiveNotes/data/2024-11-03_18-35-05_2737-notes_629-seconds_4m.svg")
# path = Path("/home/leo/Documents/LiveNotes/data/2024-11-03_18-35-05_2737-notes_629-seconds_short_5m.svg")
# path = Path("/home/leo/Documents/LiveNotes/data/2024-11-03_18-35-05_2737-notes_629-seconds_20m.svg")
# path = Path("/home/leo/Documents/LiveNotes/data/2024-11-03_18-35-05_2737-notes_629-seconds_short_15m.svg")
path = Path("/home/leo/Documents/LiveNotes/data/xml_score.svg")
# path = Path("/home/leo/Documents/LiveNotes/data/2024-11-03_18-35-05_2737-notes_629-seconds_short.svg")
# path = Path("/home/leo/Documents/LiveNotes/data/2024-11-03_18-35-05_2737-notes_629-seconds_short_as_paths.svg")


def get_svg_width_and_height(svg_path: Path):
    """
    Get the width and height of an SVG file.
    :param svg_path: Path to the SVG file.
    :return: Tuple of (width, height).
    """
    svg = se.SVG.parse(svg_path)
    return svg.width, svg.height


# Get apsect ratio of SVG
width, height = get_svg_width_and_height(path)
frame_ratio = height / width

# Set up the frame size to fit the SVG
config.frame_height = int(height)
config.frame_width = 3 * config.frame_height

# Fix the aspect ratio of the actual frame size in pixels
config.pixel_width = int(3 * config.pixel_height)
# config.pixel_height = int(frame_ratio * config.pixel_width)
if config.pixel_width % 2 != 0:  # FFMPEG does not like odd dimensions
    config.pixel_width += 1

print(f"{config.pixel_height = }")
print(f"{config.pixel_width = }")
print(f"{config.frame_height = }")
print(f"{config.frame_width = }")

# White background
config.background_color = WHITE
VMobject.set_default(fill_color=BLACK, stroke_color=BLACK)


class MusicSVG(SVGMobject):
    def __init__(self, svg_path: Path):
        super().__init__(svg_path, height=None, width=None, use_svg_cache=False, unpack_groups=False)

        # Fix the stroke width as they are too small (1 stroke_width unit = 1/100 of a frame unit)
        for index, element in enumerate(self.get_family()):
            if element.stroke_width is not None:
                element.stroke_width *= 100

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
        return self.get_by_class("note") + self.get_by_class("chord")

    def get_rests(self):
        """
        Get all rests in the SVG.
        :return: A list of rests.
        """
        return self.get_by_class("rest") + self.get_by_class("mRest")


    def flat_submobjects(self):
        """
        Get all submobjects of the SVG.
        :return: A list of submobjects.
        """
        return self.find_recursively(self.submobjects, lambda x: not isinstance(x, VGroup))



class ColoredScore(Scene):

    # Taken from https://github.com/abul4fia/manim-play-timeline
    def play_timeline(self, timeline: dict[float, Iterable[Animation] | Animation]):
        """
        Plays a timeline of animations on a given scene.
        Args:
            timeline (dict): A dictionary where the keys are the times at which the animations should start,
                and the values are the animations to play at that time. The values can be a single animation
                or an iterable of animations.

        Notes:
            Each animation in the timeline can have a different duration, so several animations can be
            running in parallel. If the value for a given time is an iterable, all the animations
            in the iterable are started at once (although they can end at different times depending
            on their run_time)
            The method returns when all animations have finished playing.
        Returns:
            None
        """
        previous_t = 0
        ending_time = 0
        for t, anims in sorted(timeline.items()):
            to_wait = t - previous_t
            if to_wait > 0:
                self.wait(to_wait)
            previous_t = t
            if not isinstance(anims, Iterable):
                anims = [anims]
            for anim in anims:
                turn_animation_into_updater(anim)
                self.add(anim.mobject)
                ending_time = max(ending_time, t + anim.run_time)
        if ending_time > t:
            self.wait(ending_time - t)

    def construct(self):
        # svg = SVGMobject(str(path), width=None, use_svg_cache=False)#, stroke_width=0.5)
        # svg = SVGMobject(str(path), width=None, use_svg_cache=False, stroke_width=0.0)
        svg = MusicSVG(path)
        # svg.scale_to_fit_width(4, scale_stroke=True)
        # svg.stroke_width = 1005

        # for subobject in svg.submobjects[::10]:
        #     subobject.color = RED

        for (cls, color) in [
            (("note", "chord"), RED),
            (("rest", "mRest"), GREEN),
            (("clef",), BLUE),
            (("meterSig",), ORANGE),
            (("keySig",), PURPLE),
            (("tie",), YELLOW),
        ]:
            for c in cls:
                try:
                    for x in svg.get_by_class(c):
                        x.set_color(color)
                except KeyError:
                    pass

        print(len(svg.submobjects))
        # svg.submobjects[10].set_style(fill_color=RED, stroke_color=RED)
        # indices = index_labels(svg, label_height=0.05, background_stroke_width=0.8)

        # SIMPLE LAG START BY LEFT SORTING
        # sorted_submobjects = sorted(
        #     svg.submobjects,
        #     key=lambda x: x.get_left()[0],
        # )
        # self.play(
        #     # LaggedStart(Create(subitem) for subitem in sorted_submobjects),
        #     LaggedStart(DrawBorderThenFill(subitem, stroke_width=100) for subitem in sorted_submobjects),
        #     # LaggedStart(FadeIn(subitem) for subitem in sorted_submobjects),
        #     # svg.animate.shift(LEFT * 5),
        #     run_time=10,
        # )


        # MORE COMPLEX WITH SIMULTANEOUS XPOS
        submobject_by_xposition = defaultdict(list)
        for subobject in svg.flat_submobjects():
            submobject_by_xposition[subobject.get_left()[0]].append(subobject)
        submobject_by_xposition = dict(sorted(submobject_by_xposition.items()))
        # self.play(
        #     LaggedStartMap(
        #         DrawBorderThenFill(VGroup(subitems), stroke_width=100) for subitems in submobject_by_xposition.values()
        #     ),
        #     # LaggedStart(FadeIn(subitem) for subitem in sorted_submobjects),
        #     # svg.animate.shift(LEFT * 5),
        #     run_time=10,
        # )


        # EVEN MORE COMPLEX WITH A TIME MAPPING ON X POSITION
        total_time = 10
        time_factor = total_time / width
        # times = [t - min(submobject_by_xposition.keys()) for t in submobject_by_xposition.keys()]
        time_to_group = {
            t - min(submobject_by_xposition.keys()): VGroup(subitems)
            for t, subitems in submobject_by_xposition.items()
        }
        print(time_factor)
        for time, group in time_to_group.items():
            self.add(group)
            turn_animation_into_updater(
                # AnimationGroup(DrawBorderThenFill(subobjets, stroke_width=100, run_time=0.5)),
                DrawBorderThenFill(group, stroke_width=100, run_time=1.0),
                delay=time * time_factor,
            )
        self.wait(total_time + 2)

        # TRY WITH PLAY TIMELINE
        # total_time = 20
        # time_factor = total_time / width
        # time_to_group: dict[float, VGroup] = {
        #     (t - min(submobject_by_xposition.keys())) * time_factor: VGroup(subitems)
        #     for t, subitems in submobject_by_xposition.items()
        # }
        # self.play_timeline({
        #     t: DrawBorderThenFill(group, stroke_width=100, run_time=1.0)
        #     for t, group in time_to_group.items()
        # })

        # self.add_sound()


        # self.add(svg)

        measures = svg.get_by_class("measure")
        for measure in measures:
            self.play(Wiggle(measure))

        layers = svg.get_by_class("layer")
        for layer in layers:
            self.play(
                AnimationGroup(Wiggle(element) for element in layer)
            )
        # self.add(indices)
        self.wait(total_time + 10)


class ScoreLayoutFirst(MovingCameraScene):
    def construct(self):
        score = MusicSVG(path)
        score.move_to(self.camera.frame.get_center(), aligned_edge=LEFT)

        # total_time = score.width / 100
        total_time = 29
        scrolling_speed = score.width / total_time
        speed = ValueTracker(30)
        # speed.begin = nothing

        self.camera.frame.add_updater(lambda mob, dt: mob.shift(RIGHT * dt * speed.get_value()))
        self.add(self.camera.frame)
        print(score)

        # Print all score layout
        layout = []

        # Get label
        layout.extend(score.get_by_class("label", error_on_not_found=False))

        # Get system
        layout.extend(score.get_by_class("grpSym", error_on_not_found=False))

        # Get first barline
        layout.extend(next(path for path in score.get_by_class("system")[0] if isinstance(path, VMobjectFromSVGPath)))

        # Get staff lines
        staffs = score.get_by_class("staff")
        staff_lines = [element for staff in staffs for element in staff if isinstance(element, VMobjectFromSVGPath)]
        single_staff_lines = staff_lines[:10]
        print(len(staff_lines))
        right_x = staff_lines[-1].get_right()[0]
        left_x = staff_lines[0].get_left()[0]
        for line in single_staff_lines:
            line.stretch_to_fit_width(right_x - left_x, about_point=line.get_left())
        layout.extend(single_staff_lines)

        # Get clef
        clefs = score.get_by_class("clef")
        layout.extend(clefs[:2])

        # Get meter
        ts = score.get_by_class("meterSig")
        layout.extend(ts[:2])

        # Get key signature
        ks = score.get_by_class("keySig", error_on_not_found=False)
        layout.extend(ks[:2])

        # Add last barline
        layout.append(score.get_by_class("barLine")[-1])

        # Show all
        self.play(
            LaggedStart(DrawBorderThenFill(objs, stroke_width=100) for objs in layout),
            run_time=5,
        )
        # self.play(speed.animate.set_value(scrolling_speed), run_time=2, rate_func=rate_functions.ease_in_out_sine)
        # turn_animation_into_updater(
        #     AnimationGroup(speed.animate(run_time=2, rate_func=rate_functions.ease_in_out_sine).set_value(scrolling_speed))
        # )
        # self.wait()

        other_elements = (
                sum(
                    [score.get_by_class(cls, error_on_not_found=False) for cls in ["note", "chord", "rest", "mRest", "tie"]],
                    [],
                ) +
                (clefs[2:] if len(clefs) > 2 else []) +
                (ks[2:] if len(ks) > 2 else []) +
                (ts[2:] if len(ts) > 2 else []) +
                score.get_by_class("barLine", error_on_not_found=False)[:-1] +
                sum([group.submobjects for group in score.get_by_class("ledgerLines below", error_on_not_found=False)], []) +
                sum([group.submobjects for group in score.get_by_class("ledgerLines above", error_on_not_found=False)], []) +
                sum([group.submobjects for group in score.get_by_class("ledgerLines", error_on_not_found=False)], []) +
                [obj for group in score.get_by_class("beam", error_on_not_found=False) for obj in group if isinstance(obj, VMobjectFromSVGPath)] +
                score.get_by_class("tupletBracket", error_on_not_found=False) +
                score.get_by_class("tupletNum", error_on_not_found=False)
        )# print(other_elements)

        other_elements_by_x_position = defaultdict(list)
        for subobject in other_elements:
            other_elements_by_x_position[subobject.get_left()[0]].append(subobject)
        other_elements_by_x_position = dict(sorted(other_elements_by_x_position.items()))
        # times = [t - min(submobject_by_xposition.keys()) for t in submobject_by_xposition.keys()]
        xpos_to_group = {
            t - min(other_elements_by_x_position.keys()): VGroup(subitems)
            for t, subitems in other_elements_by_x_position.items()
        }
        for xpos, group in xpos_to_group.items():
            print(xpos / scrolling_speed)
            self.add(group)
            turn_animation_into_updater(
                # AnimationGroup(DrawBorderThenFill(subobjets, stroke_width=100, run_time=0.5)),
                # DrawBorderThenFill(group, stroke_width=100, run_time=0.5),
                FadeIn(group, run_time=0.1),
                delay=xpos / scrolling_speed,  # Replace with value tracker?
            )
        self.play(speed.animate.set_value(scrolling_speed), run_time=3, rate_func=rate_functions.ease_in_out_sine)
        self.wait(total_time-5)
        self.play(speed.animate.set_value(0), run_time=5, rate_func=rate_functions.ease_in_out_sine)
        self.wait(2)


class RealScore(MovingCameraScene):
    score_path = Path("/home/leo/Documents/score_follower/files/xml_score_cut.musicxml")
    performance_path = Path("/home/leo/Documents/score_follower/files/Shi05M_cut.mid")
    alignment_path = Path("/home/leo/Documents/score_follower/files/alignment.match")

    def construct(self):
        score = MusicSVG(self.score_path)
        score.move_to(self.camera.frame.get_center(), aligned_edge=LEFT)

        # total_time = score.width / 100
        total_time = 29
        scrolling_speed = score.width / total_time
        speed = ValueTracker(30)
        # speed.begin = nothing

        self.camera.frame.add_updater(lambda mob, dt: mob.shift(RIGHT * dt * speed.get_value()))
        self.add(self.camera.frame)
        print(score)

        # Print all score layout
        layout = []

        # Get label
        layout.extend(score.get_by_class("label", error_on_not_found=False))

        # Get system
        layout.extend(score.get_by_class("grpSym", error_on_not_found=False))

        # Get first barline
        layout.extend(next(path for path in score.get_by_class("system")[0] if isinstance(path, VMobjectFromSVGPath)))

        # Get staff lines
        staffs = score.get_by_class("staff")
        staff_lines = [element for staff in staffs for element in staff if isinstance(element, VMobjectFromSVGPath)]
        single_staff_lines = staff_lines[:10]
        print(len(staff_lines))
        right_x = staff_lines[-1].get_right()[0]
        left_x = staff_lines[0].get_left()[0]
        for line in single_staff_lines:
            line.stretch_to_fit_width(right_x - left_x, about_point=line.get_left())
        layout.extend(single_staff_lines)

        # Get clef
        clefs = score.get_by_class("clef")
        layout.extend(clefs[:2])

        # Get meter
        ts = score.get_by_class("meterSig")
        layout.extend(ts[:2])

        # Get key signature
        ks = score.get_by_class("keySig", error_on_not_found=False)
        layout.extend(ks[:2])

        # Add last barline
        layout.append(score.get_by_class("barLine")[-1])

        # Show all
        self.play(
            LaggedStart(DrawBorderThenFill(objs, stroke_width=100) for objs in layout),
            run_time=5,
        )
        # self.play(speed.animate.set_value(scrolling_speed), run_time=2, rate_func=rate_functions.ease_in_out_sine)
        # turn_animation_into_updater(
        #     AnimationGroup(speed.animate(run_time=2, rate_func=rate_functions.ease_in_out_sine).set_value(scrolling_speed))
        # )
        # self.wait()

        other_elements = (
                sum(
                    [score.get_by_class(cls, error_on_not_found=False) for cls in ["note", "chord", "rest", "mRest", "tie"]],
                    [],
                ) +
                (clefs[2:] if len(clefs) > 2 else []) +
                (ks[2:] if len(ks) > 2 else []) +
                (ts[2:] if len(ts) > 2 else []) +
                score.get_by_class("barLine", error_on_not_found=False)[:-1] +
                sum([group.submobjects for group in score.get_by_class("ledgerLines below", error_on_not_found=False)], []) +
                sum([group.submobjects for group in score.get_by_class("ledgerLines above", error_on_not_found=False)], []) +
                sum([group.submobjects for group in score.get_by_class("ledgerLines", error_on_not_found=False)], []) +
                [obj for group in score.get_by_class("beam", error_on_not_found=False) for obj in group if isinstance(obj, VMobjectFromSVGPath)] +
                score.get_by_class("tupletBracket", error_on_not_found=False) +
                score.get_by_class("tupletNum", error_on_not_found=False)
        )# print(other_elements)

        other_elements_by_x_position = defaultdict(list)
        for subobject in other_elements:
            other_elements_by_x_position[subobject.get_left()[0]].append(subobject)
        other_elements_by_x_position = dict(sorted(other_elements_by_x_position.items()))
        # times = [t - min(submobject_by_xposition.keys()) for t in submobject_by_xposition.keys()]
        xpos_to_group = {
            t - min(other_elements_by_x_position.keys()): VGroup(subitems)
            for t, subitems in other_elements_by_x_position.items()
        }
        for xpos, group in xpos_to_group.items():
            print(xpos / scrolling_speed)
            self.add(group)
            turn_animation_into_updater(
                # AnimationGroup(DrawBorderThenFill(subobjets, stroke_width=100, run_time=0.5)),
                # DrawBorderThenFill(group, stroke_width=100, run_time=0.5),
                FadeIn(group, run_time=0.1),
                delay=xpos / scrolling_speed,  # Replace with value tracker?
            )
        self.play(speed.animate.set_value(scrolling_speed), run_time=3, rate_func=rate_functions.ease_in_out_sine)
        self.wait(total_time-5)
        self.play(speed.animate.set_value(0), run_time=5, rate_func=rate_functions.ease_in_out_sine)
        self.wait(2)