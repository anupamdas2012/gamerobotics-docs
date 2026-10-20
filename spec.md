# gameRobotics engine spec

The engine as built, exactly. What we're building on it, and for whom, is the product spec,
[product-spec.md](product-spec.md).

Status: current as of 2026-10-20 (gamerobotics `f642db1`, lexjr-sim `c8a0fc0`).
What exists today and exactly how it behaves. How it is put together is in
[architecture.md](architecture.md). Kept current by the `update-docs` skill.

Status keys: **shipped** (built, tested, committed), **partial**, **planned**.

## 0. Running a project: `gamerobotics` (shipped)

```sh
bin/gamerobotics play lexjr [--personality shy-puppy] [--headless] [--no-camera] [--seconds N] [--verbose]
bin/gamerobotics setup lexjr [--rebuild] [--upgrade]
bin/gamerobotics doctor lexjr [--no-camera]
bin/gamerobotics projects
```

`bin/gamerobotics` needs only uv the first time (it makes a small Python 3.12 environment for the
launcher in `.venv`).

**A project** is `projects/<name>/project.toml`:
- the daemon's robot file;
- the default personality;
- `workdir`, where the processes run;
- `[daemon]`, the binary and its arguments;
- `[[process]]` entries in start order: `name`, `cmd`, a `headless` variant, a `check` command, the
  `ready` line it prints (`@daemon` for the daemon), and `optional`;
- `[setup]`: the Python environments, their packages (pip specs, `path:` or `editable:` dirs
  relative to `workdir`) and the files to download.

LexJR's project still points at two robot descriptions, `robots/lexjr.toml` and lexjr-sim's
`robot.toml`. M1's assembly compiler will generate both.

**`play`:**
1. **Pre-start checks:** gamerobotd built; each process's environment present; no other
   gamerobotd answering; port 7600 free; the CPU's throttle; and, unless `--no-camera`, a 2 s
   camera check (`face_cam.py --check`). An error stops it with the fix; a warning does not.
2. **Starts each process in order,** waiting until it is ready: its `ready` line, or for the
   daemon, `robot.state` reading the robot (`read_errors` 0, positions present). Each has 90 s; a
   process that stops or times out ends the start, with the last lines of its log.
3. **Watches,** once a second:
   - every process is alive;
   - the daemon's tick time, skipped ticks per second (over 5 s) and read errors;
   - the camera's stats line (pictures a second, failed reads, share of frames with a face);
   - the CPU throttle, every 10 s.

   Tick time is judged on the median over the last 5 s, so one slow tick isn't a trend. A
   warning is shown once it has lasted 3 checks in a row (an error at once), and "fixed" once it
   has been gone for 5. There's also a status line every 15 s (5 s with `--verbose`).
4. **Stops everything** on Ctrl+C, `--seconds`, a closed sim window, or any process stopping: it
   disables the robot, then stops the processes in reverse order (SIGINT, then SIGTERM, then
   SIGKILL). Logs stay in `.runs/<time>/<process>.log`; the last 10 runs are kept.

**Health messages** (`python/gamerobotics/health.py`), each with its fix:

| problem | when | fix given |
|---|---|---|
| camera could not be opened | the check can't open it | camera permission for the terminal; the likely app |
| camera gave no pictures | opened, zero frames | quit the app likely holding it (OBS, Zoom, FaceTime, Teams, …) |
| camera starved | under 10 pictures a second while running (error under 3) | the same |
| CPU throttled | `pmset` CPU_Speed_Limit under 50% | let it cool; `--headless` |
| skipped ticks | more than 5% of ticks skipped | close other apps; let it cool |
| slow ticks | a tick over 75% of its period | close other apps; `--headless` |
| robot or simulator not answering | read errors | restart; check the log |
| no face | no face in frames while the camera works | sit in front of it, lit |

macOS does not say which process holds the camera, so the app named is the running one from a
known list, not a certainty.

**`setup`:**
- builds gamerobotd if it's missing (`--rebuild` forces it);
- creates each environment with uv, installing its packages if the environment is new
  (`--upgrade` reinstalls them);
- downloads missing files.

It only does what is missing, and says what it skips. **`doctor`** runs the pre-start checks only.

