"""Explainer animations for docs/architecture.html, rendered with manim.

  docs/build.sh            # renders every scene into docs/animations/*.mp4

Each scene shows one idea of the architecture, with the numbers the code actually uses (50 Hz,
20 ms latency, the springs in robot.toml, the golden-test results). When those change, change
them here too: the update-docs skill (.claude/skills/update-docs) lists what to check.
"""
import json
import math
import pathlib

import numpy as np
from manim import (DOWN, DR, LEFT, RIGHT, UP, UL, UR, Arrow, Circle, Create, DashedLine, DashedVMobject, Dot,
                   DoubleArrow, FadeIn, GrowArrow, Indicate, Rotate,
                   FadeOut, Line, MoveAlongPath, Rectangle, RoundedRectangle, Scene, Text, Transform,
                   ValueTracker, VGroup, always_redraw, config, linear, rate_functions)

# The palette the HTML uses for its dark panels: slate ground, sensor teal, intent amber,
# safety coral, bone text.
BG = "#121A22"
INK = "#E6E9EC"
DIM = "#7F8C98"
GRID = "#25313C"
TEAL = "#5CC2B7"
AMBER = "#E8A33D"
CORAL = "#EE7A62"
SANS = "Helvetica Neue"
MONO = "Menlo"

config.background_color = BG


def label(s, size=22, color=INK, font=SANS, weight="NORMAL"):
    return Text(s, font=font, font_size=size, color=color, weight=weight)


def box(w, h, color, title, sub=None, fill=0.08):
    r = RoundedRectangle(width=w, height=h, corner_radius=0.12, stroke_color=color, stroke_width=2.5,
                         fill_color=color, fill_opacity=fill)
    t = label(title, 22, INK, weight="BOLD")
    g = VGroup(r, t)
    if sub:
        s = label(sub, 15, DIM, MONO)
        VGroup(t, s).arrange(DOWN, buff=0.12).move_to(r)
        g.add(s)
    else:
        t.move_to(r)
    return g


class TickLoop(Scene):
    """One 20 ms control period, and what happens when one runs late."""

    def construct(self):
        title = label("One tick: 20 ms at 50 Hz", 30, INK, weight="BOLD").to_edge(UP, buff=0.4)
        self.play(FadeIn(title))

        scale = 0.5  # scene units per ms
        x0 = -5.0
        y = 0.6
        budget = Rectangle(width=20 * scale, height=0.9, stroke_color=DIM, stroke_width=1.5).move_to(
            [x0 + 10 * scale, y, 0])
        ticks = VGroup(*[Line([x0 + ms * scale, y - 0.6, 0], [x0 + ms * scale, y - 0.5, 0], color=DIM)
                         for ms in range(0, 21, 5)])
        tick_lbls = VGroup(*[label(f"{ms} ms", 14, DIM, MONO).move_to([x0 + ms * scale, y - 0.8, 0])
                             for ms in range(0, 21, 5)])
        self.play(Create(budget), FadeIn(ticks), FadeIn(tick_lbls))

        # The total, about 3 ms a tick, is measured against the LexJR sim (Intel MacBook); the split
        # between read and write is approximate (the bus round trip dominates both).
        phases = [
            ("read", 1.6, TEAL, "every joint, one transaction"),
            ("intents", 0.05, AMBER, "newest look_at, approach"),
            ("MotionCore", 0.06, AMBER, "aim + springs, ~30 us"),
            ("safety", 0.02, CORAL, "limits, speed, finite"),
            ("write", 1.4, CORAL, "goal positions"),
        ]
        t = 0.0
        blocks, notes = VGroup(), VGroup()
        for i, (name, ms, color, note) in enumerate(phases):
            w = max(ms * scale, 0.06)
            b = Rectangle(width=w, height=0.9, stroke_width=0, fill_color=color, fill_opacity=0.85)
            b.move_to([x0 + t * scale + w / 2, y, 0])
            t += ms
            n = label(f"{name}  {note}", 17, color).move_to([0, -1.2 - i * 0.42, 0]).align_to([-5, 0, 0], LEFT)
            blocks.add(b)
            notes.add(n)
            self.play(FadeIn(b), FadeIn(n), run_time=0.45)
        used = label(f"about {t:.1f} ms used, the rest is slack", 20, INK).next_to(budget, UP, buff=0.25)
        self.play(FadeIn(used))
        self.wait(1.2)

        # A late tick: skipped, never caught up in a burst.
        self.play(FadeOut(notes), FadeOut(used))
        row = VGroup()
        for k in range(6):
            r = Rectangle(width=0.9, height=0.6, stroke_color=DIM, stroke_width=1.5).move_to([-4.5 + k * 1.1, -1.8, 0])
            row.add(r)
        lbl = label("ticks on the original schedule", 18, DIM).next_to(row, DOWN, buff=0.25)
        self.play(FadeIn(row), FadeIn(lbl))
        for k in range(6):
            if k == 3:
                x = Text("x", font=MONO, font_size=28, color=CORAL).move_to(row[k])
                self.play(FadeIn(x), row[k].animate.set_stroke(CORAL), run_time=0.35)
                continue
            self.play(row[k].animate.set_fill(TEAL, 0.7), run_time=0.3)
        rule = label("late by more than a tick: skip it and count it; never send a burst of stale commands",
                     18, CORAL).next_to(lbl, DOWN, buff=0.25)
        self.play(FadeIn(rule))
        self.wait(2)


class Pipeline(Scene):
    """Who talks to whom, and the one seam a robot or a simulator plugs into."""

    def construct(self):
        title = label("Perception out there, motion in the tick", 30, INK, weight="BOLD").to_edge(UP, buff=0.4)
        self.play(FadeIn(title))
        cam = box(2.3, 1.3, DIM, "face_cam", "webcam").move_to([-5.6, 0.8, 0])
        app = box(2.3, 1.3, AMBER, "face_follow", "the app").move_to([-2.3, 0.8, 0])
        d = box(2.7, 1.7, CORAL, "gamerobotd", "50 Hz loop").move_to([1.0, 0.8, 0])
        body = box(2.5, 1.3, TEAL, "MuJoCo body", "BAM servos").move_to([4.85, 0.8, 0])
        self.play(*[FadeIn(b) for b in (cam, app, d, body)])
        links = [
            (cam, app, "UDP\nface 30/s", DIM),
            (app, d, "JSON-RPC\nintents", AMBER),
            (d, body, "RobotIo\nevery tick", TEAL),
        ]
        arrows = VGroup()
        for a, b, text, color in links:
            ar = Arrow(a.get_right(), b.get_left(), buff=0.1, color=color, stroke_width=3)
            tx = label(text, 14, color, MONO).move_to([ar.get_center()[0], -0.55, 0])
            arrows.add(VGroup(ar, tx))
        self.play(*[Create(a) for a in arrows])

        # Messages flowing: faces at 30/s, intents at 50/s, one read+write per tick.
        def pulse(a, b, color, n, rt):
            dots = []
            for _ in range(n):
                dot = Dot(a.get_right(), radius=0.06, color=color)
                path = Line(a.get_right(), b.get_left())
                dots.append(MoveAlongPath(dot, path, rate_func=linear, run_time=rt))
            return dots

        for _ in range(3):
            self.play(*pulse(cam, app, DIM, 1, 0.5), *pulse(app, d, AMBER, 1, 0.5), *pulse(d, body, TEAL, 1, 0.5))
        payload = label('{"method":"robot.look_at","params":{"target":[0.06,0.41,0.16]}}', 16, AMBER, MONO)
        payload.move_to([0, -1.9, 0])
        self.play(FadeIn(payload))
        self.wait(1)

        # The seam: swap the body, nothing above it changes.
        seam = DashedLine([3.0, 2.2, 0], [3.0, -0.2, 0], color=TEAL, dash_length=0.12)
        seam_lbl = label("RobotIo: the one seam", 16, TEAL).next_to(seam, UP, buff=0.1)
        self.play(FadeOut(payload), Create(seam), FadeIn(seam_lbl))
        fake = box(2.5, 1.3, TEAL, "FakeIo", "--io fake").move_to(body)
        servos = box(2.5, 1.3, TEAL, "Feetech", "servos, next").move_to(body)
        note = label("same daemon, same app, same tick: only the box on the right changes", 18, INK)
        note.move_to([0, -1.9, 0])
        self.play(FadeIn(note))
        self.play(Transform(body, fake), run_time=0.8)
        self.wait(0.6)
        self.play(Transform(body, servos), run_time=0.8)
        self.wait(2)


