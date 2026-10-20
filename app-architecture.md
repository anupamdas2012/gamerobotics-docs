# gameRobotics app architecture

Status: current as of 2026-10-19 (gamerobotics `ba84104`, lexjr-sim `93a7fb0`).
How an app is built on gamerobotd: the layers, the SDK, and how a behaviour is written, with face
follow and cat gaze as the worked examples. The daemon itself is in
[architecture.md](architecture.md); exact behaviour and settings are in [spec.md](spec.md) §8 and
§8a. Kept current by the `update-docs` skill.

## The split

**The daemon moves; apps decide.**

| | gamerobotd (the daemon) | an app |
|---|---|---|
| language | Rust | any; Python with the SDK |
| runs | inside the 50 Hz tick | outside it, at its own rate |
| owns | **motion primitives**: `look_at` (glide or saccade), `lean`, `tilt`, `joints` | **behaviours**: what to do and when, from what the robot sees |
| knows about | joints, limits, kinematics, timing | faces, moods, games, people |
| safety | always applies Safety | cannot bypass it |

A primitive belongs in the daemon when it says *how* the body moves and needs the tick's timing
to look right: a saccade's 70–160 ms quintic, the head's spring, the gravity trim. A behaviour
belongs in an app when it decides *what* and *when*: where a face is, when to glance, whether to
lean. Cat gaze shows the line: *when* to jump is the app's choice (a random reaction time,
attention cone, darts), but *the jump itself* is the daemon's saccade.

**The connection rule:** an app and any front end reach the robot through APIs by address,
never by being on the same machine. See [architecture.md](architecture.md), "The connection
rule".

## Layers inside an app

```text
  sensor          perception           percept         behaviours (plugins)         intents          daemon
 ┌───────┐   ┌──────────────────┐   ┌──────────┐   ┌─────────────────────────┐   ┌──────────┐   ┌────────────┐
 │webcam │──►│ face_cam.py      │──►│ Percept  │──►│ Runner                  │──►│ Robot    │──►│ gamerobotd │
 │       │UDP│ MediaPipe → 160  │   │ face,    │   │  gaze: SmoothFollow     │   │ client   │   │ look_at    │
 └───────┘   │ landmarks        │   │ distance,│   │        or CatGaze  [m]  │   │ JSON-RPC │   │ lean, tilt │
             │ FaceTarget →     │   │ tilt,    │   │  lean: KeepDistance     │   │ notify   │   │ MotionCore │
             │ world points     │   │ eyes,    │   │  tilt: MimicTilt        │   └──────────┘   │ Safety     │
             └──────────────────┘   │ mouth    │   └─────────────────────────┘                  └────────────┘
                lexjr-sim            SDK type         SDK runner + LexJR plugins       SDK            Rust
```