**Personalities** (`projects/<name>/personalities/*.toml`): a name, `gaze_behaviour = "smooth" |
"cat"`, and any of lexjr-sim `robot.toml`'s sections (`[cat_gaze]`, `[lean]`, `[tilt]`), laid
over it key by key. A key that would replace a whole section is refused. LexJR's: Curious Cat,
Shy Puppy, Attentive Owl (the presets in product-spec.md).

## 1. Robot description (shipped)

A robot is a TOML file, `robots/<name>.toml`. Angles are in degrees in the file and radians
everywhere else. The joint order in the file is the order on every wire.

```toml
name = "lexjr"
control_hz = 50

[[joint]]
name = "torso_yaw"
limit_deg = [-57, 57]           # the mechanism's range less a 3 deg margin
max_speed_dps = 183.33333333333334  # servo 550 deg/s through the torso's 3:1 gear
home_deg = 0                    # optional, default 0

[motion]                        # optional: enables robot.look_at and robot.lean
chain = "lexjr.chain.json"      # native kinematics, exported from the MJCF
config = "lexjr.motion.json"    # MotionCore's parameters
mjcf = "../../lexjr-sim/lexjr/scene.xml"   # for --kinematics mujoco
head_body = "hd_1910_head_asm"
eye_mesh = "hd_1910_eye"
```

A file is refused if a joint is listed twice, a limit has `lo >= hi`, the home is outside the
limits, or a speed is not positive. `[motion]` is refused if the chain's joints are not the
robot's, in order.

LexJR: torso_yaw ±57°, neck_yaw ±87°, neck_pitch ±87°, head_pitch ±87°, head_yaw ±87.0002°,
head_roll ±22°; 550°/s except the torso, 183.3°/s.

## 2. gamerobotd (shipped)

```sh
gamerobotd [--robot robots/lexjr.toml] [--io fake|sim] [--sim 127.0.0.1:7600]
           [--sim-timeout-ms 2000] [--socket /tmp/gamerobotd.sock] [--kinematics native|mujoco]
```

- Runs the control loop at `control_hz` and serves the API on the socket.
- Refuses to start beside another gamerobotd answering on the same socket; removes a stale one.
- Starts with torque untouched and writes nothing until enabled.
- `--kinematics mujoco` needs a build with `--features mujoco`; otherwise it exits with a message
  saying so.

## 3. API (shipped)

JSON-RPC 2.0, one object per line, on a unix socket. Radians, metres, seconds.

**Intents** are notifications: no `id`, no reply, and the newest one wins.

| method | params | effect |
|---|---|---|
| `robot.joints` | `{"targets": {"neck_pitch": 0.3, ...}}` | joints mode; named joints move toward these angles; others keep their goal |
| `robot.look_at` | `{"target": [x, y, z], "saccade": false}` or `{"target": null}` | gaze mode; look at a world point (z up, robot facing +y at rest), or return to rest. `saccade: true` jumps the head there instead of gliding (§6) |
| `robot.lean` | `{"amount": 0.2}` | lean in (+) or back (−), rad of the lean joint, eased and clipped |
| `robot.tilt` | `{"amount": -0.15}` | tilt the head about its line of sight, rad, + with the robot's right ear down, eased and clipped; the gaze stays on the target |

Intents are dropped while the robot is disabled, and gaze intents on a robot without `[motion]`
are dropped and counted. Non-finite values are dropped.

**Requests** are answered.

| method | params | result |
|---|---|---|
| `robot.info` | — | robot name, rate, joints (limits, speeds, home), daemon version, io, kinematics |
| `robot.enable` | `{"on": true}` | torque on, hold the present pose, joints mode; refused if this tick's read failed |
| `robot.state` | — | the latest state frame |
| `robot.subscribe` | `{"hz": 10}` | state frames pushed on this connection, at most the control rate; dropped if the client lags |

Sending an intent with an `id` is an error (`-32600`). An unknown method is `-32601`, bad params
`-32602`, and a refusal by the robot `-32000`.