class StaggeredGaze(Scene):
    """The head snaps to the target; the body follows; the head counter-rotates to hold its gaze.

    A yaw-only model of MotionCore, with robot.toml's springs: head 5 Hz critically damped, body
    0.9 Hz at zeta 0.75, an 8 degree body deadband, the body taking 60% of the turn."""

    def construct(self):
        title = label("Staggered gaze: the eyes lead, the body follows", 30, INK, weight="BOLD").to_edge(UP, buff=0.4)
        self.play(FadeIn(title))

        dt, T = 0.02, 3.0
        n = int(T / dt)
        target = np.where(np.arange(n) * dt < 0.3, 0.0, 60.0)
        b = bv = h = hv = 0.0
        body_goal = 0.0
        hist = []
        for k in range(n):
            goal = 0.6 * target[k]
            if abs(goal - body_goal) > 8:
                body_goal = goal
            w = 2 * math.pi * 0.9
            bv += (w * w * (body_goal - b) - 2 * 0.75 * w * bv) * dt
            b += bv * dt
            hg = target[k] - b  # head aimed against the commanded body
            w = 2 * math.pi * 5.0
            hv += (w * w * (hg - h) - 2 * 1.0 * w * hv) * dt
            h += hv * dt
            hist.append((target[k], b, h, b + h))
        hist = np.array(hist)

        # Top-down robot, left.
        c = np.array([-3.6, -0.6, 0])
        base = Circle(radius=1.0, color=DIM, stroke_width=2).move_to(c)
        t_idx = ValueTracker(0)

        def ray(angle_deg, length, color, width):
            a = math.radians(90 + angle_deg)
            return Line(c, c + length * np.array([math.cos(a), math.sin(a), 0]), color=color, stroke_width=width)

        body = always_redraw(lambda: ray(hist[int(t_idx.get_value())][1], 1.0, TEAL, 10))
        gaze = always_redraw(lambda: ray(hist[int(t_idx.get_value())][3], 2.4, AMBER, 3))
        tgt = always_redraw(lambda: Dot(c + 2.6 * np.array([math.cos(math.radians(90 + hist[int(t_idx.get_value())][0])),
                                                          math.sin(math.radians(90 + hist[int(t_idx.get_value())][0])), 0]),
                                        radius=0.11, color=CORAL))
        legend = VGroup(label("target", 16, CORAL), label("gaze", 16, AMBER), label("body", 16, TEAL)).arrange(
            RIGHT, buff=0.4).move_to(c + np.array([0, -1.6, 0]))
        self.play(Create(base), FadeIn(body), FadeIn(gaze), FadeIn(tgt), FadeIn(legend))

        # Traces, right.
        ox, oy, sx, sy = 0.6, -1.9, 6.0 / T, 3.4 / 70
        axes = VGroup(Line([ox, oy, 0], [ox + 6.1, oy, 0], color=DIM), Line([ox, oy, 0], [ox, oy + 3.5, 0], color=DIM))
        ylab = VGroup(*[label(f"{v} deg", 13, DIM, MONO).move_to([ox - 0.5, oy + v * sy, 0]) for v in (0, 30, 60)])
        xlab = VGroup(*[label(f"{s:.0f} s", 13, DIM, MONO).move_to([ox + s * sx, oy - 0.25, 0]) for s in (0, 1, 2, 3)])
        self.play(Create(axes), FadeIn(ylab), FadeIn(xlab))

        def trace(col, color, width=3):
            def f():
                k = max(2, int(t_idx.get_value()) + 1)
                pts = [[ox + i * dt * sx, oy + hist[i][col] * sy, 0] for i in range(k)]
                line = VGroup()
                for p, q in zip(pts[:-1], pts[1:]):
                    line.add(Line(p, q, color=color, stroke_width=width))
                return line
            return always_redraw(f)

        self.add(trace(0, CORAL, 2), trace(1, TEAL), trace(2, DIM, 2), trace(3, AMBER))
        head_lbl = label("head (relative)", 14, DIM).move_to([ox + 5.4, oy + 0.35, 0])
        self.add(head_lbl)
        self.play(t_idx.animate.set_value(n - 1), run_time=6, rate_func=linear)
        note = label("the gaze is on the target in ~0.25 s; the body takes ~2 s and the head unwinds as it arrives",
                     17, INK).to_edge(DOWN, buff=0.35)
        self.play(FadeIn(note))
        self.wait(2)


class GoldenHarness(Scene):
    """How the Rust port is held to MuJoCo and the Python, and how close it is."""

    def construct(self):
        title = label("Golden tests: the Rust port against MuJoCo", 30, INK, weight="BOLD").to_edge(UP, buff=0.4)
        self.play(FadeIn(title))
        src = box(2.8, 1.3, TEAL, "lexjr-sim", "MuJoCo + Python").move_to([-5.0, 1.3, 0])
        gold = box(2.8, 1.3, DIM, "golden JSON", "500 + 300 + 3,250").move_to([-1.5, 1.3, 0])
        nat = box(3.1, 1.0, AMBER, "native chain").move_to([2.4, 1.9, 0])
        mj = box(3.1, 1.0, AMBER, "MuJoCo backend").move_to([2.4, 0.7, 0])
        self.play(FadeIn(src))
        self.play(Create(Arrow(src.get_right(), gold.get_left(), buff=0.1, color=DIM)), FadeIn(gold))
        self.play(Create(Arrow(gold.get_right(), nat.get_left(), buff=0.1, color=AMBER)),
                  Create(Arrow(gold.get_right(), mj.get_left(), buff=0.1, color=AMBER)), FadeIn(nat), FadeIn(mj))

        # Log scale of the worst differences found, against the tolerances and a servo tick.
        lo, hi = -16, -2
        x0, x1, y = -5.5, 5.5, -1.6

        def x(exp):
            return x0 + (exp - lo) / (hi - lo) * (x1 - x0)

        axis = Line([x0, y, 0], [x1, y, 0], color=DIM)
        marks = VGroup(*[VGroup(Line([x(e), y - 0.08, 0], [x(e), y + 0.08, 0], color=DIM),
                                label(f"1e{e}", 13, DIM, MONO).move_to([x(e), y - 0.3, 0])) for e in range(lo, hi + 1, 2)])
        self.play(Create(axis), FadeIn(marks))
        rows = [
            ("kinematics, 500 poses", 2.4e-15, TEAL),
            ("solver, 300 cases", 3.9e-11, AMBER),
            ("MotionCore, 3,250 ticks", 2.0e-11, AMBER),
        ]
        dots = VGroup()
        for i, (name, v, color) in enumerate(rows):
            e = math.log10(v)
            yy = y + 0.55 + i * 0.4
            dot = Dot([x(e), yy, 0], color=color, radius=0.08)
            tx = label(f"{name}: {v:.1e}", 15, color, MONO).next_to(dot, RIGHT, buff=0.15)
            dots.add(VGroup(dot, tx))
        self.play(*[FadeIn(d) for d in dots], run_time=1.2)
        servo = DashedLine([x(math.log10(1.5e-3)), y, 0], [x(math.log10(1.5e-3)), y + 1.9, 0], color=CORAL)
        servo_lbl = label("one servo tick\n1.5e-3 rad", 14, CORAL).next_to(servo, UP, buff=0.05)
        self.play(Create(servo), FadeIn(servo_lbl))
        note = label("8 orders of magnitude below what a servo can resolve; 7 planted bugs all fail the harness",
                     17, INK).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(note))
        self.wait(2.5)


