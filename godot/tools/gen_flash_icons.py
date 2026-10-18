"""Generate the flash theme's icons: godot/themes/flash/icons/*.svg, hand-drawn as SVG source (no third-party art).

    python godot/tools/gen_flash_icons.py

One style for all of them: a 96 by 96 grid, a warm-paper stroke 5 wide with round ends, and one ember accent for the
part that carries the meaning. Shape carries the meaning, never the colour alone (each icon reads as a silhouette).
After running, import once (`godot_console --headless --path godot --import`) so Godot writes the .import files.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "themes", "flash", "icons"))

P = "#F4EFE6"      # paper: the line
E = "#FFB347"      # ember: the accent
HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96" fill="none" '
        'stroke="%s" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">' % P)

SHIELD = "M48 9 L80 21 V46 C80 66 66 80 48 88 C30 80 16 66 16 46 V21 Z"

ICONS = {
    # ---- the five moves
    "scavenge": '<path d="M30 42 C28 14 68 14 66 42"/>'
               '<path d="M16 42 H80 L72 80 H24 Z" fill="%s" fill-opacity=".18"/>'
               '<path d="M36 42 V80 M48 42 V80 M60 42 V80" stroke-width="3"/>'
               '<path d="M66 28 C78 18 88 22 88 22 C88 34 78 38 66 34" stroke="%s" stroke-width="4"/>' % (E, E),
    "guard": '<path d="%s" fill="%s" fill-opacity=".16"/>'
             '<path d="M33 48 L44 59 L64 35" stroke="%s" stroke-width="7"/>' % (SHIELD, E, E),
    "steal": '<path d="M26 54 V76 Q26 88 38 88 H58 Q72 88 72 74 V54" fill="%s" fill-opacity=".12"/>'
             '<path d="M34 54 V30 M45 54 V20 M56 54 V22 M66 54 V32" stroke-width="8"/>'
             '<path d="M26 64 L13 50" stroke-width="8"/>'
             '<circle cx="49" cy="72" r="7" fill="%s" stroke="none"/>' % (P, E),
    "investigate": '<circle cx="40" cy="40" r="26" fill="%s" fill-opacity=".12"/>'
                   '<path d="M59 59 L82 82" stroke="%s" stroke-width="9"/>'
                   '<path d="M26 36 A15 15 0 0 1 38 25" stroke-width="4"/>' % (P, E),
    "gift": '<rect x="16" y="42" width="64" height="40" rx="6" fill="%s" fill-opacity=".12"/>'
            '<rect x="11" y="28" width="74" height="16" rx="5"/>'
            '<path d="M48 28 V82" stroke="%s" stroke-width="7"/>'
            '<path d="M48 28 C40 8 24 12 30 24 C33 29 42 28 48 28 Z M48 28 C56 8 72 12 66 24 C63 29 54 28 48 28 Z" stroke="%s" stroke-width="4"/>' % (P, E, E),
    # ---- things
    "food": '<path d="M22 32 V70 Q48 86 74 70 V32"/>'
            '<ellipse cx="48" cy="32" rx="26" ry="9"/>'
            '<path d="M22 47 Q48 59 74 47 V59 Q48 71 22 59 Z" fill="%s" fill-opacity=".45" stroke="%s" stroke-width="3"/>' % (E, E),
    "shield": '<path d="%s"/><path d="M48 24 L68 31 V46 C68 58 60 66 48 72 C36 66 28 58 28 46 V31 Z" stroke="%s" fill="%s" fill-opacity=".25"/>' % (SHIELD, E, E),
    "bandit": '<path d="M8 38 Q48 20 88 38 V50 Q88 70 66 68 Q56 66 48 58 Q40 66 30 68 Q8 70 8 50 Z" fill="%s" fill-opacity=".2"/>'
              '<ellipse cx="30" cy="51" rx="9" ry="6" fill="%s" stroke="none"/>'
              '<ellipse cx="66" cy="51" rx="9" ry="6" fill="%s" stroke="none"/>'
              '<path d="M88 38 L94 28 M8 38 L2 28" stroke="%s" stroke-width="5"/>' % (E, P, P, E),
    "helicopter": '<ellipse cx="44" cy="58" rx="26" ry="17" fill="%s" fill-opacity=".14"/>'
                  '<path d="M68 54 H90 M88 44 V64" />'
                  '<path d="M44 41 V30 M6 30 H84" stroke="%s" stroke-width="6"/>'
                  '<path d="M26 56 Q28 46 42 46 V58 H26 Z" stroke-width="4"/>'
                  '<path d="M24 82 H68 M34 74 L32 82 M58 74 L60 82"/>' % (E, E),
    "radio": '<rect x="10" y="36" width="76" height="46" rx="9" fill="%s" fill-opacity=".1"/>'
             '<path d="M64 36 L80 8" stroke="%s" stroke-width="6"/>'
             '<path d="M22 52 H44 M22 62 H44 M22 72 H44" stroke-width="4"/>'
             '<circle cx="67" cy="59" r="12" fill="%s" fill-opacity=".35" stroke="%s"/>' % (P, E, E, E),
    # ---- beats the Stage plays that have no move of their own
    "move_resource": '<circle cx="24" cy="48" r="13" fill="%s" stroke="none"/>'
                     '<path d="M42 48 H82 M66 32 L84 48 L66 64" stroke="%s"/>' % (E, P),
    "shield_off": '<path d="%s" stroke-dasharray="9 8"/>'
                  '<path d="M52 20 L40 44 L56 54 L42 82" stroke="%s" stroke-width="6"/>' % (SHIELD, E),
    "blocked": '<path d="%s" fill="%s" fill-opacity=".14"/>'
               '<path d="M33 35 L63 65 M63 35 L33 65" stroke="%s" stroke-width="8"/>' % (SHIELD, P, E),
    "empty": '<circle cx="48" cy="48" r="32" stroke-dasharray="10 9"/>'
             '<path d="M34 48 H62" stroke="%s" stroke-width="7"/>' % E,
    "learn": '<path d="M6 48 C22 22 74 22 90 48 C74 74 22 74 6 48 Z"/>'
             '<circle cx="48" cy="48" r="13" fill="%s" stroke="none"/><circle cx="48" cy="48" r="5" fill="%s" stroke="none"/>' % (E, P),
    "marked": '<circle cx="48" cy="48" r="30"/><circle cx="48" cy="48" r="15" stroke="%s"/>'
              '<path d="M48 6 V22 M48 74 V90 M6 48 H22 M74 48 H90" stroke="%s" stroke-width="6"/>'
              '<circle cx="48" cy="48" r="4" fill="%s" stroke="none"/>' % (E, E, E),
    "camp": '<path d="M8 82 L48 16 L88 82 Z" fill="%s" fill-opacity=".12"/>'
            '<path d="M36 82 L48 56 L60 82" stroke="%s" stroke-width="6"/>'
            '<path d="M48 16 V8" stroke="%s" stroke-width="5"/>' % (P, E, E),
    "charm": '<path d="M48 6 L84 48 L48 90 L12 48 Z" fill="%s" fill-opacity=".1"/>'
             '<path d="M48 26 L66 48 L48 70 L30 48 Z" stroke="%s" fill="%s" fill-opacity=".4"/>' % (P, E, E),
    "total": '<path d="M22 20 V76 M36 20 V76 M50 20 V76 M64 20 V76" stroke-width="6"/>'
             '<path d="M10 66 L78 34" stroke="%s" stroke-width="6"/>' % E,
    "quiet": '<path d="M60 10 A38 38 0 1 0 86 62 A30 30 0 0 1 60 10 Z" fill="%s" fill-opacity=".2"/>'
             '<path d="M78 20 V34 M71 27 H85" stroke="%s" stroke-width="4"/>' % (E, E),
    "event": '<path d="M26 62 A15 15 0 0 1 26 32 A21 21 0 0 1 64 28 A17 17 0 0 1 70 62 Z" fill="%s" fill-opacity=".1"/>'
             '<path d="M52 54 L40 74 H54 L44 92" stroke="%s" stroke-width="6"/>' % (P, E),
    "unknown": '<circle cx="48" cy="48" r="38"/>'
               '<path d="M35 38 Q35 25 48 25 Q61 25 61 38 Q61 46 48 52 V58" stroke="%s" stroke-width="6"/>'
               '<circle cx="48" cy="72" r="4" fill="%s" stroke="none"/>' % (E, E),
    # ---- the morning board: the shape of a pile (full, middle, thin) says the band without colour
    "band_well_fed": '<rect x="14" y="12" width="68" height="20" rx="5" fill="%s" stroke="none"/>'
                     '<rect x="14" y="38" width="68" height="20" rx="5" fill="%s" stroke="none"/>'
                     '<rect x="14" y="64" width="68" height="20" rx="5" fill="%s" stroke="none"/>' % (E, E, E),
    "band_getting_by": '<rect x="14" y="12" width="68" height="20" rx="5" stroke-dasharray="6 7" stroke-width="3"/>'
                       '<rect x="14" y="38" width="68" height="20" rx="5" fill="%s" stroke="none"/>'
                       '<rect x="14" y="64" width="68" height="20" rx="5" fill="%s" stroke="none"/>' % (E, E),
    "band_starving": '<rect x="14" y="12" width="68" height="20" rx="5" stroke-dasharray="6 7" stroke-width="3"/>'
                     '<rect x="14" y="38" width="68" height="20" rx="5" stroke-dasharray="6 7" stroke-width="3"/>'
                     '<rect x="14" y="64" width="68" height="20" rx="5" fill="%s" stroke="none"/>' % E,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, body in ICONS.items():
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8", newline="\n") as f:
            f.write(HEAD + body + "</svg>\n")
    # the bandit mask doubles as the band icon for a bandit
    print("%d icons written to %s" % (len(ICONS), OUT))


if __name__ == "__main__":
    main()
