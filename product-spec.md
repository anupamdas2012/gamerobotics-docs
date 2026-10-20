# gameRobotics product spec

Status: draft v0.2, 2026-10-20 (v0.2: Build is a kit of parts, assembled by talking to an LLM or by
snapping parts together, starting from robot archetypes). The product we build on the engine. The engine as it exists is in
[architecture.md](architecture.md), [app-architecture.md](app-architecture.md) and the engine
spec, [spec.md](spec.md). The illustrated version, with UI mockups and animations, is
[product.html](product.html).

## Vision

**What game engines did for games, we do for robotics.**

Game engines did not make games easy by making rendering easy. They made the pipeline disappear
(build, assets, platforms, physics, input), so people could spend their time on the game. The
robotics equivalent of "the game" is what a robot does and how it feels to be around: its
behaviour and its character.

gameRobotics removes the pipeline: drivers, calibration, simulation, timing, sim-to-real, process
wrangling. What's left for the creator is the fun, creative work.

## Who it is for

| creator | wants | first experience |
|---|---|---|
| **Maker or student** (first) | to make a robot come alive, without a robotics degree | meet a robot on their laptop, give it a personality, then build one |
| Character designer or animator | to shape motion and personality, not code it | presets and sliders; record and replay |
| Robotics developer | the pipeline gone, so they can work on behaviours or policies | the SDK, the daemon, the sim |
| Educator | a reliable classroom platform | templates, a known parts kit, lessons |

v1 is designed for the **maker or student**. The others should not be blocked, but they do not
drive v1 decisions.

## Principles

1. **Time to first wiggle under 10 minutes.** From install to a robot moving on screen and
   reacting to you, with one command and no hardware.
2. **One project, sim and real the same.** Deploying to a robot is a target switch, not a port.
3. **Everything live.** Tune a spring, a cat's reaction time or a lean gain while it runs; save
   when it feels right.
4. **Safe by construction.** Nothing a creator writes can hurt the robot or a person: the
   daemon's Safety applies to everything.
5. **The system explains itself.** Problems arrive in plain words with the fix: "Camera busy: OBS
   is using it. Quit OBS." "CPU throttled to 20%: the sim is running slow." "Servo 3 is not
   answering: check its cable."
6. **Progressive depth.** Presets, then sliders, then Python behaviours, then Rust primitives.
   Nobody is forced down a level to do what they want at theirs.
7. **General by parts, not by special cases.** Robots are assemblies of known parts;
   behaviours target capabilities, never a particular robot.
8. **Every client talks to an address.** The CLI, the dashboard and later remote clients use APIs
   with a connection address, and none depends on running locally. Going from a robot tethered
   to a laptop to a robot with its own Pi is a new address, not a rewrite. Reachy Mini works this
   way: one app drives the tethered Lite and the Wireless.

## Core experiences

The order is real: each builds on the last.

1. **Play.** `gamerobotics play`, or a browser link later. The sim, daemon, camera and an app
   start together. A robot on screen looks at you within seconds.
2. **Shape.** Open the studio. Pick a personality preset (Curious Cat, Shy Puppy, Attentive Owl),
   then tune it with sliders. Save it as your own.
3. **Compose.** Choose which behaviour runs in each slot (gaze, lean, tilt...). Add one from a
   file, or write one in Python.
4. **Build.** Start something new from a kit of parts. Pick an archetype (a personality head, a
   balancing robot, a legged robot, a mobile robot), then assemble it by describing it to an LLM
   or by snapping parts together, or both. The tools check it and derive its limits, models and
   settings, and it runs in the sim straight away.
5. **Deploy.** Plug in the robot. A calibration wizard sets each servo up in a minute. The same
   project runs on the hardware.
6. **Share.** Export a personality, behaviour or robot as a file someone else can open.

## Concepts

| concept | what it is | today |
|---|---|---|
| **Part** | a characterized actuator, linkage or sensor from the catalogue | LexJR's servo and gear, characterized by hand |
| **Kit** | the set of catalogue parts a creator builds from | not built |
| **Archetype** | a kind of robot to start from: its typical structure, required parts and capabilities, and the motion it needs (e.g. balancing needs an IMU and a balance controller) | not built |
| **Robot** | an assembly of parts with joints, a kinematic chain and capabilities | LexJR, described across two files |
| **Capability** | something a robot can do: `gaze`, `lean`, `tilt`, `antennas`, `locomotion` | implicit: MotionCore assumes LexJR's head |
| **Primitive** | how a capability moves, in the daemon's tick: `look_at` (± saccade), `lean`, `tilt` | built |
| **Behaviour** | decides what to do from what the robot sees; needs capabilities; owns slots | built: SmoothFollow, CatGaze, KeepDistance, MimicTilt |
| **Personality** | a named set of behaviour parameters (and slot choices) | `[cat_gaze]`, `[lean]`, `[tilt]` in TOML |
| **Project** | a robot + its behaviours + personalities, runnable in sim or on hardware | face_follow.py plus config |
| **Target** | where a project runs: the sim, our robot, or another platform through an adapter | sim and fake built; hardware next |

