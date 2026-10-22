#!/bin/bash
# Render docs/animations/*.mp4 (and poster frames) from docs/animations/scenes.py with manim.
#   docs/build.sh                 # every scene
#   docs/build.sh TickLoop        # one scene
# manim lives in .venv-docs (git-ignored): uv venv -p 3.12 .venv-docs && uv pip install -p .venv-docs/bin/python manim
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
OUT=$ROOT/docs/animations
MEDIA=$(mktemp -d)
SCENES=${*:-TickLoop Pipeline StaggeredGaze GoldenHarness CatVsSmooth AppTick FirstWiggle PartsToRobot CapabilityMatch Personalities KitBuild ArchitectureTour BehaviourTour}
[ -x .venv-docs/bin/manim ] || { echo "no .venv-docs: see the comment at the top of this file" >&2; exit 1; }
cd "$OUT"
for s in $SCENES; do
  kind=$(python3 "$ROOT/scripts/voiceover.py" --kind "$s")
  if [ "$kind" = composed ]; then
    # A composed tour: manim renders its own steps as sections; compose-tour.py adds the reused
    # animations and the narration.
    "$ROOT/.venv-docs/bin/manim" -qm --progress_bar none --save_sections --media_dir "$MEDIA" scenes.py "$s" >/dev/null
    python3 "$ROOT/scripts/compose-tour.py" "$(python3 -c "import sys; sys.path.insert(0, '$ROOT/scripts'); import voiceover; print(voiceover.tour_of('$s'))")" "$MEDIA"
  else
    "$ROOT/.venv-docs/bin/manim" -qm --progress_bar none --media_dir "$MEDIA" scenes.py "$s" >/dev/null
    f=$(find "$MEDIA" -name "$s.mp4" -path "*720p30*" -not -path "*partial*" -not -path "*sections*")
    cp "$f" "$OUT/$s.mp4"
  fi
  ffmpeg -v error -y -sseof -0.3 -i "$OUT/$s.mp4" -frames:v 1 -vf scale=640:-1 "$OUT/$s.jpg"
  # A narrated tour's stamp records what it was rendered from; check-docs fails when that changes.
  [ "$kind" != plain ] && python3 "$ROOT/scripts/voiceover.py" --stamp "$s"
  echo "$s: $(du -k "$OUT/$s.mp4" | cut -f1) kB"
done
rm -rf "$MEDIA" "$OUT/__pycache__"
