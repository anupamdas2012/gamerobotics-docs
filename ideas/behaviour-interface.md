# Idea: behaviours as plugins

Status: **built in part, 2026-10-19.** The trigger came: two gaze behaviours (smooth follow and cat
gaze) wanted the same slot. Built: the `Behaviour` interface, `Intent`, `Percept`, and the `Runner`
with slots, live switching and the gaze handover (`gamerobotics/python`; see spec §8a). Not built:
the scaffold, replay testing, packaging and a percept service, below. The rest of this page is the
original proposal.

## Where things stand

The motion capabilities are general and live in gamerobotd: `robot.look_at`, `robot.lean`,
`robot.tilt`. Any app can send them, and none of them knows about faces.

The behaviours are hard-wired in one app. `lexjr-sim/face_follow.py` calls three of them in a fixed
order each loop:

| behaviour | code | sends |
|---|---|---|
| look at the face | `FaceTarget` (`lexjr_ctl/face.py`) | `robot.look_at` |
| keep the distance | `Proxemics` (`lexjr_ctl/social.py`) | `robot.lean` |
| mimic the head tilt | `Mimic` (`lexjr_ctl/social.py`) | `robot.tilt` |

What that costs:
- **No switching at run time.** Turning one off means editing the script or deleting its config section.
- **No reuse.** A behaviour can't be paired with another sensor or another app.
- **No rule for conflicts.** If two behaviours send the same intent, the last one wins and nothing decides.

## The proposal

Keep it in the app layer: gamerobotd does not change.

1. **A `Behaviour` interface** with one method. Given what the sensors see this tick (a percept:
   face position, distance, tilt, landmarks, time), it returns the intents it wants, each with a
   priority:

   ```python
   class Behaviour(Protocol):
       name: str
       def tick(self, seen: Percept, t: float) -> list[Intent]: ...
   ```

2. **A small runner** in place of `face_follow.py`. Each tick it reads the sensors once and builds
   the `Percept`. It then runs the enabled behaviours and sends the winning intents to gamerobotd.
   The enabled set comes from config:

   ```toml
   [behaviours]
   enabled = ["gaze", "proxemics", "mimic_tilt"]
   ```

3. **One conflict rule:** each intent kind (`look_at`, `lean`, `tilt`, ...) goes to the highest
   priority behaviour asking for it this tick. Add blending only if a real case needs it.

## Why not now

Three behaviours on one camera work fine hard-wired. The interface's shape, especially what a
`Percept` holds and whether intents need priorities or blending, is better decided from five or six
real behaviours than from three. Candidates next: nod back when you nod, glance away while
"thinking", mirror expressions.

## Related

- [architecture.md](../architecture.md): processes, the tick, where intents go.
- The earlier architecture discussion (2026-10-16): blackboard, intents, arbiter. This is its
  smallest useful slice.
