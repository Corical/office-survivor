#!/bin/sh
# Poll the Pi's public game feed; rebuild the live page and exit as soon as the posted news changes (or the game ends).
#   sh bot/tools/watch_feed.sh <scratch dir>     (max ~10 minutes per run)
D="$1"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
before=$(python -I -c "import json;d=json.load(open('$D/feed.json'));print(sorted(d['news']), d['finished'])" 2>/dev/null)
for i in $(seq 1 20); do
  sleep 30
  ssh -o BatchMode=yes pi "cd /opt/torch && sudo -u torch TORCH_DATA=/var/lib/torch /opt/torch/.venv/bin/python -m bot.tools.public_feed" > "$D/feed.new" 2>/dev/null || continue
  now=$(python -I -c "import json;d=json.load(open('$D/feed.new'));print(sorted(d['news']), d['finished'])")
  if [ "$now" != "$before" ]; then
    mv "$D/feed.new" "$D/feed.json"
    python -I "$ROOT/bot/tools/game_page.py" "$D/feed.json" "$D/torch-live.html" >/dev/null
    echo "changed: $now"
    exit 0
  fi
done
echo "no change in 10 minutes"