## Parts catalogue (v1)

A part is **characterized**: measured once, on a bench, and recorded with everything the pipeline
needs. Every robot built from it inherits that work.

| type | v1 entries | recorded |
|---|---|---|
| actuator | Feetech STS3215 class (incl. HD-1910); second family: Dynamixel XL330 (microduck) | protocol and baud; ticks per revolution; voltage; the BAM model fitted on the bench; latency; speed and torque limits; how its zero and direction are found |
| linkage | direct drive; spur gear N:1; later belt and four-bar | ratio; range it allows; backlash; efficiency |
| sensor | USB webcam; next an IMU; later a distance sensor and a microphone | field of view and lens model; rate; latency; noise; where it mounts |

**Adding a part** is a bench procedure the catalogue documents: fit the BAM model from logged
moves, measure latency and backlash, record the limits. A new part is a data file, not code.

## Build: a kit, two ways to assemble, archetypes to start from

The point of Build is to **inspire people to make something new**, not to tweak an existing robot.
Remixing a robot is still possible (open its file), but it is not the front door.

### The kit

Build starts from a **kit**: a small, known set of catalogue parts that snap together. Every part
is characterized, so anything built from the kit simulates accurately and can be bought and built
for real. v1 kit:

| part | role | notes |
|---|---|---|
| STS3215-class servo | joints; **and wheels** (its continuous-rotation mode) | one actuator covers heads, arms, legs and drive wheels |
| spur gear N:1 | more torque or range at a joint | as LexJR's 3:1 torso |
| brackets and links | the structure between joints | standard lengths and mounts, so parts line up |
| wheel | rolls, driven by a servo in wheel mode | for balancing and mobile robots |
| USB webcam | vision | gaze, faces |
| IMU | orientation and rate | required to balance or walk |
| battery and controller board | power and the servo bus | sized from the parts it feeds |

### Two ways to assemble, one file

Both produce, and both edit, the same robot file. Switching between them at any time is
expected: describe a robot, then nudge it by hand; or snap a few parts, then ask the LLM to
finish it.

**1. Describe it (the LLM builder).** A chat beside the 3D view:

> *"A little robot that balances on two wheels and looks around with a camera on a pan-tilt head."*

The LLM:
- picks the closest archetype (balancing) and builds from **kit parts only**: it cannot invent a
  part, so everything it makes can be simulated and built;
- writes the robot file, and the tools **check** it: parts connect, joints are in range, the
  motors can carry the load, the battery suffices, the required capabilities are there. Problems
  go back to the LLM, which fixes them, and to you, in plain words;
