# Build plan

Status: draft, 2026-10-20. How to get from the engine we have to the product in
[product-spec.md](product-spec.md) v0.2, module by module, in dependency order. Effort figures
are rough, for one developer working with an AI assistant, and are there to compare modules,
not to promise dates.

## Where we start

| what exists | state | what it means for the plan |
|---|---|---|
| gamerobotd: 50 Hz loop, Safety, JSON-RPC API, `RobotIo` seam | solid, tested | keep; it is robot-neutral already |
| MotionCore in Rust (`gr-motion`), golden-tested, 30 µs a tick | solid | keep; its config is exported from LexJR's Python, so it must come from an assembly instead |
| Behaviour SDK and Runner (Python) | solid | keep; add `needs` |
| LexJR's behaviours, face perception | working | keep; already robot-neutral apart from where the camera sits |
| Robot file (`robots/lexjr.toml`) | joints and limits typed by hand | replace with a project file built from parts |
| Sim body (`lexjr-sim/body_server.py`, `sim_bam.py`) | **LexJR only**: its 6 joints, its torso pinion and 3:1 gear, one BAM model are hard-coded | the biggest gap: needs to become generic |
| `RobotIo` | position targets only; IMU optional | wheels need velocity targets; balancing needs the IMU |
| Hardware | none (`FeetechIo` not written) | next: H0, bring-up tethered to the Mac |
| Starting it | four processes, three Python environments | `play` |

The engine core is general; the edges (the robot description, the sim, how it starts) are
LexJR-shaped. So the plan starts at the edges.

## The keystone: the assembly compiler

Every Build experience (describing a robot to an LLM, snapping parts, starting from an
archetype) produces the same thing: a **robot file that names kit parts and how they connect**.
What turns that into a running robot is one module, the **assembly compiler**:

```text
 robot file (parts + connections)
        │  catalogue: each part's geometry, mass, mounts, actuator model, limits
        ▼
  assembly compiler ──► MJCF for the sim (geometry, inertia, joints, actuators, sensors)
        │           ──► the daemon's robot file (joints, derived limits and speeds)
        │           ──► the kinematic chain and MotionCore config (gaze capability)
        │           ──► capabilities (gaze, lean, tilt, balance, drive...)
        ▼
     checker ──► plain-word problems: "nothing can see", "this servo cannot lift that arm"
```

The LLM builder and the snap builder are both editors on top of the compiler and checker, so the
compiler and checker come first. Everything a creator builds is only as good as these two.

## Modules, in order

### M0. Project format and `gamerobotics play` (first; ~2 weeks)

**Why first:** it unblocks testing with real people today, and every later module needs one
place for a robot's settings, not two.

- One **project** directory: the robot file, personalities, which behaviours run. Replaces the
  split between `lexjr-sim/robot.toml` and `gamerobotics/robots/lexjr.toml`.
- **`gamerobotics play <project>`** starts the sim body, daemon, camera and app in order, waits
  for each to be healthy, and stops them all together.
- **Health checks with plain-word messages:**
  - the camera: names the app holding it, such as OBS;
  - the CPU: reports throttling from `pmset`;
  - the loop: reports missed ticks;
  - the sim: reports when it has stopped answering.
- **One install:** a single Python environment where possible. MediaPipe's numpy pin and
  `mjpython` make this the fiddly part, so the fallback is managed environments the user never
  sees.

**Done when:** a clean Mac goes from install to LexJR looking at you in under 10 minutes, with
one command, and an OBS clash produces the right message.

### A0. Addressable API (now; ~1–2 weeks)

