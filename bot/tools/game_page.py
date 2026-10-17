"""Build the live game page from the public feed (bot/tools/public_feed.py output).

    python bot/tools/game_page.py feed.json out.html
"""
import html
import json
import sys

feed = json.load(open(sys.argv[1], encoding="utf-8"))
news = {int(k): v for k, v in (feed.get("news") or {}).items()}
news_html = "".join(
    f'<li data-night="{n}"><h3>Morning {n}</h3><ul>' + "".join(f"<li>{html.escape(l)}</li>" for l in lines) + "</ul></li>"
    for n, lines in sorted(news.items(), reverse=True))
end_html = ""
if feed.get("finished"):
    end_html = (f'<section class="end"><h2>The helicopter has left</h2><p>Seats: {html.escape(", ".join(feed["extracted"]))}</p>'
                f'<p>Winner: <strong>{html.escape(", ".join(feed["winners"]))}</strong></p></section>')

page = """<title>Torch Live Game</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;800&family=Atkinson+Hyperlegible:wght@400;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: status band on top (what's open now, live countdown), then the round timeline beside the news feed. */
:root {
  --bg: #f3f1ee; --panel: #ffffff; --ink: #1d1b19; --muted: #6b645c; --line: #ddd6cd;
  --torch: #d9480f; --torch-soft: #fde6d8; --done: #2f7d4f; --wait: #8a8178;
  --f-display: "Bricolage Grotesque", "Segoe UI", sans-serif;
  --f-body: "Atkinson Hyperlegible", "Segoe UI", sans-serif;
  --f-mono: "JetBrains Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #151312; --panel: #1f1c1a; --ink: #f0ebe5; --muted: #a39a90; --line: #3a3530;
  --torch: #ff7a3d; --torch-soft: #3b2216; --done: #6cc28f; --wait: #8f867c; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #151312; --panel: #1f1c1a; --ink: #f0ebe5; --muted: #a39a90; --line: #3a3530;
  --torch: #ff7a3d; --torch-soft: #3b2216; --done: #6cc28f; --wait: #8f867c; color-scheme: dark }
body { background: var(--bg); color: var(--ink); font-family: var(--f-body); font-size: 15px; }
main { max-width: none; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 20px 48px; display: grid; gap: 18px; }
h1, h2, h3 { font-family: var(--f-display); margin: 0; text-wrap: balance; }
h1 { font-size: clamp(26px, 3vw, 36px); font-weight: 800; }
.meta { color: var(--muted); font-family: var(--f-mono); font-size: 13px; }
.status { background: var(--torch-soft); border: 1px solid var(--torch); border-radius: 10px; padding: 16px 18px;
  display: flex; flex-wrap: wrap; gap: 8px 28px; align-items: baseline; }
.status .big { font-family: var(--f-mono); font-size: clamp(30px, 5vw, 46px); font-weight: 600; color: var(--torch);
  font-variant-numeric: tabular-nums; }
.status .what { font-family: var(--f-display); font-size: 20px; font-weight: 600; }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 18px; align-items: start; }
@media (max-width: 820px) { .cols { grid-template-columns: 1fr; } }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; min-width: 0; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 7px 6px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 700; }
td.t { font-family: var(--f-mono); }
.chip { font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 99px; border: 1px solid; }
.chip.done { color: var(--done); border-color: var(--done); }
.chip.open { color: var(--torch); border-color: var(--torch); background: var(--torch-soft); }
.chip.next { color: var(--wait); border-color: var(--line); }
tr.open td { background: var(--torch-soft); }
.feed { list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; }
.feed > li { border-left: 3px solid var(--torch); padding-left: 12px; }
.feed ul { margin: 6px 0 0; padding-left: 18px; display: grid; gap: 4px; }
.empty { color: var(--muted); }
.end { background: var(--panel); border: 2px solid var(--done); border-radius: 10px; padding: 16px 18px; display: grid; gap: 6px; }
.note { color: var(--muted); font-size: 13px; }
</style>
<main>
  <header>
    <h1>🔥 Torch: live game</h1>
    <div class="meta" id="meta"></div>
  </header>
  __END__
  <section class="status" aria-live="polite">
    <span class="what" id="what"></span><span class="big" id="countdown"></span><span class="meta" id="when"></span>
  </section>
  <div class="cols">
    <section class="panel"><h2>Rounds</h2><div style="overflow-x:auto"><table>
      <thead><tr><th>Round</th><th>Moves close</th><th>News</th><th>State</th></tr></thead>
      <tbody id="rounds"></tbody></table></div>
      <p class="note">Times are SAST. Miss a deadline and you scavenge automatically.</p></section>
    <section class="panel"><h2>#news</h2><ul class="feed">__NEWS__</ul></section>
  </div>
</main>
<script>
const FEED = __FEED__;
const fmt = ts => new Date(ts * 1000).toLocaleTimeString("en-ZA", {hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Africa/Johannesburg"});
const dur = s => { s = Math.max(0, Math.round(s)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
function render() {
  const now = Date.now() / 1000;
  document.getElementById("meta").textContent = FEED.started
    ? `${FEED.season} · ${FEED.players} players · ${FEED.rounds} rounds · a day every ${FEED.day_seconds / 60} min`
    : `${FEED.season} · not started yet`;
  if (!FEED.started) { document.getElementById("what").textContent = "Waiting for the Game Master to start"; return; }
  const dl = n => FEED.start_ts + n * FEED.day_seconds, nw = n => dl(n) + FEED.news_delay;
  const posted = new Set(Object.keys(FEED.news).map(Number));
  let open = null, rows = "";
  for (let n = 1; n <= FEED.rounds; n++) {
    let state = "next", label = "upcoming";
    if (now < dl(n) && open === null) { state = "open"; label = "moves open"; open = n; }
    else if (now >= dl(n)) { state = posted.has(n) ? "done" : "open"; label = posted.has(n) ? "news out" : "resolving"; }
    rows += `<tr class="${state === "open" ? "open" : ""}"><td>${n}</td><td class="t">${fmt(dl(n))}</td><td class="t">${fmt(nw(n))}</td><td><span class="chip ${state}">${label}</span></td></tr>`;
  }
  document.getElementById("rounds").innerHTML = rows;
  const what = document.getElementById("what"), cd = document.getElementById("countdown"), when = document.getElementById("when");
  if (FEED.finished) { what.textContent = "Game over"; cd.textContent = ""; when.textContent = ""; }
  else if (open) { what.textContent = `Round ${open}: moves close in`; cd.textContent = dur(dl(open) - now); when.textContent = `at ${fmt(dl(open))}`; }
  else { what.textContent = "Final round resolved: reveal coming"; cd.textContent = ""; when.textContent = ""; }
}
render(); setInterval(render, 1000);
</script>
"""
page = (page.replace("__FEED__", json.dumps(feed)).replace("__END__", end_html)
        .replace("__NEWS__", news_html or '<li class="empty">No news yet. The first morning news arrives after round 1 closes.</li>'))
open(sys.argv[2], "w", encoding="utf-8").write(page)
print(sys.argv[2])
