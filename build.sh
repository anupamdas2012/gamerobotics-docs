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
SCENES=${*:-TickLoop Pipeline StaggeredGaze GoldenHarness CatVsSmooth AppTick FirstWiggle PartsToRobot CapabilityMatch Personalities KitBuild ArchitectureTour}
[ -x .venv-docs/bin/manim ] || { echo "no .venv-docs: see the comment at the top of this file" >&2; exit 1; }
cd "$OUT"
for s in $SCENES; do
  "$ROOT/.venv-docs/bin/manim" -qm --progress_bar none --media_dir "$MEDIA" scenes.py "$s" >/dev/null
  f=$(find "$MEDIA" -name "$s.mp4" -path "*720p30*" -not -path "*partial*")
  cp "$f" "$OUT/$s.mp4"
  ffmpeg -v error -y -sseof -0.3 -i "$OUT/$s.mp4" -frames:v 1 -vf scale=640:-1 "$OUT/$s.jpg"
  # The tour's stamp records what it was rendered from; check-docs fails when that changes.
  [ "$s" = ArchitectureTour ] && python3 "$ROOT/scripts/voiceover.py" --stamp
  echo "$s: $(du -k "$OUT/$s.mp4" | cut -f1) kB"
done
rm -rf "$MEDIA" "$OUT/__pycache__"