**State frame:** `t`, `tick`, `enabled`, `mode` (`joints` | `gaze`), `look_at`, `positions`,
`velocities` (`null` when this tick's read failed), `targets` (what was written), `goals`,
`missed_ticks`, `read_errors`, `tick_time`.

## 4. gamerobotctl (shipped)

`info`, `state`, `enable`, `disable`, `joints name=deg ...` (degrees), `watch [--hz 5]`.

## 5. Safety (shipped)

Every target passes through Safety before it is written:
- A non-finite target holds the last command, and the refusal is counted.
- Each target is clamped to the joint's limits from the robot file.
- Each target is clamped to the joint's `max_speed × period` from the last command.
- Enabling anchors the speed limit at the present pose.

## 6. Gaze and lean: MotionCore (shipped)

`robot.look_at` hands the joint goals to MotionCore, which runs inside the tick:

1. **Body goal:** aim the whole chain. It takes a new goal only when the goal moves more than the
   8° deadband, so small glances are the head's alone.
2. **Body joints follow as springs:** torso 0.9 Hz at ζ 0.75; neck yaw and pitch 1.4 Hz at ζ 0.8.
3. **Layers:** idle oscillators (neck pitch 1.5° at 0.22 Hz, torso 1.0° at 0.09 Hz), and the lean
   (its own spring, 0.8 Hz, ζ 1.0, at most 30°). The tilt (`robot.tilt`, its own spring, 2 Hz,
   ζ 1.0, at most 20°) becomes the solver's roll target.
4. **Head goal:** aim the head joints against the commanded body. The head follows a 5 Hz spring
   (ζ 1.0), so it leads, then counter-rotates as the body arrives.
5. **Saccade** (`look_at` with `saccade: true`): instead of its spring, the head follows a quintic
   from its present position and velocity to the goal, arriving at rest, in
   `saccade_base_ms + saccade_ms_per_deg × travel` (60 ms + 2.5 ms/°: 4° in 70 ms, 40° in 160 ms,
   peak 470°/s), then holds; the spring resumes after. Starting from the present velocity keeps a
   saccade fired mid-move, or retargeted mid-saccade, free of a velocity jump.
6. **Trim:** once the head is still (below 20°/s, commanded and measured), integrate the measured
   gaze error (ki 3/s, at most 6°). This takes out the servos' gravity sag.
7. **Limits** (model range less 3°), then each joint's speed.

**The aim solver** is weighted damped least squares with task priority: point the gaze (2 DOF),
then hold the head's tilt about the gaze at the roll target (soft; 0 is a level horizon, + is the
right ear down), then stay near the posture in the null space. Joints are
weighted 1.0 to 4.0 from the torso to head roll. A joint pinned at a limit drops out. Each tick
solves warm with 6 iterations, and from the posture with 16 when the warm solve misses by more
than 1° and every 5th tick; it keeps the better result.

**Mode switches are continuous:** entering gaze mode starts MotionCore from the last goals.

**Kinematics:** native chain by default; MuJoCo as the fallback.

**Cost:** 30 us median a tick native, 54 us with MuJoCo (p99 75 / 158 us).

## 7. Simulator link: body protocol v1 (shipped)

TCP, one JSON object per line, one request and one reply each.

```jsonc
→ {"op":"hello","protocol":1,"joints":["torso_yaw",...],"dt":0.02}
← {"protocol":1}                     // or {"protocol":1,"error":"joint order differs: ..."}
→ {"op":"read"}                      // the simulator steps one dt, then answers
← {"positions":[...],"velocities":[...],"imu":null}
→ {"op":"write","targets":[...]}     ← {}
→ {"op":"torque","on":true}          ← {}
```

The simulator refuses a daemon whose joint names or period differ. It reports in the robot's
units, and its own servo zeros, ratios and gears stay inside it. A dropped connection is one
failed tick and a reconnect on the next.

**LexJR body** (`lexjr-sim/body_server.py`):
- BAM servo models (HD-1910 / STS3215: 7.4 V, firmware P 5, 0.94 N·m stall).
- 20 ms command latency (`robot.toml [sim] goal_delay_ms`).
- The torso's 3:1 gear.
- A viewer with a front "call" view and a side camera (`]`).
- Survives the daemon disconnecting.
- Torque off is not simulated: the servos keep holding.

## 8. Face follow (shipped)