**The rule (the user's, 2026-10-20): build every client against an API with a connection
address, and never let it depend on running locally.** Then going from LexJR on the Mac to a Pi
walker is a new address, not a rewrite. Reachy Mini works this way: one app drives the tethered
Lite (daemon on the laptop) and the Wireless (daemon on the robot's Pi, found over Wi-Fi).

Today some features are reachable only locally: health exists only as `play`'s output,
personalities only as files plus a restart, switching only as a key in the camera preview, and
parameters not at all while running. A0 makes all of it addressable:
- **gamerobotd:** the same JSON-RPC over a WebSocket, localhost by default, next to the unix
  socket. Pairing and discovery stay parked.
- **The runner's control API:** slots, switching, live parameter changes, personalities.
- **The supervisor's status API** in `play`: processes, health messages, start and stop.
- **The CLI moves onto these,** so it is the first client and proves them.

**Performance guardrails.** The API never sits inside the control loop (invariant 2: the loop
never waits on a client):
- the API servers run on their own threads;
- each tick's state is encoded once and shared by every subscriber;
- a slow client drops frames rather than slowing anything;
- video, meshes and logs stay off the control API (video gets its own channel; meshes load once);
- clients subscribe at a chosen rate instead of polling;
- the runner's control API has its own thread, so the behaviours' 50 Hz never waits on the
  dashboard.

The daemon's state gains a **jitter histogram**: tick period p50, p99 and worst, over the last
minute.

**Done when:** everything `play`'s terminal shows and the preview's keys do is available through
the APIs, and the CLI works against them; and, **measured**, the loop's tick time and jitter (p99,
worst) are the same with the dashboard subscribed at 20–50 Hz and intents streaming at 50 Hz as
with nothing connected.

### D0. Dashboard: a Tauri app over the API (~2–3 weeks; alongside H0)

Reachy Mini's shape: a Tauri desktop app over the daemon. The API's second client, with no
back-end work of its own.
- **A Tauri 2 shell,** Mac dev build only: signing, installers and Windows stay parked.
- **Connection by address:** local by default. When the target is local, it starts and stops the
  project through the supervisor API; when it's remote, it just connects.
- **Views:**
  - health and process states;
  - a 3D robot view from the model and live joints;
  - controls: torque, joint sliders, a look-at target;
  - behaviours: slots, switching, presets and live sliders, save as mine;
  - a bring-up panel with per-joint ticks for H0.

**Done when:** everything done with `play` and the preview today can be done from the
dashboard, and pointing it at another address needs no code change.

### H0. Hardware bring-up: LexJR tethered (next; ~2–3 weeks)

**Why now:** every later choice depends on how the real robot behaves: the parts catalogue's
numbers, packaging, and whether LexJR needs a Pi. So the real robot comes before more software.
It runs tethered over USB to the Mac, the way Reachy Mini Lite runs. Platform packaging is
parked: see [ideas/platforms-and-deployment.md](ideas/platforms-and-deployment.md).

- **FeetechIo:** the `RobotIo` for Feetech servos over rustypot, with one sync read and one sync
  write per tick. Tested against a fake serial port first.
- **`gamerobotd --io feetech`;** the robot file gains each servo's ID, zero, direction and ratio.
- **Bench bring-up with one servo,** then a calibration helper: torque off, move each joint by
  hand, write the zeros and directions.
- **Measure:** loop timing and jitter on the real bus, command latency, gravity sag against the
  sim, and a BAM check on one servo.
- **Face follow on the real LexJR** through `play`, compared with the sim.

**Done when:** the real LexJR follows a face through `play`, and the measured numbers are in the
spec, with the sim checked against them.

### M1. Parts catalogue and assembly compiler (the keystone; ~4–6 weeks)

- **The catalogue** is data files, one per part. Each records:
  - geometry and a mesh;
  - mass and inertia;
  - mounting points, and what may attach where;
  - for actuators, the BAM model, limits, latency and modes (position, wheel).

  First parts:
  - the STS3215 servo, with the BAM model moved out of `sim_bam.py`;
  - spur gear N:1;
  - standard brackets and links;
  - wheel, webcam, IMU, battery and board.
- **The compiler** turns robot file to MJCF, the daemon robot file, the chain, the motion config
  and capabilities. Limits and speeds are derived, not typed. Gears become a joint equality, as
  LexJR's torso already is, but generated rather than hand-coded.
- **A generic sim body:** `body_server` runs whatever MJCF the compiler produced, with one BAM
  model per actuator. This removes the LexJR hard-coding in `sim_bam.py`.
- **Proof, by two tests:**
  1. **Regress LexJR:** describe LexJR as parts and compile it. The derived limits match today's
     (±57° torso, 183.3°/s), and the existing golden replays still pass on the compiled model.
  2. **Build something new:** a pan-tilt head from the catalogue, written as a file. Cat gaze and
     mimic tilt run on it unchanged.

**Risk:** part geometry. Brackets and links need meshes and mount points; this is CAD work, not
code. Mitigation: start with a few standard parts with simple shapes, and grow the catalogue.

### M2. Checker (~2 weeks; can overlap M1's end)

- **Rules, each with a plain-word message and, where possible, a fix:**
  - parts connect at compatible mounts;
  - joints have room to move without collisions (MuJoCo can check this);
  - each actuator can hold its load (static torque from MuJoCo's inverse dynamics at a few
    poses);
  - the battery and board can feed the servos;
  - the required capabilities are present for the chosen archetype.
- **A machine-readable form,** so the LLM can read the problems and fix them.

**Done when:** every broken robot in a test set is caught with the right message, and LexJR and
the pan-tilt head pass.

### M3. Capabilities and `needs` (~1 week)

- **The compiler emits capabilities;** the daemon's `robot.info` reports them.
- **Behaviours declare `needs`;** the Runner refuses mismatches and names what's missing.
- **MotionCore's gaze works on any chain** the `gaze` capability describes. The math is already
  general (the native chain); only the config source changes.

### M4. LLM builder ("describe it") (~3 weeks)

**Why before the snap builder:** it needs no 3D editing UI, it reuses the compiler and checker
directly, and it's the most inspiring way in.

- **A tool interface over the compiler:** `list_parts`, `start_from(archetype)`, `add_part`,
  `connect`, `set_param`, `check`, `explain`. The LLM can only call these, so it can only use kit
  parts, and the checker gates every result.
- **A loop:** propose, check, fix, until it passes, then show the robot in the sim and explain it.
- **Archetype prompts and examples:** what a balancing robot or a personality head usually looks
  like.
- **Command line first** (`gamerobotics build "a robot that..."`); the studio page later.

**Done when:** a set of natural-language descriptions produce robots that pass the checker and
run their archetype's behaviour in sim, without hand fixes, most of the time. We'll measure the
rate.

### M5. Balancing archetype (~4–6 weeks)

The first archetype beyond heads, and the first with real dynamics.

- **Wheel mode:**
  - the STS3215's continuous-rotation mode in the catalogue;
  - velocity targets through `RobotIo` and the body protocol (today they're position-only);
  - a BAM-style wheel model. This needs bench data, and until then it's a first guess.
- **The IMU in the sim:** MuJoCo's gyro and accelerometer through the body protocol, which
  already carries an optional IMU.
- **A `balance` primitive in the daemon,** inside the tick. Start with a classical controller
  (LQR from the compiled model, or a cascaded PID). It's predictable, testable, and needs no
  training run. An RL policy can replace it later through the same primitive.
- **A reference two-wheel balancer** built from the kit. Cat gaze runs on its pan-tilt head
  while it balances.

**Risk:** the sim-to-real gap is largest here. The plan only promises sim balancing; real
balancing waits for hardware and a fitted wheel model.

### M6. Snap builder (~4–6 weeks)

- **A browser 3D view of the compiled MJCF,** with the kit in a tray.
- **Snap to mounts,** show derived limits, light up capabilities, and show checker messages live.
- **It edits the same robot file as the LLM builder,** so both can be used on one robot.

It comes after the LLM builder because it's the most UI work, and the compiler, checker and file
format must be stable first.

### Parallel tracks

These don't block Build and can run alongside it:

| track | when | why |
|---|---|---|
| **Integrations** (Reachy Mini and microduck models in sim, then adapters) | after M1 | their models are a test of the compiler and catalogue on robots we didn't design |

## Order at a glance

```text
 M0 project + play ──► A0 addressable API ──► D0 dashboard (Tauri)
                                 └──────────► H0 hardware bring-up ──► M1 catalogue + compiler ──► M2 checker ──► M4 LLM builder ──► M6 snap builder
                                 │                     │
                                 └──► M3 capabilities ─┴──────► M5 balancing archetype
 parallel:  integrations (after M1)
 parked:    platforms and deployment (docs/ideas/platforms-and-deployment.md)
```

## What I'd build first

1. **M0, project format and `play`:** small, unblocks real users, and every later module needs
   it.
2. **M1, the catalogue and compiler,** proven on LexJR (regression) and a pan-tilt head (new).
   Everything in Build stands on it, and it's where overfitting to LexJR gets removed for real.
3. **M2 and M3,** then **M4, the LLM builder.** That's the first moment the "describe a robot and
   watch it come alive" promise is real, for personality heads.

Balancing (M5) follows once the compiler can describe wheels and an IMU.

## Decisions needed

1. **The balance controller:** classical first, with RL later through the same primitive? This
   plan assumes so.
2. **Part geometry source:** who designs the kit's brackets and links (in Onshape, as for LexJR),
   and do they become a buyable kit?
3. **The LLM for the builder:** which model, and local or hosted. The tool-only design works with
   any capable model.
4. **The browser stack for the studio and snap builder:** for example, three.js rendering the
   compiled MJCF.
