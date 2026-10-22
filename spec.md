# gameRobotics engine spec

The engine as built, exactly. What we're building on it, and for whom, is the product spec,
[product-spec.md](product-spec.md).

Status: current as of 2026-10-22 (gamerobotics `5c506b7`, lexjr-sim `4b57cbf`).
What exists today and exactly how it behaves. How it is put together is in
[architecture.md](architecture.md). Kept current by the `update-docs` skill.

Status keys: **shipped** (built, tested, committed), **partial**, **planned**.

## 0. Running a project: `gamerobotics` (shipped)

```sh
bin/gamerobotics play lexjr [--personality shy-puppy] [--headless] [--no-camera] [--seconds N] [--verbose]
bin/gamerobotics play pantilt                 # the Pan Tilt Robot Test (§1a)
bin/gamerobotics play rover                   # the Rover Robot Test (§1b)
bin/gamerobotics play roverpt                 # the rover with the pan tilt on top (§1c)
bin/gamerobotics play lexjr --mocap-record mocap/me.jsonl   # capture your face as it runs (§8b)
bin/gamerobotics play roverpt --mocap mocap/me.jsonl        # play it back, no camera (§8b)
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
  relative to `workdir`) and the files to download;
- a camera process's `replay` (the command `--mocap FILE` runs in its place, with the file and
  `--loop`; named "mocap", so the camera's health checks are off) and `capture` (added to its
  command by `--mocap-record FILE`, `{file}` filled in);
- `[env]`: environment variables set for every process the project starts (the daemon, its
  `[[process]]` entries and the camera check), on top of the launcher's own. The pan tilt's
  sets `LEXJR_ROBOT = "pantilt/robot.toml"`, which picks lexjr-sim's robot file (§1a).

Projects: `lexjr`, `pantilt`, `rover` and `roverpt`. Each still points at two robot descriptions, the daemon's
`robots/<name>.toml` and lexjr-sim's robot file. M1's assembly compiler will generate both.

**`play`:**
1. **Pre-start checks:** gamerobotd built; each process's environment present; no other
   gamerobotd answering; port 7600 free; the CPU's throttle; and, unless `--no-camera` or
   `--mocap`, a 2 s camera check (`face_cam.py --check`). `--mocap` checks the file is a capture. An error stops it with the fix; a warning does not.
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
"cat"`, and any of lexjr-sim `robot.toml`'s sections (`[cat_gaze]`, `[keep_distance]`, `[tilt]`),
laid over it key by key. Their units are the behaviour's, not a body's: `[keep_distance] gain` is
metres of approach per metre your distance changes, the same on any robot (Shy Puppy 0.342,
Attentive Owl 0.171; LexJR's default 0.256). A key that would replace a whole section is refused. LexJR's: Curious Cat,
Shy Puppy, Attentive Owl (the presets in product-spec.md).

## 1. Robot description (shipped)

A robot is a TOML file, `robots/<name>.toml`. Angles are in degrees in the file and radians
everywhere else. The joint order in the file is the order on every wire. A joint is in **position**
mode (the default: its target an angle) or **velocity** mode (a wheel: its target a speed, its
angle unbounded).

```toml
name = "lexjr"
control_hz = 50

[[joint]]
name = "torso_yaw"
limit_deg = [-57, 57]           # the mechanism's range less a 3 deg margin
max_speed_dps = 183.33333333333334  # servo 550 deg/s through the torso's 3:1 gear
home_deg = 0                    # optional, default 0

[motion]                        # optional: enables robot.look_at, robot.approach and robot.tilt
chain = "lexjr.chain.json"      # native kinematics, exported from the MJCF
config = "lexjr.motion.json"    # MotionCore's parameters
mjcf = "../../lexjr-sim/lexjr/scene.xml"   # for --kinematics mujoco
head_body = "hd_1910_head_asm"
eye_mesh = "hd_1910_eye"
```

A wheeled robot's joints and base (`robots/rover.toml`):

```toml
[[joint]]
name = "wheel_left"
mode = "velocity"               # a wheel: no limit_deg, no home_deg
max_speed_dps = 550
max_accel_dps2 = 2200           # optional, default 4 x max_speed_dps

[base]                          # a mobile robot: a differential drive on two velocity joints
drive = "diff"
left = "wheel_left"
right = "wheel_right"
wheel_radius_m = 0.030
track_m = 0.065                 # between the wheels' contact lines
left_sign = 1                   # +1 if that wheel turning + drives its side forward
right_sign = -1
```

A file is refused if a joint is listed twice, a position joint has no limit, a limit has
`lo >= hi`, the home is outside the limits, a speed is not positive, a velocity joint has a limit
or a home, or a `[base]` names a wheel that is not a velocity joint. `[motion]` is refused if the
chain's joints are not the robot's gaze chain, in order: with a `[base]`, `base_x`, `base_y`
(metres) and `base_yaw` (rad, + turned left, 0 facing +y), then the position joints; without one,
every joint.

LexJR: torso_yaw ±57°, neck_yaw ±87°, neck_pitch ±87°, head_pitch ±87°, head_yaw ±87.0002°,
head_roll ±22°; 550°/s except the torso, 183.3°/s.

Pan tilt (`robots/pantilt.toml`): pan ±87°, tilt −87° (up) to +37° (down); 550°/s.

Rover (`robots/rover.toml`): two wheels, 550°/s and 2,200°/s² (550°/s is what lexjr-sim assumes
for the HD-1910, not measured); at 30 mm that is 0.29 m/s ahead or 8.9 rad/s turning on the spot.

Rover pan tilt (`robots/roverpt.toml`): the rover's two wheels and `[base]`, then pan ±87° and tilt
−87° to +37°, 550°/s; its gaze chain is `base_x`, `base_y`, `base_yaw`, `pan`, `tilt`.

## 1a. More than one robot: the Pan Tilt Robot Test (shipped)

A second robot runs on the same gamerobotd binary, MotionCore and face-follow behaviours
(SmoothFollow, CatGaze) as LexJR, with only its files different. It was built on 2026-10-20 to
test that claim. No daemon or solver code changed for it.

**The robot.** Two of LexJR's servos, its SwivelBracket and its camera, on a new base plate and
camera yoke (Onshape LexJR-PT, branch `pan-tilt-test`, assembly "Pan Tilt Robot Test"):
- base plate + HD-1910-Single (pan, about world −z, + turns right);
- SwivelBracket on its horn;
- HD-1910 on its side (tilt, about world −x, + looks down);
- camera yoke with the eye and lens, facing +y.

Tilt stops at +40° in the CAD. The lens meets the bracket at about +47°, and the eye meets the
pan servo at +45° near pan ±60–90° (lexjr-sim `tools/clearance.py`). Tilting up is clear to −90°.

**Its files:**

| file | what |
|---|---|
| `robots/pantilt.toml`, `.chain.json`, `.motion.json` | the daemon's robot file and its exported chain and MotionCore parameters |
| `projects/pantilt/project.toml` | `gamerobotics play pantilt`; `[env] LEXJR_ROBOT` |
| lexjr-sim `pantilt/robot.toml`, `robot.xml`, `scene.xml` | the sim's and the app's robot file; the MJCF exported by `./run.sh pantilt` |
| `crates/gr-motion/tests/golden/pantilt/` | its golden data |

**lexjr-sim's robot file** gains `[robot]`: `name`, `model` (relative to the lexjr-sim root),
`head_body`, `eye_mesh`, `body_joints` and `head_joints`. Body and head joints together must be
the `[[servo]]` joints. A file without `[robot]` is LexJR. The environment variable
`LEXJR_ROBOT` (a path relative to the lexjr-sim root; default `robot.toml`) picks the file for
the whole process: `body_server.py`, `face_follow.py`, `sim_bam.py` and `tools/export_golden.py`.

**What a robot may leave out.** The pan tilt has no body joints (both joints aim the head), no
`[approach]` and no `[tilt]`. MotionCore (Python and Rust) runs with an empty body. The app starts
no KeepDistance or MimicTilt without those sections, and `robot.approach` and `robot.tilt` do
nothing.

**Measured** with `scripts/trial.py` (§9) on 2026-10-20 (Intel MacBook, release, CPU throttled
to about 33%):

| robot, gaze | limits | fastest target | missed ticks | tick p99 | gaze wobble, held face | gaze error, held face |
|---|---|---|---|---|---|---|
| pan tilt, smooth | within | 550°/s | 0 | 4.6 ms | ≤ 0.80° | ≤ 0.83° |
| pan tilt, cat | within | 550°/s | 0 | 5.0 ms | ≤ 1.03° | ≤ 1.28° |
| LexJR, smooth (5 s holds) | within | 550°/s | 0 | 7.0 ms | ≤ 0.43° | ≤ 0.60° |
| LexJR, cat (5 s holds) | within | 550°/s | 0 | 7.8 ms | ≤ 1.35° | ≤ 0.78° |

Pushed past its limits, the pan tilt holds at pan ±85–87° and tilt −87° / +36.7°, with the gaze
wobbling by at most 1.0°. LexJR needs about 5 s to settle on a close face in a corner, because
its body stages lag. The pan tilt settles within 3 s.

## 1b. A mobile robot: the Rover Robot Test (shipped)

A third robot, built on 2026-10-21: two of LexJR's servos in wheel mode and its camera on a round
chassis. The same daemon, MotionCore and behaviours (SmoothFollow, CatGaze, KeepDistance) turn it
to look at you and drive it to keep its distance. What it needed was an API that says what to do
rather than how a body does it (§3: `robot.approach`), velocity joints and a base (§1), a diff
drive in the daemon (§5a), and body protocol v2 (§7).

**The robot** (Onshape LexJR-PT, branch `rover-test`, assembly "Rover Robot Test"):
- Rover-Chassis (new): a 120 mm round deck, a spine the two servos screw into back to back, a
  wall and lid, skids front and back for casters, and a mount plate for the camera;
- two HD-1910-Single in wheel mode (Feetech HLS operating mode 1, closed-loop speed), horns out
  along ±x, the axle 30 mm up;
- two Rover-Wheels (new), 60 mm across and 8 mm wide, 65 mm apart;
- LexJR's eye and lens, 64 mm up, looking +y.

The new parts are FeatureScript (lexjr-sim `rover/cad/rover_parts.fs`). The export turns the free
joint into `base_x`, `base_y` (slides) and `base_yaw` (a hinge), none limited.

**Its files:** `robots/rover.toml`, `.chain.json`, `.motion.json`; `projects/rover/project.toml`
(`gamerobotics play rover`); lexjr-sim `rover/robot.toml` (`[[servo]] mode = "velocity"`, `[base]`,
`[approach] base = true`, `[keep_distance] gain = 1.0`), `rover/robot.xml`, `scene.xml`; golden data
in `crates/gr-motion/tests/golden/rover/`.

**How it looks and keeps its distance.** Its gaze chain is its base's pose. MotionCore aims the
heading (`base_yaw` is its one head joint, a 2 Hz spring), from where odometry says the base is.
`robot.approach` drives along the line of sight until the eye is that much nearer the target,
across the floor, than it was at rest; with no target the base holds where it is. Travel is not
limited.

**Measured** with `scripts/trial.py rover --hold 4` on 2026-10-21 (Intel MacBook, release):

| gaze | fastest wheel target | fastest change | missed ticks | tick p99 | gaze error, held face | approach, worst miss | odometry vs true pose |
|---|---|---|---|---|---|---|---|
| smooth | 550°/s | 2,200°/s² | 0 | 4.8 ms | ≤ 0.03° | 0 mm (0.294 m in, 0.071 m back) | 0.71 mm, 0.13° after 2.6 m |
| cat | 550°/s | 2,200°/s² | 0 | 2.5 ms | ≤ 0.56° | 1 mm | 0.45 mm, 0.14° after 2.1 m |

Gaze error is across the floor: the camera is level, so a face above or below it stays above or
below. Targets behind it turn it right round (heading 3.14 rad). The pan tilt passes the same
trial, and so does LexJR (2026-10-21, CPU not throttled, 5 s holds): 0 missed ticks, tick p99
4.8 / 4.7 ms, gaze error on a held face ≤ 0.62° / 0.78° (smooth / cat). With the CPU throttled to
41% the same LexJR run missed 14 ticks (p99 15 ms): the throttle, not the code.

## 1c. Two robots in one: the Rover Pan Tilt Test (shipped)

A fourth robot, built on 2026-10-22 to test whether two robots' parts combine with **no daemon
change**: the rover's chassis and wheels with the pan tilt's head on top. None was needed. No code
in gamerobotd, gr-control, gr-motion, gr-proto or the behaviours changed; the only edit under
`crates/` is roverpt's entry in the golden test list.

**The robot** (Onshape LexJR-PT, branch `rover-pantilt-test`, assembly "Rover Pan Tilt Test"):
- RoverPT-Chassis (new): the rover's deck, spine, wheel wells and skids; the pan servo's case
  sits on its lid (z 47 mm);
- the rover's two HD-1910-Single in wheel mode and two RoverPT-Wheels (new; the rover's);
- the pan tilt's HD-1910-Single (pan), SwivelBracket and HD-1910 (tilt), its pan axis straight up
  through the middle of the axle (the pan tilt's own frame at (−59.75, 2.3, 70.89) mm in the
  rover's), and RoverPT-CameraYoke (new) carrying LexJR's eye and lens.

The new parts are FeatureScript (lexjr-sim `roverpt/cad/roverpt_parts.fs`). The mates solve with
no drift; tilt stops at −90° / +40° and pan at ±90° in the CAD. The head's clearance is the pan
tilt's: first contact at +45–49° of tilt (lexjr-sim `tools/clearance.py`, which now takes the pan and
  tilt joints' names, `--pan` and `--tilt`).

**Its files:** `robots/roverpt.toml`, `.chain.json`, `.motion.json`; `projects/roverpt/project.toml`
(`gamerobotics play roverpt`); lexjr-sim `roverpt/robot.toml`, `robot.xml`, `scene.xml`; golden
data in `crates/gr-motion/tests/golden/roverpt/`. In lexjr-sim's robot file, `base_yaw` is the
body joint (a 0.9 Hz spring) and pan and tilt are the head (5 Hz): the head glances, and the base
turns after it, as LexJR's neck leads its torso. `[approach] base = true` and `[keep_distance]
gain = 1.0` are the rover's.

**Measured** with `scripts/trial.py roverpt --hold 5` on 2026-10-22 (Intel MacBook, release; the
CPU throttled at times, down to 31%):

| gaze | limits | fastest target | missed ticks | tick p99 | gaze wobble, held face | gaze error, held face | approach, worst miss | odometry vs true pose |
|---|---|---|---|---|---|---|---|---|
| smooth | within (pan −84.4 / +85.3°, tilt −87.0 / +37.1°) | 550°/s; wheels 550°/s, 2,200°/s² | 0 | 4.6 ms | ≤ 0.58° | ≤ 0.42° | 0 mm (0.294 m in, 0.071 m back) | 0.46 mm, 0.008° after 2.4 m |
| cat | within | the same | 9 | 4.7 ms | ≤ 1.26° | ≤ 0.83° | 0 mm | 0.40 mm, 0.013° after 1.9 m |

Across the day's runs, missed ticks ranged from 0 to 11 on this robot, and from 0 to 11 on the
plain rover in the same hour; each was a stall in the simulator's reply (20–50 ms),
while the daemon's own tick stays under 0.25 ms. A target straight behind does not always settle:
see §10.

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
| `robot.approach` | `{"distance": -0.1}` | move the eye toward what the robot looks at (+, m) or away (−), eased (0.8 Hz) and clipped to what the robot can reach: LexJR leans on `neck_pitch` (about 5 cm), a rover drives (no limit) |
| `robot.tilt` | `{"amount": -0.15}` | tilt the head about its line of sight, rad, + with the robot's right ear down, eased and clipped; the gaze stays on the target |

Intents say what to do, not how a body does it: `look_at` is a world point and `approach` metres
toward it, whether the robot reaches them with a neck, a pan tilt or its wheels. Intents are
dropped while the robot is disabled, and gaze intents on a robot without `[motion]` are dropped and
counted. Non-finite values are dropped. On a velocity joint, `robot.joints` sets a speed (rad/s).

**Requests** are answered.

| method | params | result |
|---|---|---|
| `robot.info` | — | robot name, rate, joints (mode, limits or `null` for a wheel, speeds, home), daemon version, io, kinematics, `base` (drive, wheels, radius, track) or `null` |
| `robot.enable` | `{"on": true}` | torque on, hold the present pose, joints mode; refused if this tick's read failed |
| `robot.state` | — | the latest state frame |
| `robot.subscribe` | `{"hz": 10}` | state frames pushed on this connection, at most the control rate; dropped if the client lags |

Sending an intent with an `id` is an error (`-32600`). An unknown method is `-32601`, bad params
`-32602`, and a refusal by the robot `-32000`.

**State frame:** `t`, `tick`, `enabled`, `mode` (`joints` | `gaze`), `look_at`, `positions`,
`velocities` (`null` when this tick's read failed), `targets` (what was written; a wheel's is a
speed), `goals`, `base` (`{"pose": [x, y, heading], "target": [...] or null}`, from odometry, or
`null` without a base), `missed_ticks`, `read_errors`, `tick_time`.

## 4. gamerobotctl (shipped)

`info`, `state`, `enable`, `disable`, `joints name=deg ...` (degrees), `watch [--hz 5]`.

## 5. Safety (shipped)

Every target passes through Safety before it is written:
- A non-finite target holds the last command, and the refusal is counted. On a velocity joint it
  is 0: a wheel stops (holding its last speed would keep it driving).
- Each target is clamped to the joint's limits from the robot file.
- Each target is clamped to the joint's `max_speed × period` from the last command. A velocity
  joint's speed is clamped to `max_speed` and changes by at most `max_accel × period` a tick.
- Enabling anchors the speed limit at the present pose, and the wheels at standing still.
- Enabling, and leaving gaze mode, set every wheel's goal to 0.

## 5a. A mobile robot's base: the diff drive (shipped)

`gr-control/src/base.rs`, between MotionCore and Safety, on a robot with `[base]`:
- **Odometry:** every read, the base's pose from the wheels' angles (midpoint rule). It is what
  the daemon reports in `state.base.pose` and what MotionCore aims from.
- **Command:** in gaze mode, wheel speeds that take the base to the pose MotionCore asks for: the
  asked pose's own motion this tick, plus 5/s × the error along the heading and in the heading. A
  sideways error is not driven (a differential drive cannot); the heading brings it round. If a
  wheel would pass its top speed, both are scaled down together, keeping the curve.

The world is where the daemon started: `robot.look_at` targets are in that frame.

## 6. Gaze and approach: MotionCore (shipped)

`robot.look_at` hands the joint goals to MotionCore, which runs inside the tick:

1. **Body goal:** aim the whole chain. It takes a new goal only when the goal moves more than the
   8° deadband, so small glances are the head's alone.
2. **Body joints follow as springs:** torso 0.9 Hz at ζ 0.75; neck yaw and pitch 1.4 Hz at ζ 0.8.
3. **Layers:** idle oscillators (neck pitch 1.5° at 0.22 Hz, torso 1.0° at 0.09 Hz), and the
   approach (`robot.approach`, metres, its own spring, 0.8 Hz, ζ 1.0). On a lean joint (LexJR's
   `neck_pitch`, at most 30°) the metres become the joint's angle by how far the eye moves forward
   per radian at the posture (0.098 m/rad, so about 5 cm of reach). On a base, it drives along
   the line of sight until the eye is that much nearer the target than at rest. The tilt
   (`robot.tilt`, its own spring, 2 Hz, ζ 1.0, at most 20°) becomes the solver's roll target.
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

**Mode switches are continuous:** entering gaze mode starts MotionCore from the last goals (a
base, from its pose).

**The chain** may hold slides and joints with no limits (a base's `base_x`, `base_y`, `base_yaw`).
Aiming moves only body and head joints; a base's x and y are measured, not placed, so every aim
is from where odometry says it is.

**Kinematics:** native chain by default; MuJoCo as the fallback.

**Cost:** 30 us median a tick native, 54 us with MuJoCo (p99 75 / 158 us).

## 7. Simulator link: body protocol v2 (shipped)

TCP, one JSON object per line, one request and one reply each.

```jsonc
→ {"op":"hello","protocol":2,"joints":["wheel_left","wheel_right"],"modes":["velocity","velocity"],"dt":0.02}
← {"protocol":2}                     // or {"protocol":2,"error":"joint order differs: ..."}
→ {"op":"read"}                      // the simulator steps one dt, then answers
← {"positions":[...],"velocities":[...],"imu":null}
→ {"op":"write","targets":[...]}     ← {}
→ {"op":"torque","on":true}          ← {}
```

The simulator refuses a daemon whose joint names, modes or period differ. It reports in the
robot's units, and its own servo zeros, ratios and gears stay inside it. A dropped connection is
one failed tick and a reconnect on the next. Version 2 added the modes: a velocity joint's target
is a speed (rad/s) and its position keeps counting turns. **A wheel whose target is not renewed
within 0.1 s of body time stops**, and so does every wheel on torque off.

**LexJR body** (`lexjr-sim/body_server.py`):
- BAM servo models (HD-1910 / STS3215: 7.4 V, firmware P 5, 0.94 N·m stall).
- 20 ms command latency (`robot.toml [sim] goal_delay_ms`).
- The torso's 3:1 gear.
- A viewer with a front "call" view and a side camera (`]`).
- Survives the daemon disconnecting.
- Torque off is not simulated for position servos: they keep holding. Wheels stop.
- Wheels are velocity servos (kv 0.5 N·m per rad/s, the same 0.94 N·m stall, 550°/s): BAM is
  for the position loop. A base rolls on its wheels without slip (the model has no collision
  geometry). SimBus reports a wheel's position modulo a turn, as the HLS servo does; ServoMap
  unwraps it.
- `--truth-log PATH` writes the true base pose after every read (JSON lines, off the protocol),
  for checking odometry.
- `--publish HOST:PORT` sends the body's state after every read, off the protocol (UDP JSON:
  `t` body time, `qpos`, `eye`, `gaze`, and `viz`, the app's last visualization message), for
  the recorder (§9b).

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

**Proxemics** (`lexjr-sim robot.toml [keep_distance]`): your distance over the first second is
normal. Beyond a 2 cm deadband the robot approaches `gain` metres per metre, toward you when you
move away and back when you come closer (`robot.approach`). LexJR's gain is 0.256 (its old 1.5°
of lean per cm), reaching about 5 cm; the rover's is 1.0, making up all of it.

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
- approach: `KeepDistance` (Proxemics), on a robot with `[keep_distance]` and `[approach]`; tilt:
  `MimicTilt` (Mimic), with `[tilt]`.
- Sends `robot.look_at`, `robot.approach` and `robot.tilt` at 50 Hz. `--verbose` prints the cat's
  state changes; `--cat-seed` makes its choices repeatable.
- Sends the target and face mesh to the viewer (UDP 7610); the viewer draws the face wireframe
  and the gaze line from the robot's actual eye.

```sh
cd lexjr-sim && .venv-bam/bin/mjpython body_server.py
../gamerobotics/target/release/gamerobotd --io sim
.venv-cam/bin/python face_cam.py
.venv-bam/bin/python face_follow.py
```

## 8b. Face capture and playback (shipped)

Record your face once with the webcam; after that, any robot can follow it without the camera,
exactly as it followed you live.

- **Capture:** `face_cam.py --record FILE` (or `play --mocap-record FILE`) writes a header
  (`{"mocap": 1, detector, hfov_deg, width, height, mesh_idx, recorded}`), then every message as
  it was sent, with its time: the box, the 160 landmarks, and the `c` and `m` key presses. With
  the landmarker it also records MediaPipe's 52 expression blendshapes (`bs`) and the head pose
  (`pose`, a 4 x 4 matrix), which stay in the file: nothing uses them yet.
- **Playback:** `face_replay.py FILE` (or `play --mocap FILE`, looping) sends each message again
  to UDP 5005 with its original timing and the time it is sent, without `bs` and `pose`. The app,
  the daemon and the viewer can't tell it from the camera: the viewer draws the face mesh, and
  LexJR mirrors the head tilt.
- **Captures are a person's face.** They go in `mocap/`, which git ignores; the `face-mocap`
  skill (`.claude/skills/face-mocap/`) records and plays them back.
- First capture, 2026-10-22: 42.3 s, 817 frames, a face in every one, head tilt −9.2° to +6.3°,
  distance 0.24–0.51 m; played back on the rover pan tilt and on all four robots (§9b).

## 8a. Behaviours and the app SDK (shipped)

**The Python SDK** (`gamerobotics/python`, package `gamerobotics`, no dependencies, Python 3.10+):
- `gamerobotics.client.Robot`: `call(method, params)` for requests, `notify(method, params)` for intents.
- `gamerobotics.behaviours`:
  - `Behaviour`: `name`, `slots`, `start(previous)` (called on taking over, with the last
    intent per slot), `tick(seen) -> [Intent]`.
  - `Intent.look_at(target, saccade=False)`, `Intent.approach(distance)` (m), `Intent.tilt(amount)`.
  - `Percept`: `t`, `face` (`Face`: `eyes`, `left_eye`, `right_eye`, `mouth`, `distance`, `tilt`),
    `eye` (the robot's eye at rest), `home`, `events` (e.g. `"calibrate"`).
  - `Runner(behaviours, send, handover_s=0.5)`: slots `gaze`, `approach`, `tilt`, each owned by one
    behaviour (at the start, the first in the list that wants it); `select(name)` and
    `cycle(slot)` switch live; intents for slots a behaviour does not own are dropped. When the
    gaze changes hands, the new owner starts from the last target and the runner blends the two
    targets along a minimum-jerk curve for `handover_s`, holding saccades back.

**LexJR's behaviours** (`lexjr-sim/lexjr_ctl/behaviours.py`):

| behaviour | slot | what it does |
|---|---|---|
| `SmoothFollow` | gaze | look at your face, gliding after it; lost, ease home (0.5 s) |
| `CatGaze` | gaze | hold, decide, saccade, track, dart (below) |
| `KeepDistance` | approach | Proxemics as a behaviour |
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
track, dart and stare (164 state changes in 6.8 minutes), with the lean (now the approach) and tilt alongside.

## 9b. Recording the simulation (shipped)

**`recorder.py`** (lexjr-sim) films the 3D scene from `body_server.py --publish`: it builds the
same model (`sim_bam.build`, for the robot `LEXJR_ROBOT` names), renders it with MuJoCo's
off-screen renderer, draws the face and the line of sight over it as the viewer does
(`lexjr_ctl/overlay.py`, shared with the viewer), and pipes the frames to ffmpeg (H.264,
yuv420p). It is a separate process, reached by an address.
- **Body time:** frames follow the body's clock, so a video plays at the robot's own speed; a
  late state repeats the last frame. Each run reports the body's pace against the wall clock.
- **Two passes:** `--save-states` saves the states (no rendering, so the sim keeps the CPU) and
  `--states` renders them after. Rendering 1280 x 720 takes about 11 ms a frame (Intel MacBook);
  done during a run, on a throttled laptop, it let the sim fall to about 70% of real time, and a
  face played in wall time then outran the robot. Saved and rendered after, all four robots ran
  at 100%.
- **Cameras:** `behind` (over the shoulder), `fixed`, `front`, `side`, `orbit`, `view`, and
  `fit`: from saved states, the camera is framed on the bounding box of the whole interaction
  (every robot geom with its bounding radius, the face, its mesh and the end of the line of
  sight) inside `--fit-area` of the frame, from a set angle; one still shot, or following over
  `--fit-window` s smoothed both ways in time. The same states give the same video.
- **`play --record`** (branch `face-sim`) runs it alongside a project.

**`scripts/showreel.py`** makes `docs/recordings/one-face-four-robots.mp4` (2:07, 2026-10-22):
the first face capture (§8b) played to LexJR, the pan tilt, the rover and the rover pan tilt,
each filmed with the fit camera, captioned, with an explainer inset, a grid of all four at the
same moment, and narration from `docs/recordings/showreel.json`, voiced with ElevenLabs (never
a stand-in voice). Every video under `docs/` is on `media.html`; the simulation recordings are
listed in `docs/recordings/recordings.json`.

## 9. Verification (shipped)

| suite | what | where |
|---|---|---|
| unit | model parsing, Safety (incl. a wheel's speed and acceleration, a non-finite wheel target stopping it), Controller rules, the diff drive (odometry, command), body protocol client (modes in the hello), API envelopes | `cargo test` |
| golden | for each robot (LexJR, pan tilt, rover, rover pan tilt): FK + Jacobian on 500 poses (tolerance 1e-12), aim on 300 cases including roll targets (1e-9 rad), MotionCore replays over 4,850 ticks including tilt, the approach and 48 saccades (some fired mid-move) on perfect servos and BAM physics (1e-9 rad), on both kinematics backends; the approach's reach matches Python; the rover backs off along its line of sight | `crates/gr-motion/tests/golden.rs` |
| control path | the golden replay through Controller + Safety + FakeIo; limits no tighter than the motion's; mode switches without jumps; tilt and approach kept across the mode switch, gaze held while tilted | `crates/gr-control/tests/gaze.rs` |
| mobile robot | the rover through Controller + Safety + the diff drive + MotionCore on a FakeIo whose wheels turn: wheels still on enable, turning to look within the wheels' speed and acceleration, backing off 20 cm, stopping when told to hold | `crates/gr-control/tests/rover.rs` |
| Python | face_replay: a capture's header and info, a file that isn't one, and a capture played over UDP into `FaceTarget` gives the recorded points, the key press and its timing; ServoMap (incl. unwrapping a wheel), aim, MotionCore (incl. tilt, saccades, the approach) on NullBus and SimBus, face geometry and tilt, Proxemics, Mimic, the behaviours; each robot file describes itself; the pan tilt's MotionCore aims within its limits; the rover's wheel signs match its model, it turns to look, backs off and rolls as far as its wheels turned | `lexjr-sim/tests` |
| end to end | a robot's body, daemon and app with synthetic faces (UDP 5098, body port 7698), then targets past its limits: positions within the limits (0.5° slack), target speed per tick within `max_speed_dps` (a wheel's target within its speed and acceleration), gaze wobble under 1.5° on a held face, no missed ticks; on a wheeled robot, the approach within 2 cm of what keeping the distance asks and odometry within 1 cm and 1° of the body's true pose, once the base has come to rest | `scripts/trial.py` |
| stress | the API, loop and simulator link under load: floods, subscription spam, stalled and many clients, long lines, fuzzing, a disabled robot, CPU load, simulator faults | `scripts/stress.py` |
| SDK | the behaviour Runner: slots, switching, handover | `python/tests` |

Worst differences found: 2.4e-15 for kinematics, 3.9e-11 rad for the solver, 2.0e-11 rad for
MotionCore. The pan tilt's, on the native chain: 9.7e-16, 2.5e-10 rad and 9.2e-12 rad. The
rover's: 4.4e-16, 1.8e-15 and 7.9e-13. LexJR's joints with the approach in metres are its old
lean's, to 8e-15 rad. All eight planted bugs fail the harness (two for tilt: the roll target ignored, the
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
- **A capture plays in wall time.** If the sim falls behind real time, the face moves faster
  than the robot could follow it; `recorder.py` reports the pace, and `showreel.py` warns below
  95%.
- **Captures keep 160 of MediaPipe's 478 landmarks**, plus the blendshapes and head pose, which
  no behaviour uses yet.
- **The webcam is exclusive in practice.** With OBS running, `face_cam` got only occasional
  frames (126 failed reads in 143 s) and never a face. Quit other camera apps first. A camera
  check: 150 of 150 frames read, a face in all of them, once OBS was closed.

- **LexJR-only assumptions left** after the pan tilt (2026-10-20):
  - `gamerobotd --robot` defaults to `robots/lexjr.toml`.
  - gr-control's `tests/gaze.rs`, gr-motion's `examples/tick_time.rs` and `scripts/stress.py`
    use LexJR only.
  - Kinematics takes the eye's gaze as +y at the zero pose. (The approach now measures forward
    along the gaze, not +y.)
  - The solver keeps its roll-task row on a 2-DOF robot. This is harmless for pan then tilt,
    which cannot roll.
  - `robot.approach` and `robot.tilt` do nothing, without an error, on a robot with no
    `[approach]` or `[tilt]`.
- **The rover's limits** (2026-10-21):
  - The wheels' 550°/s is assumed, not measured; nor is the HLS speed loop's response.
  - The simulator rolls the base without slip and with no contact: how a wheel grips a desk is
    not modelled, so the sim's odometry is near exact.
  - The servo itself has no watchdog: on hardware, the bus driver must stop the wheels when the
    daemon stops writing, as the body does in sim.
  - The approach has no memory of place: after the target changes, the rover keeps its distance,
    not its spot, and a lost face leaves it where it is.
  - MotionCore limits `base_x` and `base_y` to the base's speed each, not together; the diff
    drive's scaling keeps the wheels within theirs.
  - `lookat.py` refuses a wheeled robot: it drives servos to angles, and only gamerobotd has the
    diff drive.
  - A robot is still described in two files: the daemon's `robots/<name>.toml` and lexjr-sim's
    robot file. M1's assembly compiler is meant to merge them.
  - lexjr-sim's robot constants are one robot per process (`LEXJR_ROBOT`).
- **The rover pan tilt's limits** (2026-10-22):
  - **A target straight behind can hunt.** Heading and pan both turn the gaze, and for a target at
    180° there are two mirror-image rest poses (heading about ±100°, pan near its far end). The
    posture pull costs them the same, so the slow base and the fast head can swing between them: in
    one trace the heading went to +130°, overshooting the target by 16°, then wound back to −106°.
    SmoothFollow failed to settle within 6 s in 2 of 6 trials (wobble 11–12°); CatGaze and the plain
    rover (one joint, one answer) always settled. Fixing it is a MotionCore change (keep to the side
    it is already turning to), not a robot-file one. A face behind the camera cannot be seen, so only
    `robot.look_at` can ask for this.
  - Missed ticks come and go with the CPU throttle, as on the other robots (§10, a throttled laptop).

## 11. Planned

- **FeetechIo:** sync read and write in ticks over rustypot, one transaction a tick; torque; IDs,
  zeros and directions from the robot file.
- **Policies:** an ONNX runner, an observation builder from a layout in the robot file, and
  loading microduck's manifest (schema 2) and 61/14 policies.
- **A Reachy Mini bridge** (Zenoh to JSON-RPC).
- **For third-party behaviours:** a scaffold (`gamerobotics behaviour new`), replay testing on
  recorded percepts, packaging; a percept service so perception is not tied to one app.