**`face_cam.py`** (lexjr-sim, its own venv `.venv-cam`):
- Uses the MediaPipe Face Landmarker. It smooths 160 of the 478 landmarks with a One-Euro filter
  and sends them with the face box over UDP 5005 (~3.7 kB).
- The preview is mirrored; `c` sets the normal distance; `q` quits.
- `--detector box` uses BlazeFace (a box only); `--hfov` (default 60°) sets the camera's field of view.

**Geometry** (`lexjr_ctl/face.py`):
- The webcam stands in for the robot's eye at its rest posture.
- Distance comes from the iris (11.7 mm across, the larger of its two spans).
- The face is shown at `[face] distance_scale` (0.65) of its real distance, life-size and along the line of sight.
- The robot looks between the eyes.
- A lost face holds for 1 s, then eases home.

**Proxemics** (`lexjr-sim robot.toml [lean]`): your distance over the first second is normal. Beyond a 2 cm deadband the robot
leans 1.5° per cm, in when you move away and back when you come closer, up to 30°.

**Mimic** (`lexjr-sim robot.toml [tilt]`):
- Your head tilt is the slope of the line between your eyes in the image (`Mesh.roll`; shown in
  the camera preview).
- Beyond a 3° deadband, the robot tilts by gain 1.0 × that, up to 20° (LexJR's head_roll range is
  ±22° after the margin).
- **Mirrored**, face to face: you tilt toward your right shoulder, it tilts toward its left, so on
  screen it reads as copying you (`mirror = false` copies literally).
- No face: upright. The box detector (`--detector box`) has no landmarks, so no tilt.
- Measured end to end on BAM physics: your 15° tilt gives the robot 11.7–11.8°, the other way,
  with the gaze within 0.6°.

**`face_follow.py`** is a behaviour Runner (§8a) over LexJR's four behaviours:
- gaze: `SmoothFollow` (the default) or `CatGaze` (`--gaze cat`); **`m` in the camera preview
  switches between them live**, with a half-second glide;
- lean: `KeepDistance` (Proxemics); tilt: `MimicTilt` (Mimic).
- Sends `robot.look_at`, `robot.lean` and `robot.tilt` at 50 Hz. `--verbose` prints the cat's
  state changes; `--cat-seed` makes its choices repeatable.
- Sends the target and face mesh to the viewer (UDP 7610); the viewer draws the face wireframe
  and the gaze line from the robot's actual eye.

```sh
cd lexjr-sim && .venv-bam/bin/mjpython body_server.py
../gamerobotics/target/release/gamerobotd --io sim
.venv-cam/bin/python face_cam.py
.venv-bam/bin/python face_follow.py
```

## 8a. Behaviours and the app SDK (shipped)

