# Idea: platforms and deployment

Status: **parked**, 2026-10-20. Explored in conversation and set aside until a real robot has been
brought up. The user's call: designing packaging for several deployment setups before touching
hardware risks building the wrong thing. For now LexJR runs **tethered, the way Reachy Mini Lite
does**: the robot connects over USB and the laptop (the user's Mac) runs everything. Revisit after
hardware bring-up (plan module H0), with real numbers.

## The goal behind it

"It just works" on **Mac and Windows**, with nothing else to install. It should also work with
**external hardware** (a Raspberry Pi on the robot) as well as locally on a laptop. The user wants
the flexibility to choose either.

## What is tied to local hardware

| piece | local? | why |
|---|---|---|
| servo bus + the 50 Hz loop (gamerobotd) | yes, hard | the USB or serial port is local; the 20 ms tick can't cross a network; RL needs its trained timing |
| camera and microphone capture | yes | the device is local; what's done with the pictures can move |
| perception | movable, with costs | streaming video adds ~50–150 ms, bandwidth, and a privacy question |
| behaviours | movable | intents are small and the daemon smooths them |
| simulator, compiler, checker, LLM builder, training | not hardware | can run anywhere |

## Three setups, one codebase

| setup | brain runs on | used from | hardware link |
|---|---|---|---|
| sim only | the laptop | the laptop | none |
| **tethered** (now; Reachy Mini Lite's model) | the laptop (Mac or Windows) | the laptop | USB to the servos |
| onboard | a Pi on the robot (Linux) | any laptop or tablet, through the studio | the Pi's serial port |

gamerobotd is Rust, so the same code builds natively for Mac, Windows and Linux on ARM.

## Packaging options considered

- **Desktop app (Reachy Mini's way).** Pollen's Reachy Mini Control
  (github.com/pollen-robotics/reachy-mini-desktop-app, Apache-2.0):
  - **Tauri 2 and React.** Release v0.9.35 (2026-10-05) ships macOS `.dmg` for arm64 and x64,
    a Windows `.msi`, and Linux `.AppImage`, `.deb` and `.rpm`.
  - **A small Rust helper ("uv-trampoline") sets up Python on first launch:** it creates the
    environments in the per-user data folder (`~/Library/Application Support/…`,
    `%LOCALAPPDATA%\…`) and installs their package from PyPI.
  - **It supervises their Python daemon,** draws the robot in 3D (URDF, kinematics in
    WebAssembly), auto-updates the app and the robot software, and has an app store.
  - **Lessons:** Windows lagged macOS (their README: macOS production-ready, Windows and Linux
    work in progress). Windows code signing needs cloud or hardware keys since 2023; their report
    compares services at ~$120–700 a year, with Azure Trusted Signing the cheapest and the only
    one with immediate SmartScreen reputation. Antivirus can break first-launch downloads.
- **Fully bundled Python** instead of first-launch install: works offline, but the installer is
  large and every update means a new one.
- **Containers.** Good for Linux targets (a Pi, a cloud VM, CI): one multi-architecture image,
  with devices passed in. Wrong for hardware on a Mac or Windows laptop: Docker Desktop runs a
  hidden Linux VM, macOS can't pass USB serial in at all, Windows needs WSL2 plus `usbipd`, the
  webcam generally isn't available, the 50 Hz loop gets VM jitter, and Docker Desktop is a
  heavy install that needs a paid licence at companies of 250+ people.
- **A cloud VM backend.** Removes platform problems for the sim-only experience (the browser
  handles the camera on any OS), but costs a VM per user, sends the user's video to a server,
  and can't own a USB robot.
- **In the browser.** gr-control and gr-motion are pure Rust, so they could compile to
  WebAssembly. MuJoCo has WebAssembly builds (maturity unchecked); MediaPipe has a JavaScript
  version. This means no install and no server cost, and the webcam stays local. It needs a
  local native agent for hardware.
- **"Everyone on Linux."** Our code would be simpler (Unix sockets, signals, no `mjpython`), but
  users aren't on Linux, and WSL, Docker and VMs move the problem onto them. Linux has its own
  issues: distros, X11 vs Wayland, serial-port permissions (the `dialout` group). Linux works
  best **on the robot**: an onboard computer, as microduck (an RK3566 board, a phone app, and
  `duckctl` over BLE) and Reachy Mini Wireless do.

## Where the Windows port would break today

- The unix-socket API in gamerobotd and the Python client (Windows would use named pipes, or
  TCP plus a token).
- Process groups and signals in `play`.
- The bash wrapper `bin/gamerobotics`.
- `pmset` and `ps` in the health checks.
- `bin/python` vs `Scripts\python.exe`.
- `mjpython` (Mac-only).

## Performance per OS: separate builds, each optimized (decided 2026-10-20)

The user wants the best performance possible, even if that means separate builds for Mac and
Windows. Rust builds natively per OS anyway; each build should also get the OS's scheduling
right, since this matters more than the API:

| OS | risk to the 50 Hz loop | what the build does |
|---|---|---|
| Windows | default timer resolution of ~15.6 ms: sleeps overshoot a 20 ms tick | high-resolution waitable timers (or a raised timer resolution) and a raised thread priority for the control thread |
| macOS | App Nap and timer coalescing throttle background processes when the window is hidden or the Mac is idle | opt the daemon and app out of App Nap; give the control thread a high-priority (or real-time) scheduling class |
| both | local clients over TCP cost more than OS IPC | unix sockets on macOS, named pipes on Windows for local clients; the WebSocket for the dashboard and remote clients |
| Linux (a Pi) | CPU frequency scaling, other processes | a performance governor; a real-time priority for the control thread |

Measure each with the jitter histogram (A0): p50, p99 and worst tick period, on each OS's build.

## Onboard: Raspberry Pi Zero 2 W (the user's choice of board)

- **Fits easily:** gamerobotd (Rust; well under 1 ms of the 20 ms tick, scaled from 30 µs on the
  Mac), the behaviours, and the servo bus at 1 Mbit/s (over USB with an adapter, or the GPIO
  UART).
- **Tight:** 512 MB of RAM and slow ARM cores for MediaPipe onboard (to measure; the likely
  answer is perception on the laptop or in the browser, sending percepts over Wi-Fi); Docker's
  overhead (to measure; the fallback is a release folder run by systemd, as microduck does);
  under-voltage from servos (the health page should report it first).
- **What it adds:** a network API next to the local socket (JSON-RPC over WebSocket, with
  pairing), mDNS discovery (`lexjr.local`), a Pi image with an updater, and a remote health page.
- **To measure first:** gamerobotd's tick time and jitter on a Zero 2 W; MediaPipe's frames a
  second and memory; Docker's footprint.

## When to pick this up

After hardware bring-up (H0): when LexJR runs tethered on the Mac with measured timing, and
someone other than the user needs to install it.