class CatVsSmooth(Scene):
    """Two gaze behaviours on the same moving face: where each decides to look.

    Runs the real lexjr-sim behaviours (lexjr_ctl/behaviours.py: SmoothFollow and CatGaze, seeded)
    through the gamerobotics Runner's interface, on a face that drifts and jumps, and plots the
    yaw of each one's gaze target."""

    def construct(self):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        sys.path[:0] = [str(root / "python"), str(root.parent / "lexjr-sim")]
        from gamerobotics.behaviours import Face, Intent, Percept
        from lexjr_ctl.behaviours import CatGaze, SmoothFollow

        eye, dist, dt, T = np.array([0.06, 0.057, 0.157]), 0.35, 0.02, 10.0

        def at(yaw):
            a = math.radians(yaw)
            c = eye + dist * np.array([-math.sin(a), math.cos(a), 0.0])
            side = np.array([math.cos(a), math.sin(a), 0.0]) * 0.032
            return Face(eyes=tuple(c), left_eye=tuple(c - side), right_eye=tuple(c + side), mouth=tuple(c - [0, 0, 0.05]))

        def face_yaw(t):  # drifts, then jumps: 0, +25, -15, +10 deg
            base = [0, 25, -15, 10][min(int(t // 2.5), 3)]
            return base + 3 * math.sin(1.7 * t)

        def yaw_of(p):
            d = np.asarray(p) - eye
            return -math.degrees(math.atan2(d[0], d[1]))

        smooth, cat = SmoothFollow(), CatGaze(seed=4)
        start = {"gaze": Intent.look_at(at(0).eyes)}
        smooth.start(start)
        cat.start(start)
        n = int(T / dt)
        rows = []
        for k in range(n):
            t = k * dt
            seen = Percept(t=t, face=at(face_yaw(t)), eye=tuple(eye), home=tuple(eye + [0, dist, 0]))
            s = smooth.tick(seen)[0]
            c = cat.tick(seen)[0]
            rows.append((face_yaw(t), yaw_of(s.params["target"]), yaw_of(c.params["target"]), c.params["saccade"], cat.state))

        title = label("Two gaze behaviours, one face", 30, INK, weight="BOLD").to_edge(UP, buff=0.35)
        self.play(FadeIn(title))
        lo = -28  # yaw -28..+32 deg: darts sit ~5 deg either side of the face, at its eyes
        ox, oy, sx, sy = -5.6, -2.6, 11.0 / T, 4.0 / 60
        y0 = oy - lo * sy
        axes = VGroup(Line([ox, y0, 0], [ox + 11.2, y0, 0], color=GRID),
                      Line([ox, oy, 0], [ox, oy + 4.1, 0], color=DIM))
        ylab = VGroup(*[label(f"{v:+d}", 13, DIM, MONO).move_to([ox - 0.35, oy + (v - lo) * sy, 0]) for v in (-20, 0, 20)])
        xlab = VGroup(*[label(f"{s} s", 13, DIM, MONO).move_to([ox + s * sx, oy - 0.25, 0]) for s in (0, 2, 4, 6, 8, 10)])
        unit = label("gaze yaw, deg", 13, DIM).move_to([ox + 0.8, oy + 4.25, 0])
        legend = VGroup(label("your face", 16, CORAL), label("smooth follow", 16, TEAL), label("cat gaze", 16, AMBER),
                        label("saccade", 16, AMBER)).arrange(RIGHT, buff=0.5).to_edge(DOWN, buff=0.25)
        legend[3].set_opacity(0.0)
        dot_key = Dot(radius=0.07, color=AMBER).next_to(legend[3], LEFT, buff=0.1)
        self.play(Create(axes), FadeIn(ylab), FadeIn(xlab), FadeIn(unit), FadeIn(legend))
        legend[3].set_opacity(1.0)
        self.add(dot_key)

        idx = ValueTracker(1)

        def pt(i, col):
            return [ox + i * dt * sx, oy + (rows[i][col] - lo) * sy, 0]

        def trace(col, color, width, opacity=1.0):
            def f():
                k = max(2, int(idx.get_value()))
                g = VGroup()
                for i in range(1, k):
                    g.add(Line(pt(i - 1, col), pt(i, col), color=color, stroke_width=width, stroke_opacity=opacity))
                return g
            return always_redraw(f)

        def jumps():
            k = int(idx.get_value())
            return VGroup(*[Dot(pt(i, 2), radius=0.06, color=AMBER) for i in range(k) if rows[i][3]])

        def state():
            k = max(0, int(idx.get_value()) - 1)
            return label(f"cat: {rows[k][4]}", 18, AMBER, MONO).move_to([4.6, 2.55, 0])

        self.add(trace(0, CORAL, 12, 0.35), trace(1, TEAL, 2.5), trace(2, AMBER, 3.5), always_redraw(jumps), always_redraw(state))
        self.play(idx.animate.set_value(n - 1), run_time=9, rate_func=linear)
        note = label("smooth glides after every drift; the cat holds, decides, jumps, follows, then darts",
                     17, INK).move_to([0, 2.0, 0])
        self.play(FadeIn(note))
        self.wait(2)


class AppTick(Scene):
    """One app tick: a percept in, each slot's owner answers, intents out; then a live switch of the
    gaze slot, with the glide."""

    def construct(self):
        title = label("One app tick: percept in, intents out", 30, INK, weight="BOLD").to_edge(UP, buff=0.35)
        self.play(FadeIn(title))
        perc = box(2.6, 1.2, DIM, "Percept", "face, tilt").move_to([-5.3, 0.4, 0])
        runner = RoundedRectangle(width=4.6, height=4.2, corner_radius=0.15, stroke_color=AMBER, stroke_width=2.5,
                                  fill_color=AMBER, fill_opacity=0.05).move_to([-0.6, 0.2, 0])
        rlab = label("Runner", 20, AMBER, weight="BOLD").next_to(runner, UP, buff=0.08).align_to(runner, LEFT)
        slots = []
        for k, (slot, owner, color) in enumerate([("gaze", "SmoothFollow", TEAL), ("approach", "KeepDistance", TEAL),
                                                  ("tilt", "MimicTilt", TEAL)]):
            y = 1.5 - k * 1.3
            s = label(slot, 15, DIM, MONO).move_to([-2.25, y, 0])
            b = box(2.7, 0.85, color, owner).move_to([0.0, y, 0])
            slots.append((s, b))
        daemon = box(2.6, 1.6, CORAL, "gamerobotd", "motion primitives").move_to([5.1, 0.4, 0])
        self.play(FadeIn(perc), Create(runner), FadeIn(rlab), *[FadeIn(VGroup(s, b)) for s, b in slots], FadeIn(daemon))

        intents = ["look_at", "approach", "tilt"]

        def one_tick(gaze_text="look_at", gaze_color=AMBER):
            dots = [Dot(perc.get_right(), radius=0.07, color=DIM) for _ in slots]
            self.play(*[MoveAlongPath(d, Line(perc.get_right(), b.get_left())) for d, (_, b) in zip(dots, slots)],
                      run_time=0.6)
            chips = []
            for k, (_, b) in enumerate(slots):
                text = gaze_text if k == 0 else intents[k]
                c = label(text, 15, gaze_color if k == 0 else AMBER, MONO).next_to(b, RIGHT, buff=0.15)
                chips.append(c)
            self.play(*[FadeOut(d) for d in dots], *[FadeIn(c) for c in chips], run_time=0.4)
            self.play(*[c.animate.move_to(daemon.get_left() + [-0.3, 0.3 - 0.3 * k, 0]).set_opacity(0.0)
                        for k, c in enumerate(chips)], run_time=0.6)

        one_tick()
        one_tick()
        note = label("each slot has one owner; intents for slots it does not own are dropped", 17, INK).to_edge(DOWN, buff=0.5)
        self.play(FadeIn(note))
        self.wait(0.6)

        # m pressed: the gaze slot goes to CatGaze, with a glide.
        key = label("m", 22, CORAL, MONO, weight="BOLD").move_to([-5.3, -1.3, 0])
        keybox = RoundedRectangle(width=0.6, height=0.6, corner_radius=0.08, stroke_color=CORAL).move_to(key)
        self.play(FadeIn(keybox), FadeIn(key))
        cat = box(2.7, 0.85, AMBER, "CatGaze").move_to(slots[0][1])
        self.play(Transform(slots[0][1], cat), run_time=0.7)
        glide = label("handover: a 0.5 s glide, saccades held back", 17, AMBER).to_edge(DOWN, buff=0.5)
        self.play(Transform(note, glide))
        one_tick("look_at (blend)", DIM)
        one_tick("look_at saccade", CORAL)
        final = label("after the glide the cat's saccades go through; approach and tilt never stopped", 17, INK).to_edge(DOWN, buff=0.5)
        self.play(Transform(note, final))
        self.wait(2)


# ---- product.html: the user flow and the parts model --------------------------------------


class FirstWiggle(Scene):
    """The goal: from install to a robot reacting to you in under 10 minutes, one command."""

    def construct(self):
        title = label("Time to first wiggle: under 10 minutes", 30, INK, weight="BOLD").to_edge(UP, buff=0.35)
        self.play(FadeIn(title))

        today = VGroup(*[label(t, 16, DIM, MONO) for t in (
            "terminal 1  .venv-bam/bin/mjpython body_server.py",
            "terminal 2  gamerobotd --io sim",
            "terminal 3  .venv-cam/bin/python face_cam.py",
            "terminal 4  .venv-bam/bin/python face_follow.py",
            "+ three Python environments, quit OBS, watch the CPU")]).arrange(DOWN, aligned_edge=LEFT, buff=0.14)
        today.move_to([0, 1.0, 0])
        tl = label("today", 18, CORAL).next_to(today, UP, buff=0.2).align_to(today, LEFT)
        self.play(FadeIn(tl), *[FadeIn(t) for t in today], run_time=1.0)
        cross = Line(today.get_corner(UL) + [-0.1, 0.1, 0], today.get_corner(DOWN + RIGHT) + [0.1, -0.1, 0],
                     color=CORAL, stroke_width=4)
        self.play(Create(cross))
        self.wait(0.4)
        cmd = label("$ gamerobotics play lexjr", 30, AMBER, MONO).move_to([0, 1.0, 0])
        self.play(FadeOut(today), FadeOut(cross), FadeOut(tl), FadeIn(cmd))

        # The timeline: minutes 0..10.
        x0, x1, y = -5.5, 5.5, -1.4
        axis = Line([x0, y, 0], [x1, y, 0], color=DIM)
        marks = VGroup(*[label(f"{m} min", 13, DIM, MONO).move_to([x0 + (x1 - x0) * m / 10, y - 0.3, 0]) for m in (0, 2, 4, 6, 8, 10)])
        self.play(Create(axis), FadeIn(marks))
        steps = [(0.0, "install", DIM), (1.5, "play", AMBER), (2.0, "it looks at you", TEAL),
                 (4.0, "pick Curious Cat", AMBER), (6.0, "tune it live", AMBER), (8.0, "save as yours", TEAL)]
        dots = VGroup()
        for k, (m, text, color) in enumerate(steps):
            x = x0 + (x1 - x0) * m / 10
            d = Dot([x, y, 0], radius=0.09, color=color)
            t = label(text, 16, color).move_to([x, y + (0.55 if k % 2 == 0 else 1.05), 0])
            dots.add(VGroup(d, t))
            self.play(FadeIn(d), FadeIn(t), run_time=0.45)
        goal = DashedLine([x1, y - 0.15, 0], [x1, y + 1.6, 0], color=CORAL)
        gl = label("goal", 15, CORAL).next_to(goal, UP, buff=0.05)
        self.play(Create(goal), FadeIn(gl))
        note = label("no hardware, no terminals: the robot is on your screen and it sees you", 18, INK).to_edge(DOWN, buff=0.35)
        self.play(FadeIn(note))
        self.wait(2)


class PartsToRobot(Scene):
    """A robot is an assembly of characterized parts; the tools derive what used to be hand-typed."""

    def construct(self):
        title = label("Parts in, robot out: limits derived, not typed", 30, INK, weight="BOLD").to_edge(UP, buff=0.35)
        self.play(FadeIn(title))
        servo = box(3.2, 1.3, TEAL, "STS3215", "360°, 550°/s, BAM").move_to([-5.1, 1.4, 0])
        gear = box(3.2, 1.3, AMBER, "spur 3:1", "backlash 0.3°").move_to([-5.1, -0.2, 0])
        cam = box(3.2, 1.3, DIM, "USB webcam", "60° FOV, 33 ms").move_to([-5.1, -1.8, 0])
        cl = label("catalogue", 18, DIM).next_to(servo, UP, buff=0.2)
        self.play(FadeIn(cl), FadeIn(servo), FadeIn(gear), FadeIn(cam))

        joint = box(2.6, 1.4, CORAL, "torso_yaw", "servo + gear").move_to([-0.9, 0.6, 0])
        self.play(Create(Arrow(servo.get_right(), joint.get_left(), buff=0.1, color=TEAL)),
                  Create(Arrow(gear.get_right(), joint.get_left(), buff=0.1, color=AMBER)), FadeIn(joint))
        derived = [
            ("range", "360° ÷ 3 = ±60°, less 3° = ±57°"),
            ("speed", "550°/s ÷ 3 = 183.3°/s"),
            ("sim", "the servo's BAM model, through the gear"),
            ("driver", "ID, zero, direction from the wizard"),
        ]
        rows = VGroup()
        for k, (a, b) in enumerate(derived):
            r = VGroup(label(a, 16, DIM, MONO), label(b, 17, INK)).arrange(RIGHT, buff=0.3)
            rows.add(r)
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.22).move_to([3.5, 0.6, 0])
        for r in rows:
            self.play(FadeIn(r), run_time=0.5)
        capl = label("capability: gaze, eye = the webcam at the head", 18, TEAL).move_to([1.5, -1.8, 0])
        self.play(Create(Arrow(cam.get_right(), capl.get_left(), buff=0.15, color=DIM)), FadeIn(capl))
        note = label("characterize a part once; every robot built from it inherits the work", 18, INK).to_edge(DOWN, buff=0.35)
        self.play(FadeIn(note))
        self.wait(2)


class CapabilityMatch(Scene):
    """Behaviours need capabilities; robots, ours and others', provide them."""

    def construct(self):
        title = label("Behaviours target capabilities, not robots", 30, INK, weight="BOLD").to_edge(UP, buff=0.35)
        self.play(FadeIn(title))
        robots = [("pan-tilt head", {"gaze"}, ""), ("LexJR", {"gaze", "approach", "tilt"}, ""),
                  ("Reachy Mini", {"gaze", "tilt"}, "no saccade: glides"), ("microduck", {"gaze", "locomotion"}, "")]
        behaviours = [("cat gaze", {"gaze"}), ("keep distance", {"approach"}), ("mimic tilt", {"tilt"}), ("walk to you", {"locomotion", "gaze"})]
        x0, y0, dx, dy = -2.2, 1.6, 2.35, -0.95
        hdr = VGroup(*[label(r[0], 17, TEAL, weight="BOLD").move_to([x0 + i * dx, y0 + 0.75, 0]) for i, r in enumerate(robots)])
        side = VGroup(*[label(b[0], 17, AMBER).move_to([-5.0, y0 + j * dy, 0]) for j, b in enumerate(behaviours)])
        needs = VGroup(*[label("needs " + " + ".join(sorted(b[1])), 12, DIM, MONO).move_to([-5.0, y0 + j * dy - 0.3, 0])
                         for j, b in enumerate(behaviours)])
        self.play(FadeIn(hdr), FadeIn(side), FadeIn(needs))
        for j, (bname, need) in enumerate(behaviours):
            cells = []
            for i, (rname, caps, note) in enumerate(robots):
                ok = need <= caps
                c = label("✓" if ok else "×", 26, TEAL if ok else CORAL, weight="BOLD").move_to([x0 + i * dx, y0 + j * dy, 0])
                cells.append(FadeIn(c))
            self.play(*cells, run_time=0.5)
        fallback = label("Reachy Mini: gaze without saccades, so cat gaze glides there", 16, DIM).move_to([1.3, y0 + 4 * dy + 0.1, 0])
        self.play(FadeIn(fallback))
        note = label("the runner checks needs before it runs a behaviour, and says what is missing", 18, INK).to_edge(DOWN, buff=0.35)
        self.play(FadeIn(note))
        self.wait(2)


class Personalities(Scene):
    """A personality is parameters: the real CatGaze with two presets, on the same face."""

    def construct(self):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        sys.path[:0] = [str(root / "python"), str(root.parent / "lexjr-sim")]
        from gamerobotics.behaviours import Face, Intent, Percept
        from lexjr_ctl.behaviours import CatGaze

        eye, dist, dt, T = np.array([0.06, 0.057, 0.157]), 0.35, 0.02, 10.0

        def at(yaw):
            a = math.radians(yaw)
            c = eye + dist * np.array([-math.sin(a), math.cos(a), 0.0])
            side = np.array([math.cos(a), math.sin(a), 0.0]) * 0.032
            return Face(eyes=tuple(c), left_eye=tuple(c - side), right_eye=tuple(c + side), mouth=tuple(c - [0, 0, 0.05]))

        def face_yaw(t):
            return [0, 20, -10, 12][min(int(t // 2.5), 3)] + 3 * math.sin(1.3 * t)

        def yaw_of(p):
            d = np.asarray(p) - eye
            return -math.degrees(math.atan2(d[0], d[1]))

        # The presets proposed in product-spec.md.
        curious = CatGaze(seed=2, react_s=(0.10, 0.30), cone_deg=5.0, dart_every_s=(0.25, 0.6), track_s=(0.6, 1.2))
        shy = CatGaze(seed=2, react_s=(0.4, 0.8), cone_deg=12.0, dart_every_s=(0.6, 1.2), stare_s=(2.5, 4.0), darts=(2, 4))
        start = {"gaze": Intent.look_at(at(0).eyes)}
        for c in (curious, shy):
            c.start(start)
        rows = []
        for k in range(int(T / dt)):
            t = k * dt
            seen = Percept(t=t, face=at(face_yaw(t)), eye=tuple(eye), home=tuple(eye + [0, dist, 0]))
            a = curious.tick(seen)[0]
            b = shy.tick(seen)[0]
            rows.append((face_yaw(t), yaw_of(a.params["target"]), yaw_of(b.params["target"])))

        title = label("A personality is parameters", 30, INK, weight="BOLD").to_edge(UP, buff=0.35)
        self.play(FadeIn(title))
        lo, ox, oy, sx, sy = -24, -5.6, -2.5, 11.0 / T, 3.8 / 52
        axes = VGroup(Line([ox, oy - lo * sy, 0], [ox + 11.2, oy - lo * sy, 0], color=GRID),
                      Line([ox, oy, 0], [ox, oy + 3.9, 0], color=DIM))
        xl = VGroup(*[label(f"{s} s", 13, DIM, MONO).move_to([ox + s * sx, oy - 0.25, 0]) for s in (0, 2, 4, 6, 8, 10)])
        legend = VGroup(label("your face", 16, CORAL), label("Curious Cat", 16, AMBER), label("Shy Puppy", 16, TEAL)).arrange(
            RIGHT, buff=0.6).to_edge(DOWN, buff=0.25)
        presets = VGroup(label("Curious Cat: react 0.1–0.3 s, cone 5°, quick darts", 15, AMBER, MONO),
                         label("Shy Puppy:   react 0.4–0.8 s, cone 12°, long stares", 15, TEAL, MONO)).arrange(
            DOWN, aligned_edge=LEFT, buff=0.12).move_to([0, 2.15, 0])
        self.play(Create(axes), FadeIn(xl), FadeIn(legend), FadeIn(presets))
        idx = ValueTracker(1)

        def pt(i, col):
            return [ox + i * dt * sx, oy + (rows[i][col] - lo) * sy, 0]

        def trace(col, color, width, opacity=1.0):
            def f():
                k = max(2, int(idx.get_value()))
                return VGroup(*[Line(pt(i - 1, col), pt(i, col), color=color, stroke_width=width, stroke_opacity=opacity)
                                for i in range(1, k)])
            return always_redraw(f)

        self.add(trace(0, CORAL, 12, 0.3), trace(2, TEAL, 3), trace(1, AMBER, 3))
        self.play(idx.animate.set_value(len(rows) - 1), run_time=8, rate_func=linear)
        self.wait(2)


class KitBuild(Scene):
    """Build from the kit: describe a robot, the LLM picks kit parts, they snap together, the
    checks pass, capabilities light up."""

    def construct(self):
        title = label("Describe it, and it's built from the kit", 30, INK, weight="BOLD").to_edge(UP, buff=0.35)
        self.play(FadeIn(title))
        prompt = label('"a little robot that balances on two wheels and looks around"', 19, AMBER, MONO)
        prompt.move_to([0, 2.45, 0])
        self.play(FadeIn(prompt, shift=0.2 * UP))

        # The kit tray.
        tray_y = -2.75
        names = [("servo", TEAL), ("servo", TEAL), ("wheel", DIM), ("wheel", DIM), ("IMU", CORAL),
                 ("bracket", DIM), ("servo", TEAL), ("servo", TEAL), ("webcam", AMBER), ("battery", DIM)]
        kit = []
        for k, (n, c) in enumerate(names):
            b = RoundedRectangle(width=1.0, height=0.5, corner_radius=0.08, stroke_color=c, stroke_width=2,
                                 fill_color=c, fill_opacity=0.12).move_to([-5.4 + k * 1.2, tray_y, 0])
            kit.append(VGroup(b, label(n, 13, INK, MONO).move_to(b)))
        tl = label("kit", 15, DIM).next_to(kit[0], LEFT, buff=0.25)
        self.play(FadeIn(tl), *[FadeIn(p) for p in kit], run_time=0.8)

        # Where each part lands: a two-wheel balancer with a pan-tilt head.
        cx = -2.2
        targets = [
            [cx - 0.75, -0.60, 0], [cx + 0.75, -0.60, 0],    # drive servos
            [cx - 1.35, -1.00, 0], [cx + 1.35, -1.00, 0],    # wheels
            [cx, -0.10, 0],                                  # IMU
            [cx, 0.50, 0],                                   # body bracket
            [cx, 1.10, 0], [cx, 1.65, 0],                     # pan, tilt
            [cx + 0.95, 1.65, 0],                             # webcam
            [cx - 1.1, 0.50, 0],                             # battery
        ]
        moves = [kit[k].animate.move_to(targets[k]) for k in range(len(kit))]
        self.play(*moves, FadeOut(tl), run_time=1.6, rate_func=rate_functions.smooth)
        wheels = VGroup(*[Circle(radius=0.42, color=DIM, stroke_width=3).move_to(targets[k]) for k in (2, 3)])
        self.play(Create(wheels), run_time=0.5)

        checks = ["parts connect", "servos carry the load", "IMU present: can balance", "the battery feeds every servo",
                  "every joint in range"]
        rows = VGroup()
        for c in checks:
            rows.add(VGroup(label("✓", 18, TEAL, weight="BOLD"), label(c, 17, INK)).arrange(RIGHT, buff=0.2))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.18).move_to([3.2, 0.7, 0])
        cl = label("checks", 15, DIM).next_to(rows, UP, buff=0.2).align_to(rows, LEFT)
        self.play(FadeIn(cl))
        for r in rows:
            self.play(FadeIn(r), run_time=0.35)
        caps = VGroup(*[label(c, 16, TEAL, MONO) for c in ("balance", "drive", "gaze")]).arrange(RIGHT, buff=0.35)
        boxes = VGroup(*[RoundedRectangle(width=c.width + 0.3, height=0.45, corner_radius=0.06, stroke_color=TEAL).move_to(c)
                         for c in caps])
        capg = VGroup(boxes, caps).next_to(rows, DOWN, buff=0.45).align_to(rows, LEFT)
        self.play(FadeIn(capg))
        note = label("kit parts only, every suggestion checked: what it builds simulates, and can be built", 17, INK)
        note.move_to([0, tray_y + 0.05, 0])
        self.play(FadeIn(note))
        self.wait(2)


# Narrated tours: videos with a voice-over, one step per entry in tours/<tour>.json. These helpers
# are shared by every tour scene (scripts/voiceover.py hashes them with each scene).
#
# The architecture tour: the overview diagram (architecture.md) built up a block at a time, with a
# voice-over. The words are in tours/architecture.json; scripts/voiceover.py makes
# voice/architecture/<id>.mp3 and the lengths in its manifest.json, which set how long each step lasts.
TOUR = pathlib.Path(__file__).resolve().parent


def node(x, y, w, title, sub=None, color=INK, planned=False, h=0.8):
    r = RoundedRectangle(width=w, height=h, corner_radius=0.1, stroke_color=color, stroke_width=2.2,
                         fill_color=color, fill_opacity=0.0 if planned else 0.08)
    if planned:
        r = DashedVMobject(r, num_dashes=int(2.4 * (w + h)) + 6, dashed_ratio=0.55)
    t = label(title, 17, INK, weight="BOLD")
    g = VGroup(r, t)
    if sub:
        s = label(sub, 12, DIM, MONO)
        VGroup(t, s).arrange(DOWN, buff=0.08)
        g.add(s)
    VGroup(*g[1:]).move_to([x, y, 0])
    r.move_to([x, y, 0])
    return g


def frame(x0, y0, x1, y1, name, color):
    r = Rectangle(width=x1 - x0, height=y1 - y0, stroke_color=color, stroke_width=1.2, stroke_opacity=0.5,
                  fill_color=color, fill_opacity=0.04).move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0])
    t = label(name, 12, color, MONO).next_to(r, UP, buff=0.06).align_to(r, LEFT)
    return VGroup(r, t)


def link(a, b, text=None, both=False, planned=False, color=DIM, side=RIGHT):
    cls = DoubleArrow if both else Arrow
    ar = cls(a, b, buff=0.0, stroke_width=2.2, color=color, tip_length=0.16, max_tip_length_to_length_ratio=0.2)
    if planned:
        ar = VGroup(DashedLine(a, b, stroke_width=2.2, color=color, dash_length=0.1),
                    *[t.copy() for t in ar.get_tips()]) if hasattr(ar, "get_tips") else ar
    g = VGroup(ar)
    if text:
        g.add(label(text, 11, DIM, MONO).next_to(ar.get_center() if not planned else ar[0].get_center(), side, buff=0.1))
    return g


class ArchitectureTour(Scene):
    """The architecture overview, built up block by block, narrated."""

    def construct(self):
        steps = json.loads((TOUR / "tours" / "architecture.json").read_text())["steps"]
        manifest = json.loads((TOUR / "voice" / "architecture" / "manifest.json").read_text())
        self.caption = None

        def step(i, name, *anims, hold=0.5):
            sid = steps[i]["id"]
            self.add_sound(str(TOUR / "voice" / "architecture" / f"{sid}.mp3"))
            spent = 0.0
            cap = label(name, 18, AMBER, weight="BOLD").to_corner(DOWN + LEFT, buff=0.3)
            if self.caption is None:
                self.play(FadeIn(cap), run_time=0.4)
            else:
                self.play(FadeOut(self.caption), FadeIn(cap), run_time=0.4)
            self.caption = cap
            spent += 0.4
            for a, rt in anims:
                self.play(*a, run_time=rt)
                spent += rt
            self.wait(max(hold, manifest[sid]["seconds"] - spent + hold))

        # Step 0: title and legend.
        title = label("gameRobotics architecture", 40, INK, weight="BOLD").move_to([0, 0.5, 0])
        sub = label("built up one block at a time", 22, DIM).next_to(title, DOWN, buff=0.25)
        solid = RoundedRectangle(width=0.6, height=0.32, corner_radius=0.06, stroke_color=INK, stroke_width=2)
        dash = DashedVMobject(solid.copy(), num_dashes=10, dashed_ratio=0.55)
        legend = VGroup(VGroup(solid, label("running today", 14, DIM)).arrange(RIGHT, buff=0.15),
                        VGroup(dash, label("planned (A0, D0, H0)", 14, DIM)).arrange(RIGHT, buff=0.15)
                        ).arrange(RIGHT, buff=0.5).next_to(sub, DOWN, buff=0.6)
        step(0, "", ([FadeIn(title), FadeIn(sub)], 1.0), ([FadeIn(legend)], 0.8), hold=0.2)
        self.play(FadeOut(title), FadeOut(sub), legend.animate.scale(0.85).to_corner(DOWN + RIGHT, buff=0.3), run_time=0.8)

        # Step 1: the daemon's control loop.
        dmn = frame(-6.4, -1.75, 0.15, 1.95, "gamerobotd · Rust · 50 Hz", CORAL)
        loop = node(-2.35, 0.1, 3.55, "Control loop", "Controller · MotionCore · Safety", CORAL)
        tick = Circle(radius=0.16, color=CORAL, stroke_width=3).next_to(loop, RIGHT, buff=0.15)
        drive = node(-5.35, 0.1, 1.9, "Diff drive", "odometry · wheels", CORAL)
        l_drive = link(drive[0].get_right(), loop[0].get_left(), both=True)
        step(1, "1  The daemon", ([FadeIn(dmn)], 0.6), ([FadeIn(loop), Create(tick)], 0.8),
             ([Rotate(tick, angle=-2 * math.pi, rate_func=linear)], 1.0),
             ([FadeIn(drive), FadeIn(l_drive)], 0.8))

        # Step 2: RobotIo and the body.
        io = node(-1.95, -1.2, 3.9, "RobotIo", "FakeIo · RemoteIo · FeetechIo (H0)", CORAL)
        sim = node(-0.8, -2.75, 3.0, "Simulator: body_server", "MuJoCo + BAM servo models", INK)
        servos = node(-4.4, -2.75, 2.8, "Servos (H0)", "via Waveshare board", INK, planned=True)
        l_io = link(loop[0].get_bottom() + RIGHT * 1.0, io[0].get_top() + RIGHT * 0.0)
        l_sim = link(io[0].get_bottom() + RIGHT * 0.9, sim[0].get_top(), "TCP 7600 · 1/tick", both=True)
        l_srv = link(io[0].get_bottom() + LEFT * 1.0, servos[0].get_top() + RIGHT * 0.6, "serial 1 Mbit/s",
                     both=True, planned=True, side=LEFT)
        step(2, "2  One seam to the body", ([FadeIn(io), GrowArrow(l_io[0])], 0.8),
             ([FadeIn(sim), FadeIn(l_sim)], 0.8), ([FadeIn(servos), FadeIn(l_srv)], 0.8))

        # Step 3: the API.
        api = node(-1.3, 1.35, 2.3, "JSON-RPC API", "unix socket", CORAL)
        l_api = link(api[0].get_bottom(), loop[0].get_top() + RIGHT * 1.1)
        step(3, "3  The API", ([FadeIn(api), GrowArrow(l_api[0])], 0.8))

        # Step 4: the app.
        appf = frame(1.4, -1.7, 4.75, 2.15, "App · Python SDK", AMBER)
        runner = node(3.1, 0.1, 2.3, "Runner", "one owner per slot", AMBER)
        beh = node(3.1, -1.05, 3.0, "Behaviours", "SmoothFollow · CatGaze\nKeepDistance · MimicTilt", AMBER, h=1.0)
        l_beh = link(runner[0].get_bottom(), beh[0].get_top())
        l_run = link(runner[0].get_left(), api[0].get_right() + DOWN * 0.15, "intents ≤50 Hz", both=True, color=AMBER, side=UP)
        step(4, "4  Apps and behaviours", ([FadeIn(appf)], 0.5), ([FadeIn(runner)], 0.5),
             ([FadeIn(beh), GrowArrow(l_beh[0])], 0.6), ([FadeIn(l_run)], 0.8))

        # Step 5: perception.
        perf = frame(4.85, 1.2, 7.0, 3.55, "Perception", TEAL)
        cam = node(5.92, 3.0, 1.6, "Webcam", None, TEAL, h=0.6)
        fc = node(5.92, 1.75, 2.0, "face_cam", "OpenCV · MediaPipe", TEAL)
        l_cam = link(cam[0].get_bottom(), fc[0].get_top())
        l_fc = link(fc[0].get_bottom() + LEFT * 0.5, runner[0].get_right() + UP * 0.15, "UDP 5005 · 30/s", color=TEAL)
        dot = Dot(color=TEAL, radius=0.07).move_to(fc[0].get_bottom() + LEFT * 0.5)
        step(5, "5  Perception", ([FadeIn(perf), FadeIn(cam)], 0.6), ([FadeIn(fc), GrowArrow(l_cam[0])], 0.6),
             ([FadeIn(l_fc)], 0.6), ([MoveAlongPath(dot, Line(dot.get_center(), runner[0].get_right() + UP * 0.15))], 0.8),
             ([FadeOut(dot)], 0.2))

        # Step 6: the viewer.
        view = node(5.7, -2.75, 2.7, "Viewer", "robot · face · gaze line", INK)
        l_v1 = link(sim[0].get_right(), view[0].get_left())
        l_v2 = link(runner[0].get_bottom() + RIGHT * 0.8, view[0].get_top() + RIGHT * 0.2, "UDP 7610 · viz",
                    planned=True)
        step(6, "6  Seeing what it thinks", ([FadeIn(view), GrowArrow(l_v1[0])], 0.8), ([FadeIn(l_v2)], 0.6))

        # Step 7: the clients.
        ctl = node(-2.0, 3.0, 2.2, "gamerobotctl", "Rust CLI", INK)
        cli = node(0.9, 3.0, 2.6, "gamerobotics", "play · setup · doctor", INK)
        l_ctl = link(ctl[0].get_bottom(), api[0].get_top() + LEFT * 0.4, both=True)
        l_cli = link(cli[0].get_bottom() + LEFT * 0.6, api[0].get_top() + RIGHT * 0.5, "state, health", both=True)
        step(7, "7  The tools", ([FadeIn(ctl), FadeIn(l_ctl)], 0.7), ([FadeIn(cli), FadeIn(l_cli)], 0.7))

        # Step 8: what's planned.
        ws = node(-4.6, 1.35, 2.3, "WebSocket API", "A0 · :7700", CORAL, planned=True)
        pub = node(-5.15, -1.15, 2.2, "Publisher", "A0 · state, jitter", CORAL, planned=True)
        ctrl = node(3.1, 1.55, 2.6, "Control + status", "A0", AMBER, planned=True)
        dashb = node(-4.9, 3.0, 2.5, "Dashboard", "D0 · Tauri + web UI", INK, planned=True)
        l_ws = link(ws[0].get_bottom() + RIGHT * 0.6, loop[0].get_top() + LEFT * 1.0)
        l_pub = link(loop[0].get_bottom() + LEFT * 1.0, pub[0].get_top() + RIGHT * 0.5)
        l_ctrl = link(cli[0].get_bottom() + RIGHT * 0.9, ctrl[0].get_top() + LEFT * 0.4, both=True, planned=True)
        l_dash = link(dashb[0].get_bottom() + RIGHT * 0.3, ws[0].get_top() + RIGHT * 0.0, "WebSocket", both=True, planned=True)
        step(8, "8  Next: A0, D0, H0", ([FadeIn(ws), FadeIn(pub), FadeIn(l_ws), FadeIn(l_pub)], 1.0),
             ([FadeIn(ctrl), FadeIn(l_ctrl)], 0.8), ([FadeIn(dashb), FadeIn(l_dash)], 0.8),
             ([Indicate(servos, color=AMBER, scale_factor=1.06)], 0.8))

        # Step 9: the connection rule.
        addr = label("ws://127.0.0.1:7700", 13, AMBER, MONO).next_to(dashb, UP, buff=0.12)
        addr2 = label("ws://walker.local:7700", 13, AMBER, MONO).move_to(addr)
        clients = VGroup(dashb, ctl, cli)
        step(9, "9  Every client, by address", ([FadeIn(addr), Indicate(clients, color=AMBER, scale_factor=1.04)], 1.2),
             ([Transform(addr, addr2)], 0.9), hold=1.5)
        self.wait(1.5)


def code_block(src, size=15):
    """Python source as monospaced text on a dark card; one Text line per source line, so lines can be lit."""
    lines = VGroup(*[Text(l, font=MONO, font_size=size, color=INK, disable_ligatures=True) if l.strip()
                     else Text("x", font=MONO, font_size=size).set_opacity(0) for l in src.split("\n")])
    lines.arrange(DOWN, aligned_edge=LEFT, buff=0.09)
    cw = Text("x" * 20, font=MONO, font_size=size).width / 20  # Text drops leading spaces: indent by hand
    for line, l in zip(lines, src.split("\n")):
        line.shift(RIGHT * cw * (len(l) - len(l.lstrip(" "))))
    card = RoundedRectangle(width=lines.width + 0.6, height=lines.height + 0.5, corner_radius=0.1, stroke_color=GRID,
                            stroke_width=1.5, fill_color="#0C1218", fill_opacity=1).move_to(lines)
    return VGroup(card, lines)


class BehaviourTour(Scene):
    """The behaviour stack, narrated: how an app decides, face follow and cat gaze, and how a new
    behaviour (and a new app) is added. Steps with a "clip" in tours/behaviours.json reuse a rendered
    animation; this scene renders the others, one section each (docs/build.sh --save_sections)."""

    def construct(self):
        steps = {s["id"]: s for s in json.loads((TOUR / "tours" / "behaviours.json").read_text())["steps"]}
        manifest = json.loads((TOUR / "voice" / "behaviours" / "manifest.json").read_text())
        caption = [None]

        def step(sid, name, *anims):
            """One section: its caption, its animations, then hold until the words are done."""
            self.next_section(sid)
            spent = 0.0
            if name:
                cap = label(name, 18, AMBER, weight="BOLD").to_corner(DOWN + LEFT, buff=0.3)
                self.add(cap)
                caption[0] = cap
            for a, rt in anims:
                self.play(*a, run_time=rt)
                spent += rt
            self.wait(max(0.3, 0.3 + manifest[sid]["seconds"] + 0.6 - spent))

        def clear():
            self.remove(*self.mobjects)

        # intro
        title = label("The behaviour stack", 42, INK, weight="BOLD").move_to([0, 0.9, 0])
        sub = label("how a robot decides what to do, and how you add something new", 22, DIM).next_to(title, DOWN, buff=0.25)
        rule = VGroup(label("The daemon moves.", 30, CORAL, weight="BOLD"), label("Apps decide.", 30, AMBER, weight="BOLD")
                      ).arrange(RIGHT, buff=0.5).next_to(sub, DOWN, buff=0.8)
        step("intro", "", ([FadeIn(title), FadeIn(sub)], 1.0), ([FadeIn(rule[0])], 0.6), ([FadeIn(rule[1])], 0.6))
        clear()

        # split: daemon and app side by side
        def column(x, color, head, rows):
            r = RoundedRectangle(width=5.6, height=3.6, corner_radius=0.14, stroke_color=color, stroke_width=2.5,
                                 fill_color=color, fill_opacity=0.06).move_to([x, 0.3, 0])
            h = label(head, 26, color, weight="BOLD").next_to(r.get_top(), DOWN, buff=0.35)
            items = VGroup(*[label(t, 18, INK) for t in rows]).arrange(DOWN, aligned_edge=LEFT, buff=0.32)
            items.next_to(h, DOWN, buff=0.45)
            return VGroup(r, h, items)
        dmn = column(-3.3, CORAL, "gamerobotd", ["Rust, inside the 50 Hz tick", "owns the motion primitives:",
                                                  "   look_at · approach · tilt · joints", "Safety always applies"])
        app = column(3.3, AMBER, "an app", ["Python SDK, at its own pace", "owns the behaviours:", "   what to do, and when,",
                                             "   from what the robot sees"])
        ar = Arrow([0.45, 0.3, 0], [-0.45, 0.3, 0], buff=0, color=AMBER, stroke_width=3)
        it = label("intents", 15, AMBER, MONO).next_to(ar, UP, buff=0.12)
        step("split", "1  The daemon moves; apps decide", ([FadeIn(dmn[0]), FadeIn(dmn[1])], 0.6),
             ([FadeIn(dmn[2], lag_ratio=0.3)], 1.2), ([FadeIn(app[0]), FadeIn(app[1])], 0.6),
             ([FadeIn(app[2], lag_ratio=0.3)], 1.2), ([GrowArrow(ar), FadeIn(it)], 0.6))
        clear()

        # pipeline: camera to daemon
        xs = [-6.0, -3.6, -1.2, 1.2, 3.6, 6.0]
        specs = [("Webcam", None, TEAL), ("face_cam", "MediaPipe", TEAL), ("Percept", "what it sees", INK),
                 ("Runner", "behaviours", AMBER), ("Robot", "client", AMBER), ("gamerobotd", "Rust", CORAL)]
        boxes = [node(x, 1.2, 1.75, t, sub_, c) for x, (t, sub_, c) in zip(xs, specs)]
        links = [Arrow(boxes[i][0].get_right(), boxes[i + 1][0].get_left(), buff=0.06, stroke_width=2.2, color=DIM,
                       tip_length=0.14, max_tip_length_to_length_ratio=0.3) for i in range(5)]
        tags = [label(t, 12, DIM, MONO).next_to(links[i], UP, buff=0.5) for i, t in [(1, "UDP"), (4, "JSON-RPC")]]
        fields = VGroup(*[label(f, 15, INK, MONO) for f in ("face.eyes      where your eyes are", "face.distance  how far away",
                                                             "face.tilt      your head's tilt", "events         e.g. calibrate")]
                        ).arrange(DOWN, aligned_edge=LEFT, buff=0.16).move_to([-1.2, -1.3, 0])
        fbox = RoundedRectangle(width=fields.width + 0.5, height=fields.height + 0.4, corner_radius=0.1, stroke_color=GRID,
                                fill_color="#0C1218", fill_opacity=1).move_to(fields)
        hook = DashedLine(boxes[2][0].get_bottom(), fbox.get_top(), color=GRID, dash_length=0.08)
        intents = label("intents: look_at · approach · tilt", 13, AMBER, MONO).next_to(links[3], DOWN, buff=0.6)
        dot = Dot(color=TEAL, radius=0.08).move_to(boxes[0][0].get_center())
        step("pipeline", "2  An app is a short pipeline", ([FadeIn(boxes[0]), FadeIn(boxes[1]), GrowArrow(links[0])], 0.7),
             ([FadeIn(boxes[2]), GrowArrow(links[1]), FadeIn(tags[0])], 0.6),
             ([FadeIn(fbox), Create(hook), FadeIn(fields, lag_ratio=0.25)], 1.4),
             ([FadeIn(boxes[3]), GrowArrow(links[2])], 0.6),
             ([FadeIn(boxes[4]), GrowArrow(links[3]), FadeIn(intents)], 0.6),
             ([FadeIn(boxes[5]), GrowArrow(links[4]), FadeIn(tags[1])], 0.6),
             ([MoveAlongPath(dot, Line(boxes[0][0].get_center(), boxes[5][0].get_center()))], 2.0, ), ([FadeOut(dot)], 0.2))
        clear()

        # slots: one owner each
        head = label("three slots, one owner each", 24, INK, weight="BOLD").move_to([0, 2.9, 0])
        rows = []
        for k, (slot, who, sends, col) in enumerate([("gaze", "SmoothFollow", "look_at(face.eyes)", AMBER),
                                                      ("approach", "KeepDistance", "back off when you're close", AMBER),
                                                      ("tilt", "MimicTilt", "tilt: mirror your head", AMBER)]):
            y = 1.5 - k * 1.45
            sl = label(slot, 22, DIM, MONO).move_to([-5.2, y, 0])
            ow = node(-1.9, y, 3.0, who, None, col)
            ar = Arrow(ow[0].get_right(), [1.3, y, 0], buff=0.08, stroke_width=2.2, color=DIM, tip_length=0.14)
            se = label(sends, 16, INK, MONO).next_to(ar, RIGHT, buff=0.2)
            rows.append(VGroup(sl, ow, ar, se))
        note = label("different slots, so all three run together", 18, TEAL).move_to([0, -2.9, 0])
        step("slots", "3  Face follow: three behaviours", ([FadeIn(head)], 0.5),
             *[([FadeIn(r[0]), FadeIn(r[1])], 0.5) for r in rows],
             ([*[GrowArrow(r[2]) for r in rows], *[FadeIn(r[3]) for r in rows]], 0.9),
             ([Indicate(VGroup(*[r[1] for r in rows]), color=TEAL, scale_factor=1.04), FadeIn(note)], 1.0))
        clear()

        # new: a behaviour of your own
        src = """class Peekaboo(Behaviour):
    name = "peekaboo"
    slots = frozenset({"gaze", "tilt"})

    def start(self, previous):
        self.hidden = False

    def tick(self, seen):
        if seen.face is None:
            self.hidden = True
            return [Intent.look_at(None)]
        if self.hidden:              # you're back
            self.hidden = False
            return [Intent.look_at(seen.face.eyes, saccade=True),
                    Intent.tilt(0.3)]
        return [Intent.look_at(seen.face.eyes), Intent.tilt(0.0)]"""
        code = code_block(src, 14).move_to([-2.3, 0.35, 0])
        lines = code[1]
        table = VGroup()
        owners = {}
        for k, (slot, who) in enumerate([("gaze", "SmoothFollow"), ("approach", "KeepDistance"), ("tilt", "MimicTilt")]):
            y = 1.3 - k * 0.95
            sl = label(slot, 18, DIM, MONO).move_to([3.7, y, 0])
            ow = node(5.6, y, 2.4, who, None, AMBER, h=0.65)
            owners[slot] = ow
            table.add(sl, ow)
        th = label("owners", 15, DIM, MONO).next_to(table, UP, buff=0.3)
        run = label("Runner([Peekaboo(), SmoothFollow(), KeepDistance(), MimicTilt()], robot.notify)", 13, INK, MONO
                    ).move_to([0, -3.05, 0])
        new_g = node(5.6, 1.3, 2.4, "Peekaboo", None, TEAL, h=0.65)
        new_t = node(5.6, -0.6, 2.4, "Peekaboo", None, TEAL, h=0.65)

        def lit(i, j):
            return Indicate(VGroup(*lines[i:j]), color=TEAL, scale_factor=1.02)
        step("new", "4  A behaviour of your own", ([FadeIn(code[0]), FadeIn(lines, lag_ratio=0.05)], 1.4),
             ([lit(1, 3)], 0.9), ([FadeIn(th), FadeIn(table)], 0.6), ([lit(7, 16)], 1.4), ([lit(11, 15)], 1.0),
             ([FadeIn(run)], 0.6), ([Transform(owners["gaze"], new_g), Transform(owners["tilt"], new_t)], 0.9),
             ([Indicate(owners["approach"], color=AMBER, scale_factor=1.05)], 0.7))
        clear()

        # app: an app is a process
        app_src = """robot = Robot()                         # gamerobotd's API
robot.call("robot.enable", {"on": True})
runner = Runner([Peekaboo(), KeepDistance()], robot.notify)
while True:                             # 50 times a second
    runner.tick(percept(...))"""
        toml = ('[[process]]\nname = "app"\ncmd = [".venv-bam/bin/python", "peekaboo_app.py"]\n'
                'ready = "enabled;"')
        c1 = code_block(app_src, 14).move_to([0, 1.85, 0])
        c1t = label("peekaboo_app.py", 14, DIM, MONO).next_to(c1, UP, buff=0.12).align_to(c1, LEFT)
        c2 = code_block(toml, 14).move_to([-2.6, -1.0, 0])
        c2t = label("projects/<yours>/project.toml", 14, DIM, MONO).next_to(c2, UP, buff=0.12).align_to(c2, LEFT)
        chain = VGroup(*[node(0, 0, 1.25, n, None, c, h=0.5) for n, c in
                         (("sim", INK), ("daemon", CORAL), ("camera", TEAL), ("app", AMBER))]).arrange(DOWN, buff=0.18)
        chain.move_to([4.6, -1.1, 0])
        play = label("gamerobotics play", 14, AMBER, MONO).next_to(chain, UP, buff=0.18)
        step("app", "5  An app is a process", ([FadeIn(c1t), FadeIn(c1[0]), FadeIn(c1[1], lag_ratio=0.1)], 1.2),
             ([Indicate(c1[1][0], color=TEAL, scale_factor=1.02)], 0.8), ([Indicate(c1[1][2], color=TEAL, scale_factor=1.02)], 0.8),
             ([Indicate(VGroup(*c1[1][3:5]), color=TEAL, scale_factor=1.02)], 0.8),
             ([FadeIn(c2t), FadeIn(c2)], 0.8), ([FadeIn(play)], 0.4), ([FadeIn(chain, lag_ratio=0.4)], 1.4),
             ([Indicate(chain[3], color=AMBER, scale_factor=1.1)], 0.8))
        clear()

        # safe: what a behaviour can and can't do
        cards = VGroup()
        for t, d, c in (("Safety still applies", "limits and speeds hold,\nwhatever a behaviour asks", CORAL),
                        ("Test without a robot", "feed it Percepts,\ncheck the intents it returns", TEAL),
                        ("New kind of motion?", "a gesture is a new\ndaemon primitive, not a behaviour", AMBER)):
            r = RoundedRectangle(width=4.0, height=2.6, corner_radius=0.14, stroke_color=c, stroke_width=2.5,
                                 fill_color=c, fill_opacity=0.06)
            h = label(t, 21, c, weight="BOLD")
            b = Text(d, font=SANS, font_size=17, color=INK, line_spacing=1.1)
            VGroup(h, b).arrange(DOWN, buff=0.35).move_to(r)
            cards.add(VGroup(r, h, b))
        cards.arrange(RIGHT, buff=0.35).move_to([0, 0.3, 0])
        step("safe", "6  The guard rails", ([FadeIn(cards[0])], 0.7), ([FadeIn(cards[1])], 0.7), ([FadeIn(cards[2])], 0.7))
        clear()

        # next: what's planned
        nh = label("still to come", 24, DIM, weight="BOLD").move_to([0, 2.4, 0])
        planned = VGroup(*[node(0, 0, 6.4, t, d, INK, planned=True, h=0.85) for t, d in
                           (("gamerobotics behaviour new", "scaffold a new behaviour"),
                            ("replay testing", "run a behaviour on recorded percepts"),
                            ("packaging", "share behaviours like apps"))]).arrange(DOWN, buff=0.3).move_to([0, 0.3, 0])
        today = label("today: one small class, and the SDK", 22, TEAL, weight="BOLD").move_to([0, -2.3, 0])
        step("next", "7  What's next", ([FadeIn(nh)], 0.4), ([FadeIn(planned, lag_ratio=0.4)], 1.6), ([FadeIn(today)], 0.7))
