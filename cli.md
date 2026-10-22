# Command-line reference

Every command in gameRobotics, with examples. The page `docs/cli.html` is generated from this
file by `scripts/build-pages.py`; `scripts/check-docs.py` fails if a command or flag in the code
is missing here. Exact behaviour (what `play` checks, every health message) is in the engine
spec, [spec.md](spec.md) §0.

## Quick start

```sh
cd gamerobotics
bin/gamerobotics setup lexjr        # once: builds gamerobotd, makes the Python environments
bin/gamerobotics play lexjr         # the sim, the daemon, the camera and the app; Ctrl+C stops all
```

You need [uv](https://docs.astral.sh/uv) and [Rust](https://rustup.rs). `setup` tells you if
either is missing. The first `play` asks for camera access for your terminal.

| I want to… | run |
|---|---|
| see LexJR follow my face | `bin/gamerobotics play lexjr` |
| run the Pan Tilt Robot Test instead | `bin/gamerobotics play pantilt` |
| run the Rover Robot Test (it turns and drives) | `bin/gamerobotics play rover` |
| try another personality | `bin/gamerobotics play lexjr --personality shy-puppy` |
| run without a window or the camera | `bin/gamerobotics play lexjr --headless --no-camera` |
| check everything is ready, without starting | `bin/gamerobotics doctor lexjr` |
| see what projects and personalities there are | `bin/gamerobotics projects` |
| move a joint by hand | `gamerobotctl enable` then `gamerobotctl joints neck_pitch=20` |
| watch the robot's state | `gamerobotctl watch --hz 5` |

## gamerobotics

The command most people use. `bin/gamerobotics` needs only uv the first time: it makes a small
Python environment for itself in `.venv`.

### gamerobotics play

Run a project: its processes start in order, each when the one before is ready, and they stop
together.

```sh
bin/gamerobotics play lexjr
bin/gamerobotics play lexjr --personality attentive-owl
bin/gamerobotics play lexjr --headless --no-camera --seconds 20
bin/gamerobotics play pantilt                    # the 2-DOF pan tilt, same daemon and app
bin/gamerobotics play rover                      # the two-wheeled rover: it turns to look and drives to keep its distance
```

| flag | what it does |
|---|---|
| `--personality NAME` | a personality from the project (`curious-cat`, `shy-puppy`, `attentive-owl`) or a path to a file; default: the project's |
| `--headless` | no sim window (the sim still runs) |
| `--no-camera` | run without the webcam; the robot looks straight ahead |
| `--seconds N` | stop after N seconds |
| `--verbose` | show every process's output as it happens, and a status line every 5 s |

While it runs, it prints each problem it finds, with what to do, and "fixed" when it clears. It
also prints a status line every 15 s:

```text
  loop 50 Hz · 3.7 ms a tick · skipped 0.0/s · camera 27 fps · face yes · CPU 100%
```

It stops everything on Ctrl+C, when the sim window is closed, or when any process stops. Each
process's output is kept in `.runs/<date-time>/<process>.log` (the last 10 runs).

**In the camera preview:** `m` switches the gaze between smooth follow and cat gaze, `c` makes
your current distance the normal one, and `q` quits the camera.

### gamerobotics setup

Make a project runnable. It only does what is missing, and says what it skips.

```sh
bin/gamerobotics setup lexjr
bin/gamerobotics setup lexjr --upgrade      # reinstall the environments' packages
```

| flag | what it does |
|---|---|
| `--rebuild` | rebuild gamerobotd even if it is built |
| `--upgrade` | reinstall the packages in environments that already exist |

### gamerobotics doctor

The pre-start checks of `play`, without starting anything: the daemon is built, the environments
exist, nothing else is running, the CPU isn't throttled, and the camera gives pictures.

```sh
bin/gamerobotics doctor lexjr
bin/gamerobotics doctor lexjr --no-camera
```

| flag | what it does |
|---|---|
| `--no-camera` | skip the camera check |

### gamerobotics projects

List the projects in `projects/`, and their personalities.

```text
$ bin/gamerobotics projects
lexjr        LexJR  · personalities: attentive-owl, curious-cat, shy-puppy
```

## gamerobotctl

Talk to a running gamerobotd from a terminal: for checking, and for moving joints by hand.
Angles are in degrees on this command line, and radians everywhere else.

```sh
target/release/gamerobotctl info                        # joints, limits, rate, what it drives
target/release/gamerobotctl enable                      # torque on; holds the pose it's in
target/release/gamerobotctl joints neck_pitch=20 head_yaw=-15
target/release/gamerobotctl watch --hz 5                # state, five times a second
target/release/gamerobotctl disable                     # torque off
```

| command | what it does |
|---|---|
| `info` | the robot: name, rate, joints with limits and speeds, the IO and kinematics in use |
| `state` | one state frame (mode, positions, targets, tick time, skipped ticks) |
| `enable` | torque on; the robot holds the pose it is in |
| `disable` | torque off |
| `joints name=deg …` | move joints to these angles (joints mode) |
| `watch` | print state frames as they come; `--hz` sets the rate (default 5) |

| flag | what it does |
|---|---|
| `--socket PATH` | the daemon's socket (default `/tmp/gamerobotd.sock`, or `GAMEROBOTD_SOCKET`) |
| `--hz N` | for `watch`: frames a second |

`play` runs a daemon for you; `gamerobotctl` works alongside it.

## gamerobotd

The daemon: the robot's 50 Hz loop. `play` starts it, so you only run it yourself to drive the
robot directly or to develop the daemon.

```sh
target/release/gamerobotd --io fake                     # a robot that tracks perfectly
target/release/gamerobotd --io sim                      # the simulator on 127.0.0.1:7600
```

| flag | what it does | default |
|---|---|---|
| `--robot FILE` | the robot file | `robots/lexjr.toml` |
| `--io fake\|sim` | a perfect fake robot, or a simulator over TCP | `fake` |
| `--sim ADDR` | the simulator's address, for `--io sim` | `127.0.0.1:7600` |
| `--sim-timeout-ms N` | how long to wait for the simulator each call before reconnecting | `2000` |
| `--socket PATH` | the API socket | `/tmp/gamerobotd.sock` |
| `--kinematics native\|mujoco` | the gaze kinematics; `mujoco` needs a build with `--features mujoco` | `native` |

## Test scripts

Run from the gamerobotics directory.

### scripts/golden.sh

Exports each robot's golden data from lexjr-sim (LexJR, then the pan tilt), then runs gr-motion's
and gr-control's tests against it. Run it after changing gr-motion or lexjr-sim's motion Python.

```sh
scripts/golden.sh
```

### scripts/trial.py

Runs one robot end to end: its simulated body (headless), gamerobotd and the face follow app,
with synthetic faces instead of the camera. With the app stopped, it then sends `look_at` targets
past the robot's limits. It checks positions against the limits, target speed per tick (a
wheel's speed and acceleration), gaze wobble on a held face, and missed ticks. On a wheeled
robot it also checks the approach against what keeping the distance asks (within 2 cm) and the
daemon's odometry against the body's true pose (`body_server --truth-log`, within 1 cm and 1°).
Then it prints JSON and PASS or FAIL. It uses its own ports
and socket (body 7698, faces 5098, `/tmp/gamerobotd-trial-<pid>.sock`), so it can run beside a
live demo.

```sh
../lexjr-sim/.venv-bam/bin/python scripts/trial.py pantilt
../lexjr-sim/.venv-bam/bin/python scripts/trial.py lexjr --gaze smooth --hold 5
../lexjr-sim/.venv-bam/bin/python scripts/trial.py rover --hold 4
```

| flag | what it does |
|---|---|
| `lexjr\|pantilt\|rover` | the robot |
| `--gaze smooth\|cat\|both` | which gaze behaviours to run (default both) |
| `--hold S` | seconds each synthetic face holds still (default 3; LexJR settles in about 5) |
| `--json FILE` | also write the results here |

### scripts/stress.py

Stresses gamerobotd's API, loop and simulator link. Each test starts its own daemon on its own
socket, and a fake body on port 7699.

```sh
python3 scripts/stress.py              # every test
python3 scripts/stress.py flood stalled
python3 scripts/stress.py --list
```

## The LexJR processes (lexjr-sim)

`play` runs these with the right settings. Run them by hand only to work on one of them. Each
runs from the `lexjr-sim` directory with its own environment.

**Which robot:** each runs LexJR unless `LEXJR_ROBOT` names another robot file, relative to
lexjr-sim, for example `LEXJR_ROBOT=pantilt/robot.toml .venv-bam/bin/python body_server.py`
(`rover/robot.toml` for the rover). A project sets it in its `[env]`. `lookat.py` refuses the
rover: it drives servos to angles, and a wheeled robot needs gamerobotd's diff drive.

### body_server.py

The simulated body: MuJoCo, LexJR's servo models, and the viewer.

```sh
.venv-bam/bin/mjpython body_server.py            # with the viewer
.venv-bam/bin/python body_server.py --headless
```

| flag | what it does |
|---|---|
| `--headless` | no viewer |
| `--host`, `--port` | where gamerobotd connects (default `127.0.0.1:7600`) |
| `--viz-port` | UDP port for the face and gaze line to draw (default 7610) |
| `--truth-log PATH` | write the true base pose after every read (JSON lines `{"t", "pose": [x, y, heading]}`), to check a wheeled robot's odometry against; never sent to the daemon |

**In the viewer:** `]` gives the side view, and `Esc` returns to the front view.

### face_cam.py

The webcam and face perception.

```sh
.venv-cam/bin/python face_cam.py
.venv-cam/bin/python face_cam.py --check 2       # 2 s camera test: one JSON line, then exit
```

| flag | what it does |
|---|---|
| `--camera N` | which camera (OpenCV index; default 0) |
| `--width`, `--height` | the picture size (default 640 × 480) |
| `--hfov DEG` | the camera's horizontal field of view, for distances (default 60) |
| `--detector landmarks\|box` | the face landmarker (default) or the simpler box detector |
| `--model FILE` | the Face Landmarker model |
| `--face-width M` | the face width the box detector assumes |
| `--port N` | where faces are sent (UDP, default 5005) |
| `--min-confidence X` | for `--detector box` |
| `--no-preview` | no preview window |
| `--check SECONDS` | test the camera and exit; prints opened, frames, failed reads, faces, fps |
| `--stats-every S` | how often to print a stats line for `play` (default 5) |

### face_follow.py

The app: LexJR's behaviours, run by the behaviour Runner.

```sh
.venv-bam/bin/python face_follow.py --personality ../gamerobotics/projects/lexjr/personalities/shy-puppy.toml
```

| flag | what it does |
|---|---|
| `--personality FILE` | a personality file |
| `--gaze smooth\|cat` | the gaze behaviour to start with (default: the personality's) |
| `--cat-seed N` | make the cat's choices repeatable |
| `--verbose` | print the cat's state changes |
| `--socket PATH` | gamerobotd's socket |
| `--face-port N` | where faces arrive (default 5005) |
| `--viz-port N` | the viewer's drawing port (default 7610; 0 for none) |
| `--hz N` | how often to send intents (default 50) |

## Troubleshooting

`play` and `doctor` print these. Each line says what's wrong, then what to do.

| you see | it means | do |
|---|---|---|
| The camera could not be opened | macOS hasn't given your terminal camera access, or another app has the camera | System Settings → Privacy & Security → Camera: allow your terminal; quit other camera apps |
| The camera opened but gave no pictures | another app is holding the camera | quit the app named (OBS, Zoom, FaceTime, Teams…), then run again |
| The camera is giving N pictures a second | the camera is starved | the same; or `--no-camera` |
| The Mac is throttling its CPU to N% | it's hot; the sim runs slower than real time (the motion is still right) | let it cool, close other apps, or use `--headless` |
| The control loop is skipping N ticks a second | the computer can't keep up | close other apps; let it cool |
| Ticks are taking N ms of their 20 ms | the loop is close to its limit | close other apps, or `--headless` |
| The robot (or simulator) is not answering | the sim stopped or hung | start again; check `.runs/…/sim.log` |
| No face in view | the camera works but sees no one | sit in front of it, with your face lit |
| Another gamerobotd is already running | an earlier run, or one you started | Ctrl+C it, or `pkill gamerobotd` |
| Another simulator is already running (port 7600) | an earlier sim is still open | close its window, or `pkill -f body_server.py` |
| gamerobotd isn't built yet; an environment is missing | setup hasn't run, or not fully | `bin/gamerobotics setup <project>` |
| The X isn't ready: it stopped | a process failed to start | read the log lines shown, and its full log in `.runs/` |