- explains what it made and why ("two servos in wheel mode for balance; an IMU, which balancing
  needs; a pan-tilt head on top for gaze"), and takes changes ("make the head taller", "add a
  tail");
- **never skips the check**: an LLM suggestion is a proposal, and only a robot that passes runs.

**2. Snap it (the interactive builder).** A 3D view and the kit in a tray:
- drag a part onto a mount; it snaps where it fits and refuses where it doesn't;
- each joint shows its derived range and speed; each capability lights up as its parts arrive
  (an IMU plus two wheels turns on `balance`);
- warnings appear as you go: "this servo cannot lift that arm", "nothing can see: add a camera
  for gaze".

### Archetypes: kinds of robot to start from

An archetype is a **starting point for something new**, not a finished robot to edit: the
typical structure of a kind of robot, the parts it needs, the capabilities it gets, and the motion
it needs to work. Choosing one sets up the builder; the creator decides the rest.

| archetype | typical structure | needs from the kit | capabilities | motion it needs | engine today |
|---|---|---|---|---|---|
| **Personality head** | 2–6 joints aiming a camera (pan-tilt to LexJR) | servos, webcam | gaze, lean, tilt | MotionCore (built) | **runs** |
| **Balancing robot** | two wheels under a body, maybe a head | 2 servos in wheel mode, IMU, webcam optional | balance, drive, gaze | a balance controller or policy | not yet |
| **Legged robot** | 2 or 4 legs, 2–3 joints each, body, head | 6–12 servos, IMU | locomotion, gaze | an RL policy (microduck-style) | not yet |
| **Mobile robot** | wheels on a base, a sensor mast | 2–4 servos in wheel mode, webcam | drive, gaze | a drive primitive | not yet |
| **Arm** | a chain of joints, a camera or gripper at the end | 4–6 servos, webcam | gaze, reach | MotionCore's IK, then reach | gaze runs; reach not yet |

Each new archetype adds what its motion needs to the engine once: a `balance` primitive, a
`drive` primitive, `locomotion` through policies. After that, every robot of that kind gets it.

## Assemblies and capabilities

**A robot file names parts; the tools derive the rest.** For each joint it gives the actuator, the
linkage and the mount. From those the tools derive:
- joint limits: LexJR's ±57° torso is the servo's 360° through 3:1, less a margin, computed
  rather than typed;
- speed limits: 550°/s through 3:1 is 183.3°/s;
- the sim's actuator models, from the part's BAM fit;
- the servo driver's settings: IDs, zeros and directions come from the calibration wizard;
- the kinematic chain and motion defaults.

**A robot declares capabilities**, each with the joints and links that provide it and its
quality:

```toml
[capability.gaze]       # joints that aim a sensor; the sensor
joints = ["torso_yaw", "neck_yaw", "neck_pitch", "head_pitch", "head_yaw", "head_roll"]
eye = "camera"
saccade = true          # the daemon can jump; an adapter may say false

[capability.lean]
joint = "neck_pitch"

[capability.tilt]
via = "gaze"            # roll about the line of sight
```

**A behaviour declares what it needs**, such as `needs = {"gaze", "face"}` for cat gaze. The runner
refuses a behaviour whose needs a robot does not meet, and says which is missing. Where a quality
is lower (no saccades), the behaviour falls back (it glides) rather than failing.

## Reference robots

One built example per archetype: the set that proves the kit and the parts model are general.
Behaviours must run on every robot that has the capabilities they need, unchanged.

| robot | parts | capabilities | status |
|---|---|---|---|
| pan-tilt head (personality) | 2 × STS3215, webcam | gaze (2 joints) | to build (sim first) |
| LexJR (personality) | 6 × STS3215, spur 3:1, webcam | gaze, lean, tilt | built (sim) |
| two-wheel balancer (balancing) | 2 × STS3215 in wheel mode, IMU, a pan-tilt head | balance, drive, gaze | to build (sim first) |
| small quadruped (legged) | 8–12 × STS3215, IMU | locomotion, gaze | later |
| desk rover (mobile) | 2 × STS3215 in wheel mode, webcam mast | drive, gaze | later |
| arm (SO-100 class) | 6 × STS3215, wrist camera | gaze, later reach | later |
| Reachy Mini | imported model | gaze, tilt, antennas | integration |
| microduck | imported model, XL330 | gaze (head), locomotion | integration |

## Integrations

Other platforms are targets and sources, through their own protocols, with **no dependency** on
their code:

| level | what | how | v1 |
|---|---|---|---|
| **A. Our behaviours on their robots** | cat gaze, mimic tilt and the rest drive Reachy Mini or microduck | an adapter per platform behind the SDK's `Robot` interface: Zenoh to Reachy Mini's daemon; JSON-RPC to microduck's `robotd`. Each reports its capabilities and their quality | yes |
| **B. Their robots in our sim** | prototype for them without owning one | import their MuJoCo models; characterize their actuators as catalogue parts | yes |
| **C. Their content on our robots** | run microduck's policies, Reachy Mini's apps | load microduck's policy format (manifest schema 2, 61/14 layout); a Zenoh bridge for Reachy Mini apps | later |
| **D. Our daemon on their hardware** | our tick and motion quality on their bodies | a `RobotIo` for their buses | research only |

With adapters, the motion quality is theirs: saccades, springs and trim run in our daemon, so on
their robots a saccade may become their own interpolation. The capability's quality says so, and
behaviours degrade gracefully.

## Removing the pipeline: concrete goals

Each of these came from building LexJR's face follow.

| pain today | goal |
|---|---|
| four processes, four terminals, three Python environments, `mjpython` | `gamerobotics play`: one command, one install |
| the camera starved while OBS held it, with no message | the camera check names the app using it and says how to free it |
| the laptop throttled; the only symptom was a bad frame rate | a health bar: loop rate, missed ticks, CPU throttle, camera rate; plain-word warnings |
| change a setting: edit TOML, restart everything | live sliders; save to the project |
| motion changes need a manual golden-data export | the engine's own tests run it; creators never see it |
| CAD to robot file: export scripts, hand-typed limits (two wrong by rounding) | assemble from parts; limits derived and checked |
| servo IDs, zeros, directions edited by hand | a calibration wizard, one joint at a time |

## The UI (v1 scope)

v1 is the command line plus the **dashboard**: a Tauri desktop app (Reachy Mini's shape), the
"studio" in this spec. Both are clients of the same addressable APIs. It starts as a Mac
development build; installers, signing and Windows come later. A full editor is out of scope.

| screen | for | v1 |
|---|---|---|
| **Launcher** | play a ready-made robot, start building from an archetype, or open a project | yes, minimal |
| **Studio** | see the robot (the sim view), tune the personality live, health bar, messages | yes |
| **Behaviours** | which behaviour owns each slot; switch live; add from a file | yes (in the studio) |
| **Builder: describe** | an LLM chat that assembles kit parts into a robot, checked by the tools | phase 2 |
| **Builder: snap** | a 3D view and the kit tray; parts snap together, limits and capabilities appear as you go | phase 2 |
| **Calibration wizard** | set up each servo on real hardware | with FeetechIo |
| **Deploy** | switch target: sim, our robot, an integration | with FeetechIo |

Mockups of each are in [product.html](product.html).

## Personalities (v1 presets)

A personality is a named set of behaviour parameters and slot choices, saved as a small file.
Proposed presets, to tune by feel:

| preset | gaze | feel | settings (from today's defaults) |
|---|---|---|---|
| **Curious Cat** | CatGaze | quick, jumpy, lots of darts | react 0.10–0.30 s, cone 5°, darts every 0.25–0.6 s, tilt gain 1.0 |
| **Shy Puppy** | CatGaze | slow to look, glances away, keeps its distance | react 0.4–0.8 s, cone 12°, long stares, lean gain 2.0 (leans back more), tilt gain 1.2 |
| **Attentive Owl** | SmoothFollow | calm, steady, follows closely | smooth follow, tilt gain 0.5, lean gain 1.0 |

## Success measures

- Time to first wiggle: median under 10 minutes on a clean laptop.
- Personalities made and saved per new user.
- People who come back within a week.
- Behaviours that run unchanged on every reference robot (target: all).
- Sim-to-real: a personality tuned in sim feels the same on hardware (rated by the user).

## What changes in today's code

The engine is general underneath, but these places are fitted to LexJR:

| today | needed |
|---|---|
| settings split across `lexjr-sim/robot.toml` and `gamerobotics/robots/lexjr.toml` | one project format |
| `ServoMap` zeros, directions, ratios, and gear arithmetic by hand | derived from parts and the calibration wizard |
| the BAM model wired to one servo; the torso gear special-cased in the sim | per-part models from the catalogue |
| motion config exported from LexJR's Python | defaults derived from the assembly |
| gaze assumes an eye mesh on a head; perception assumes the webcam at the eye | the `gaze` capability names its sensor and mount |
| behaviours cannot state what they need | `needs` checked by the runner |
| four processes started by hand | `gamerobotics play` |

## Roadmap

The module-by-module plan, in dependency order, is [build-plan.md](build-plan.md).

| phase | goal | includes |
|---|---|---|
| **1. Play and shape** | time to first wiggle under 10 minutes, no hardware | `gamerobotics play`; addressable APIs; the dashboard, a Tauri app (live tuning, presets, health bar, messages); personality files |
| **2. The kit and the builder** | start something new; not overfit to LexJR | the kit and catalogue; robot files from parts, with checks; capabilities and `needs`; the builder (describe with an LLM, and snap); the personality-head and balancing archetypes in sim, with a `balance` primitive |
| **3. Real hardware** | the same project on a robot | FeetechIo; the calibration wizard; deploy |
| **4. Integrations** | other platforms | Reachy Mini and microduck models in sim; adapters for both |
| **5. Further** | breadth | legged (policies as a primitive), mobile and arm archetypes; browser play link; sharing; Reachy apps and microduck policies |

## Open questions (with the defaults this draft assumes)

1. First creator: **the maker or student**.
2. Actuators in v1: **the STS3215 class**, with XL330 second via microduck.
3. Sensors in v1: **USB webcam**; IMU in phase 2–3.
4. Archetypes in phase 2: **personality head and balancing**; legged, mobile and arm after.
   (Balancing is the cheapest step beyond heads that adds real dynamics: two servos and an IMU.)
8. The builder's LLM: **any capable model through a tool interface** (it may only call
   "add part", "connect", "check"), so it cannot write anything the checker has not passed.
5. Editor: **CLI plus the studio page** in v1; a full editor later.
6. Studio technology: **a browser page served locally by the app**, talking to the runner and
   daemon.
7. Business model: not decided; this spec does not assume one.
9. Platforms: **decided for now (2026-10-20): tethered over USB, the laptop runs everything (Reachy
   Mini Lite's model), on the user's Mac.** Mac and Windows packaging, containers, an onboard
   Pi Zero 2 W and browser or cloud options are parked until after hardware bring-up:
   [ideas/platforms-and-deployment.md](ideas/platforms-and-deployment.md).