| layer | where | what it does |
|---|---|---|
| perception | `lexjr-sim/face_cam.py`, `lexjr_ctl/face.py` | the camera, MediaPipe, and turning landmarks into world points (FaceTarget) |
| percept | `gamerobotics.behaviours.Percept`, built by `lexjr_ctl.behaviours.percept()` | what the robot sees this tick, in robot terms: the face's eyes, eye and mouth points, real distance, head tilt, plus one-shot events |
| behaviours | `lexjr_ctl/behaviours.py` (LexJR's), or your own | each turns a percept into intents for the slots it owns |
| runner | `gamerobotics.behaviours.Runner` | gives each slot one owner, switches owners live, glides gaze handovers, drops intents for slots a behaviour does not own |
| client | `gamerobotics.client.Robot` | sends intents to gamerobotd as JSON-RPC notifications |

The **SDK** (`gamerobotics/python`, package `gamerobotics`, no dependencies) is the robot-neutral
part: `Behaviour`, `Intent`, `Percept`, `Face`, `Runner`, `Robot`. **LexJR's app**
(`lexjr-sim`) is one user of it: its perception and its four behaviours.

## Slots, owners and handover

There are three slots, one per motion primitive a behaviour can drive:

| slot | intent | primitive in the daemon |
|---|---|---|
| `gaze` | `Intent.look_at(target, saccade=False)` | MotionCore's whole-chain and head aim; spring or saccade |
| `lean` | `Intent.lean(amount)` | the lean layer on `neck_pitch` |
| `tilt` | `Intent.tilt(amount)` | the head's roll target about its gaze |

- **One owner per slot.** At the start, each slot goes to the first behaviour in the list that
  wants it. `Runner.select(name)` gives a behaviour all its slots; `Runner.cycle(slot)` moves a
  slot to the next behaviour that wants it.
- **Sharing and replacing.** Behaviours that want different slots run together (smooth follow
  looks while keep-distance leans). Behaviours that want the same slot replace each other
  (smooth follow or cat gaze).
- **Dropped intents.** A behaviour may return an intent for a slot it does not own; the runner
  drops it, so a behaviour cannot take over a slot by accident.
- **Handover.** When the gaze slot changes hands, the new owner's `start(previous)` gets the last
  intent per slot, so it can begin where the robot is looking. For the next 0.5 s the runner
  blends the outgoing and incoming targets along a minimum-jerk curve, with saccades held back.
  Lean and tilt need no blend: the daemon eases both.

## A tick of the app

At 50 Hz, `face_follow.py`:

1. **Takes in** the camera's messages (`FaceTarget`), including the preview's keys: `c`
   (calibrate the distance) becomes an event; `m` cycles the gaze slot.
2. **Builds** the `Percept`. A face counts as seen until 1 s after it was last detected.
3. **Runs** the owners: each returns intents.
4. **Sends** the winning intents: `robot.look_at`, `robot.lean`, `robot.tilt`.
5. **Draws:** sends the gaze target and the face mesh to the simulator's viewer (visualization only).

## Example 1: face follow

Face follow is three behaviours, one per slot:

| behaviour | slot | from the percept | sends |
|---|---|---|---|
| `SmoothFollow` | gaze | `face.eyes` | `look_at(face.eyes)` every tick; lost, a target easing home (0.5 s) |
| `KeepDistance` | lean | `face.distance`, the `calibrate` event | `lean(a)`: 1.5° per cm beyond 2 cm from your normal distance, ≤ 30° |
| `MimicTilt` | tilt | `face.tilt` | `tilt(−gain × tilt)`: mirrored, beyond 3°, ≤ 20° |

`SmoothFollow` is the simplest possible gaze behaviour (abridged: the real one in
`lexjr_ctl/behaviours.py` also keeps the time of the last tick for `dt`, and starts from the
previous gaze target):

```python
class SmoothFollow(Behaviour):
    name = "smooth"
    slots = frozenset({"gaze"})

    def tick(self, seen):
        if seen.face is not None:
            self.point = np.asarray(seen.face.eyes, float)
        else:  # lost: ease the target home
            self.point += (np.asarray(seen.home) - self.point) * (1 - math.exp(-dt / self.ease))
        return [Intent.look_at(tuple(self.point))]
```

Every tick it says "look there", and the daemon's head spring turns that into a glide.

## Example 2: cat gaze

`CatGaze` owns the same slot, `gaze`, so it replaces smooth follow rather than running beside it.
It is a state machine that decides *when* to look and uses the daemon's saccade for *how*:

```text
              face appears (react 0.15–0.45 s)
     ┌──────┐ ─────────────────────────────────► ┌───────┐
     │ idle │                                    │ track │  follow the face, 1–2.5 s
     └──────┘ ◄──────── face lost ─────────────  └───────┘
                                                     │ timer
       face moves > 8° from where it locked on       ▼
       (react 0.15–0.45 s, then saccade) ◄──── ┌──────┐  3–7 saccades to an eye (80%)
                     ▲                         │ dart │  or the mouth, ±1.5°, every 0.35–0.9 s
                     │                         └──────┘
                     │                             │ darts done
                     │                             ▼
                     └──────────────────────── ┌───────┐
                                               │ stare │  hold the last dart, 1.5–4 s
                                               └───────┘  then dart again
```

What it sends:

| state | intent each tick |
|---|---|
| idle | `look_at(point drifting home)` |
| deciding (face left the cone) | `look_at(fixation)`, held, until the reaction time is up |
| the jump to the face | `look_at(face.eyes, saccade=True)` once, then **track** |
| track | `look_at(face.eyes)` (smooth pursuit) |
| each dart | `look_at(feature + scatter, saccade=True)` once, then held |
| stare | `look_at(fixation)` |

Two details that make it work:
- **The attention cone is anchored on the face,** not on the fixation. A dart to the mouth is
  about 10° below the eyes. Measured from the fixation, that looks like the face moving, and the
  cat jumped straight back; the tests caught it.
- **The saccade starts from the head's present velocity** (in the daemon), so a dart fired while
  the head is still moving does not jerk.

Its settings are `[cat_gaze]` in `lexjr-sim/robot.toml`; `--cat-seed` makes a run repeatable,
and `--verbose` prints its state changes.

## Switching between them

`face_follow.py --gaze smooth|cat` picks the starting gaze behaviour; `m` in the camera preview
switches live:

1. `Runner.cycle("gaze")` makes the other one the owner.
2. The new owner's `start()` begins from the last gaze target. Cat gaze starts by **staring**
   where the robot already looks, so nothing moves until it decides to.
3. For 0.5 s the runner blends the targets, saccades held back. Cat to smooth glides to your face;
   smooth to cat holds still.
4. Lean and tilt never stop: their owners did not change.

## Writing your own behaviour

```python
from gamerobotics.behaviours import Behaviour, Intent, Runner
from gamerobotics.client import Robot

class Peekaboo(Behaviour):
    name = "peekaboo"
    slots = frozenset({"gaze", "tilt"})

    def start(self, previous):
        self.hidden = False

    def tick(self, seen):
        if seen.face is None:
            self.hidden = True
            return [Intent.look_at(None), Intent.tilt(0.0)]
        if self.hidden:  # you're back
            self.hidden = False
            return [Intent.look_at(seen.face.eyes, saccade=True), Intent.tilt(0.3)]
        return [Intent.look_at(seen.face.eyes), Intent.tilt(0.0)]
```

Add it to the runner's list in `face_follow.py` (or your own app), or `select("peekaboo")` it
live. It owns `gaze` and `tilt`; `KeepDistance` keeps the lean.

- **Test it without a robot:** feed it `Percept`s and check the intents, as
  `lexjr-sim/tests/test_behaviours.py` does for cat gaze.
- **Run it** against the simulator: the four processes in [spec.md](spec.md) §8.
- **What it cannot do:** move the robot beyond its limits or speeds, or move it before it is
  enabled. Safety in the daemon applies to every intent.
- **When you need a new kind of motion** (a gesture, say), that is a new daemon primitive, not a
  behaviour. Ask for it.

## Not built yet

- A scaffold (`gamerobotics behaviour new`), replay testing on recorded percepts, and packaging.
- A percept service, so perception is not tied to one app.
- Choosing behaviours by context (cat gaze while you're quiet, smooth while you talk): an
  arbiter on top of the runner.

See [ideas/behaviour-interface.md](ideas/behaviour-interface.md).