**The Python SDK** (`gamerobotics/python`, package `gamerobotics`, no dependencies, Python 3.10+):
- `gamerobotics.client.Robot`: `call(method, params)` for requests, `notify(method, params)` for intents.
- `gamerobotics.behaviours`:
  - `Behaviour`: `name`, `slots`, `start(previous)` (called on taking over, with the last
    intent per slot), `tick(seen) -> [Intent]`.
  - `Intent.look_at(target, saccade=False)`, `Intent.lean(amount)`, `Intent.tilt(amount)`.
  - `Percept`: `t`, `face` (`Face`: `eyes`, `left_eye`, `right_eye`, `mouth`, `distance`, `tilt`),
    `eye` (the robot's eye at rest), `home`, `events` (e.g. `"calibrate"`).
  - `Runner(behaviours, send, handover_s=0.5)`: slots `gaze`, `lean`, `tilt`, each owned by one
    behaviour (at the start, the first in the list that wants it); `select(name)` and
    `cycle(slot)` switch live; intents for slots a behaviour does not own are dropped. When the
    gaze changes hands, the new owner starts from the last target and the runner blends the two
    targets along a minimum-jerk curve for `handover_s`, holding saccades back.

**LexJR's behaviours** (`lexjr-sim/lexjr_ctl/behaviours.py`):

| behaviour | slot | what it does |
|---|---|---|
| `SmoothFollow` | gaze | look at your face, gliding after it; lost, ease home (0.5 s) |
| `CatGaze` | gaze | hold, decide, saccade, track, dart (below) |
| `KeepDistance` | lean | Proxemics as a behaviour |
| `MimicTilt` | tilt | Mimic as a behaviour |

**CatGaze** (`lexjr-sim robot.toml [cat_gaze]`), an animal's attention:
- **stare:** hold the fixation, even as your face drifts. When your face moves more than
  `cone_deg` (8°) from where the cat locked on to it, wait `react_s` (0.15–0.45 s, random), then
  saccade to it. The cone is measured from the face, not from the fixation, so a dart to your
  mouth does not count as your face moving.
- **track:** follow your face for `track_s` (1–2.5 s).
- **dart:** `darts` (3–7) saccades to your eyes (`eye_weight` 0.8) or mouth, with up to
  `jitter_deg` (1.5°) of scatter, every `dart_every_s` (0.35–0.9 s); then **stare** for
  `stare_s` (1.5–4 s), then dart again.
- **idle:** no face: drift home; when one appears, react, then saccade to it.

Tests: `cd gamerobotics/python && python3 -m unittest discover -s tests` (the runner), and
`lexjr-sim/tests/test_behaviours.py` (each behaviour, the LexJR set).

Tried live with the webcam (2026-10-19): CatGaze found the face in 0.26 s, then cycled through
track, dart and stare (164 state changes in 6.8 minutes), with lean and tilt alongside.

## 9. Verification (shipped)

| suite | what | where |
|---|---|---|
| unit | model parsing, Safety, Controller rules, body protocol client, API envelopes | `cargo test` |
| golden | FK + Jacobian on 500 poses (tolerance 1e-12), aim on 300 cases including roll targets (1e-9 rad), MotionCore replays over 4,850 ticks including tilt, lean and 48 saccades (some fired mid-move) on perfect servos and BAM physics (1e-9 rad), on both kinematics backends | `crates/gr-motion/tests/golden.rs` |
| control path | the golden replay through Controller + Safety + FakeIo; limits no tighter than the motion's; mode switches without jumps; tilt kept across the mode switch, gaze held while tilted | `crates/gr-control/tests/gaze.rs` |
| Python | ServoMap, aim, MotionCore (incl. tilt and saccades) on NullBus and SimBus, face geometry and tilt, Proxemics, Mimic, the behaviours | `lexjr-sim/tests` |
| SDK | the behaviour Runner: slots, switching, handover | `python/tests` |

Worst differences found: 2.4e-15 for kinematics, 3.9e-11 rad for the solver, 2.0e-11 rad for
MotionCore. All eight planted bugs fail the harness (two for tilt: the roll target ignored, the
tilt not eased; one for saccades: restarting from rest instead of the present velocity).

To regenerate and re-check: `scripts/golden.sh`.

## 10. Known limits

- **Reaction time on the simulated servos** is set by the servos: 20 ms latency, P gain 5, about
  550°/s. Faster springs give about 8% on short glances and overshoot on big turns (measured
  2026-10-19, not adopted).
- **A throttled laptop** (`pmset -g therm` CPU_Speed_Limit below about 40) runs the simulator below
  real time. Results are unchanged; the run is just slower. With the whole demo running (simulator
  and viewer, daemon, face_cam with preview, face_follow) on the Intel MacBook, the CPU throttles
  to 20% within minutes. Measured 2026-10-19: ticks rise from about 4 ms to 10–50 ms, and 6–22%
  of ticks are missed, so saccades and darts look slow. Moving the simulator to another machine
  is the real fix; `face_cam --no-preview` helps a little.
- **The webcam is exclusive in practice.** With OBS running, `face_cam` got only occasional
  frames (126 failed reads in 143 s) and never a face. Quit other camera apps first. A camera
  check: 150 of 150 frames read, a face in all of them, once OBS was closed.

## 11. Planned

- **FeetechIo:** sync read and write in ticks over rustypot, one transaction a tick; torque; IDs,
  zeros and directions from the robot file.
- **Policies:** an ONNX runner, an observation builder from a layout in the robot file, and
  loading microduck's manifest (schema 2) and 61/14 policies.
- **A Reachy Mini bridge** (Zenoh to JSON-RPC).
- **For third-party behaviours:** a scaffold (`gamerobotics behaviour new`), replay testing on
  recorded percepts, packaging; a percept service so perception is not tied to one app.
