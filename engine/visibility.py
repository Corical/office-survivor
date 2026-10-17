"""Morning ration ranges: which band each player is in, as posted to the whole camp (owner, 17 Oct 2026).

Shared by Torch (#news) and the simulator (what its AI may know). Ranges show a band, never a count.
"""
VISIBILITIES = ("hidden", "ranges", "exact")

# Band edges: the lowest ration count in each band, richest first. Below the last edge a survivor cannot exist (0 =
# bandit). (7, 3, 1) is the owner's proposal: well fed 7+, getting by 3-6, starving 1-2, bandit 0.
BAND_EDGES = (7, 3, 1)
BAND_LABELS = ("🟢 well fed", "🟡 getting by", "🔴 starving", "🏴‍☠️ bandit")


def band_index(q, edges=BAND_EDGES):
    """0 = richest band ... len(edges)-1 = poorest survivors, len(edges) = bandit. A bandit is a bandit whatever it holds."""
    if q.bandit:
        return len(edges)
    for i, lo in enumerate(edges):
        if q.rations >= lo:
            return i
    return len(edges) - 1            # a survivor on 0 is converted to a bandit before anyone can see it


def band_label(q, edges=BAND_EDGES):
    return BAND_LABELS[min(band_index(q, edges), len(BAND_LABELS) - 1)] if len(edges) == 3 else \
        f"band {band_index(q, edges)}"


def morning_board(players, vis, edges=BAND_EDGES):
    """The post each morning. Ranges: the player order inside a band is alphabetical so the post cannot leak a
    ranking; exact: richest first. Hidden: None."""
    if vis == "hidden":
        return None
    if vis == "exact":
        return [f"{p.name}: {'bandit, ' if p.bandit else ''}{p.rations}" for p in sorted(players, key=lambda p: (-p.rations, p.name))]
    lines = []
    for i in range(len(edges) + 1):
        names = sorted(p.name for p in players if band_index(p, edges) == i)
        if names:
            lines.append(f"{BAND_LABELS[i] if len(edges) == 3 else 'band ' + str(i)}: " + ", ".join(names))
    return lines
