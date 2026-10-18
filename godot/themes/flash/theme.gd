extends RefCounted
## The "flash" theme: a camp on a dark island, ten nights long. Night-blue surfaces, one ember accent that always means
## "the thing you act on" (your name, the clock, Lock in), warm paper text, chunky rounded buttons with a lit edge.
##
## The look in one line each:
##  - Backdrop: a firelight glow rising from the bottom of the screen (a gradient behind every scrolling page).
##  - Hierarchy: your alias and the room code in ember at 46 px, the clock and amounts at 28 px, body at 20 px, small
##    labels at 15 px in spaced capitals. The eye lands on who you are, then the clock, then Lock in.
##  - Depth: raised buttons with a soft shadow; the primary button is ember with a darker lip and a faint glow.
##  - Accessibility: every text colour is 7:1 or better on its surface (see docs/visual/flash/NOTES.md for the table);
##    state is never colour alone (words, shapes and icons carry it); a 3 px cyan focus ring on keyboard focus.
##
## Everything visual lives in this folder. Screens name a type variation only; the Stage asks the "Stage" type for its
## colours; icons are SVG textures keyed by id. Regenerate words with tools/gen_flash_words.py and icons with
## tools/gen_flash_icons.py.

# ---------------- palette (hex, so the notes can quote them) ----------------
const INK_DEEP := Color("0a0f1c")          # deepest night: input wells, the timer track
const INK := Color("111a2e")               # the sky
const SURFACE := Color("1b2742")           # cards
const RAISED := Color("26365a")            # buttons
const RAISED_HI := Color("33477a")         # buttons, hovered
const EDGE := Color("5c78b4")              # borders at rest (3:1 against the sky, as WCAG asks of a control's edge)
const PAPER := Color("f6f1e7")             # body text (warm white)
const MUTED := Color("d0d9ea")             # secondary text (lifted so the small caps labels survive glare)
const EMBER := Color("ffb347")             # the accent
const EMBER_HI := Color("ffcc7a")
const EMBER_LO := Color("e8892b")
const EMBER_LIP := Color("a8590f")         # the dark lip under the primary button
const ON_EMBER := Color("1c1206")          # text on ember
const FOCUS := Color("8fe8f7")             # keyboard focus ring
const DISABLED_TEXT := Color("7f8ca6")

const ICONS := {
	"scavenge": preload("res://themes/flash/icons/scavenge.svg"),
	"guard": preload("res://themes/flash/icons/guard.svg"),
	"steal": preload("res://themes/flash/icons/steal.svg"),
	"investigate": preload("res://themes/flash/icons/investigate.svg"),
	"gift": preload("res://themes/flash/icons/gift.svg"),
	"food": preload("res://themes/flash/icons/food.svg"),
	"shield": preload("res://themes/flash/icons/shield.svg"),
	"bandit": preload("res://themes/flash/icons/bandit.svg"),
	"helicopter": preload("res://themes/flash/icons/helicopter.svg"),
	"radio": preload("res://themes/flash/icons/radio.svg"),
	# beat kinds the Stage plays (rulesets/survivors/adapter.gd BEAT_KINDS)
	"move_resource": preload("res://themes/flash/icons/move_resource.svg"),
	"shield_on": preload("res://themes/flash/icons/shield.svg"),
	"shield_off": preload("res://themes/flash/icons/shield_off.svg"),
	"blocked": preload("res://themes/flash/icons/blocked.svg"),
	"empty": preload("res://themes/flash/icons/empty.svg"),
	"learn": preload("res://themes/flash/icons/learn.svg"),
	"marked": preload("res://themes/flash/icons/marked.svg"),
	"status": preload("res://themes/flash/icons/bandit.svg"),
	"camp": preload("res://themes/flash/icons/camp.svg"),
	"charm": preload("res://themes/flash/icons/charm.svg"),
	"total": preload("res://themes/flash/icons/total.svg"),
	"quiet": preload("res://themes/flash/icons/quiet.svg"),
	"event": preload("res://themes/flash/icons/event.svg"),
	"unknown": preload("res://themes/flash/icons/unknown.svg"),
	# the morning board: the shape of the pile says the band (words say it too)
	"band.well_fed": preload("res://themes/flash/icons/band_well_fed.svg"),
	"band.getting_by": preload("res://themes/flash/icons/band_getting_by.svg"),
	"band.starving": preload("res://themes/flash/icons/band_starving.svg"),
	"band.bandit": preload("res://themes/flash/icons/bandit.svg"),
}


static func build() -> ThemeDef:
	var t := ThemeDef.new()
	t.id = "flash"
	t.title = "Long Night"
	t.words = load("res://themes/flash/words.po")
	t.icons = ICONS.duplicate()
	var th := t.godot_theme

	# ---- fonts: only the engine's own font, in two weights
	var body := FontVariation.new()
	body.base_font = ThemeDB.fallback_font
	body.variation_embolden = 0.2
	var bold := FontVariation.new()
	bold.base_font = ThemeDB.fallback_font
	bold.variation_embolden = 0.75
	var spaced := FontVariation.new()
	spaced.base_font = ThemeDB.fallback_font
	spaced.variation_embolden = 0.55
	spaced.spacing_glyph = 1
	th.default_font = body
	th.default_font_size = 18                 # the Stage derives its label size from this; other controls set their own
	RenderingServer.set_default_clear_color(Color("0b1120"))   # the page margin; the ONE global this theme touches

	_labels(th, bold, spaced)
	_buttons(th, bold)
	_timer_bar(th)
	_inputs(th)
	_scroll(th)
	_panels(th)
	_stage(th)
	return t


# ---------------- pieces ----------------

static func _labels(th: Theme, bold: Font, spaced: Font) -> void:
	th.set_font_size("font_size", "Label", 20)
	th.set_color("font_color", "Label", PAPER)
	th.set_constant("line_spacing", "Label", 4)
	# HeaderLabel: the clock, the amounts, section titles
	th.set_type_variation("HeaderLabel", "Label")
	th.set_font("font", "HeaderLabel", bold)
	th.set_font_size("font_size", "HeaderLabel", 28)
	th.set_color("font_shadow_color", "HeaderLabel", Color(0, 0, 0, 0.55))
	th.set_constant("shadow_offset_y", "HeaderLabel", 2)
	# BigLabel: who you are, the room code, the app name: the first thing the eye lands on
	th.set_type_variation("BigLabel", "Label")
	th.set_font("font", "BigLabel", bold)
	th.set_font_size("font_size", "BigLabel", 46)
	th.set_color("font_color", "BigLabel", EMBER_HI)
	th.set_color("font_shadow_color", "BigLabel", Color(0, 0, 0, 0.6))
	th.set_constant("shadow_offset_y", "BigLabel", 3)
	# MutedLabel: small spaced labels above a group, and quiet notes
	th.set_type_variation("MutedLabel", "Label")
	th.set_font("font", "MutedLabel", spaced)
	th.set_font_size("font_size", "MutedLabel", 16)
	th.set_color("font_color", "MutedLabel", MUTED)


static func _buttons(th: Theme, bold: Font) -> void:
	# Secondary buttons: raised slate, lit amber edge on hover and press
	th.set_font("font", "Button", bold)
	th.set_font_size("font_size", "Button", 20)
	th.set_color("font_color", "Button", PAPER)
	th.set_color("font_hover_color", "Button", Color.WHITE)
	th.set_color("font_pressed_color", "Button", EMBER_HI)
	th.set_color("font_hover_pressed_color", "Button", EMBER_HI)
	th.set_color("font_focus_color", "Button", PAPER)
	th.set_color("font_disabled_color", "Button", DISABLED_TEXT)
	th.set_constant("h_separation", "Button", 10)
	th.set_stylebox("normal", "Button", _pad(_flat(RAISED, 14, EDGE, 2, 4, 3), 18, 12))
	th.set_stylebox("hover", "Button", _pad(_flat(RAISED_HI, 14, EMBER, 2, 6, 4), 18, 12))
	th.set_stylebox("pressed", "Button", _pad(_flat(INK_DEEP, 14, EMBER, 2, 0, 0), 18, 12, 2))
	th.set_stylebox("hover_pressed", "Button", _pad(_flat(INK_DEEP, 14, EMBER, 2, 0, 0), 18, 12, 2))
	th.set_stylebox("disabled", "Button", _pad(_flat(Color("141d33"), 14, Color("26334f"), 2, 0, 0), 18, 12))
	th.set_stylebox("focus", "Button", _ring(14))

	# PrimaryButton: ember, a dark lip underneath, a faint glow; pressing sinks it onto the lip
	th.set_type_variation("PrimaryButton", "Button")
	th.set_font("font", "PrimaryButton", bold)
	th.set_font_size("font_size", "PrimaryButton", 22)
	th.set_color("font_color", "PrimaryButton", ON_EMBER)
	th.set_color("font_hover_color", "PrimaryButton", ON_EMBER)
	th.set_color("font_pressed_color", "PrimaryButton", ON_EMBER)
	th.set_color("font_hover_pressed_color", "PrimaryButton", ON_EMBER)
	th.set_color("font_focus_color", "PrimaryButton", ON_EMBER)
	th.set_color("font_disabled_color", "PrimaryButton", Color("b4bdd0"))
	th.set_stylebox("normal", "PrimaryButton", _lip(EMBER, EMBER_LIP, 5, true))
	th.set_stylebox("hover", "PrimaryButton", _lip(EMBER_HI, EMBER_LIP, 5, true))
	th.set_stylebox("pressed", "PrimaryButton", _lip(EMBER_LO, EMBER_LIP, 2, false))
	th.set_stylebox("hover_pressed", "PrimaryButton", _lip(EMBER_LO, EMBER_LIP, 2, false))
	th.set_stylebox("disabled", "PrimaryButton", _lip(Color("2b3550"), Color("1a2238"), 5, false))
	th.set_stylebox("focus", "PrimaryButton", _ring(16))

	# ChosenButton: the move / target / amount you have picked (not used by a screen yet, see REQUESTS.md). A lit ember
	# frame on a warm dark fill, so a pick reads as "selected" in greyscale too: a thick bright frame, not just a hue.
	th.set_type_variation("ChosenButton", "Button")
	th.set_font("font", "ChosenButton", bold)
	th.set_font_size("font_size", "ChosenButton", 20)
	for k in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
		th.set_color(k, "ChosenButton", EMBER_HI)
	th.set_color("font_disabled_color", "ChosenButton", Color("e0b878"))
	var chosen := _pad(_flat(Color("33281a"), 14, EMBER, 4, 10, 0), 18, 12)
	chosen.shadow_color = Color(EMBER, 0.32)
	th.set_stylebox("normal", "ChosenButton", chosen)
	th.set_stylebox("hover", "ChosenButton", chosen)
	th.set_stylebox("pressed", "ChosenButton", chosen)
	th.set_stylebox("hover_pressed", "ChosenButton", chosen)
	th.set_stylebox("disabled", "ChosenButton", _pad(_flat(Color("2a2218"), 14, Color("a8782f"), 4, 0, 0), 18, 12))
	th.set_stylebox("focus", "ChosenButton", _ring(14))


static func _timer_bar(th: Theme) -> void:
	var track := _flat(INK_DEEP, 8, Color("33477a"), 2, 0, 0)
	var fill := _flat(EMBER, 8, Color("ffe2b0"), 0, 0, 0)       # a lit top edge and an ember glow: the clock is the hot thing
	fill.border_width_top = 3
	fill.shadow_size = 7
	fill.shadow_color = Color(EMBER, 0.4)
	th.set_stylebox("background", "ProgressBar", track)
	th.set_stylebox("fill", "ProgressBar", fill)
	th.set_color("font_color", "ProgressBar", PAPER)
	# UrgentBar: the same bar in coral for the last seconds (not used by a screen yet, see REQUESTS.md). The number beside
	# it keeps counting, so the warning is never colour alone.
	th.set_type_variation("UrgentBar", "ProgressBar")
	th.set_stylebox("background", "UrgentBar", track)
	var hot := _flat(Color("ff7466"), 8, Color("ffc2ba"), 0, 0, 0)
	hot.border_width_top = 3
	hot.shadow_size = 8
	hot.shadow_color = Color(1.0, 0.45, 0.4, 0.5)
	th.set_stylebox("fill", "UrgentBar", hot)


static func _inputs(th: Theme) -> void:
	th.set_font_size("font_size", "LineEdit", 20)
	th.set_color("font_color", "LineEdit", PAPER)
	th.set_color("font_placeholder_color", "LineEdit", Color("8d9ab3"))
	th.set_color("font_uneditable_color", "LineEdit", MUTED)
	th.set_color("caret_color", "LineEdit", EMBER)
	th.set_color("selection_color", "LineEdit", Color(EMBER, 0.4))
	th.set_constant("caret_width", "LineEdit", 3)
	th.set_stylebox("normal", "LineEdit", _pad(_flat(INK_DEEP, 12, EDGE, 2, 0, 0), 14, 11))
	th.set_stylebox("focus", "LineEdit", _pad(_flat(INK_DEEP, 12, EMBER, 3, 0, 0), 14, 11))
	th.set_stylebox("read_only", "LineEdit", _pad(_flat(Color("141d33"), 12, Color("26334f"), 2, 0, 0), 14, 11))


static func _scroll(th: Theme) -> void:
	# The page backdrop: a firelight glow from the bottom edge. It sits in the ScrollContainer's panel slot and is
	# grown by the page's 16 px side margin so it reaches the window edge. Only the glow is decoration; text never
	# sits on anything lighter than #3a2530.
	var g := Gradient.new()
	# The glow fades to exactly the clear colour (0b1120) before it reaches the sides, so the 16 px margin the
	# ScrollContainer clips away is invisible: no frame.
	g.offsets = PackedFloat32Array([0.0, 0.22, 0.6, 1.0])
	g.colors = PackedColorArray([Color("5a322e"), Color("17223d"), Color("0b1120"), Color("0b1120")])
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.width = 128
	tex.height = 256
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 1.08)
	tex.fill_to = Vector2(0.5, -0.1)
	var back := StyleBoxTexture.new()
	back.texture = tex
	back.set_expand_margin_all(16)
	th.set_stylebox("panel", "ScrollContainer", back)
	for kind in ["VScrollBar", "HScrollBar"]:
		th.set_stylebox("scroll", kind, _pad(_flat(Color(1, 1, 1, 0.05), 6, Color(0, 0, 0, 0), 0, 0, 0), 4, 4))
		th.set_stylebox("grabber", kind, _pad(_flat(Color("6b82b3"), 6, Color(0, 0, 0, 0), 0, 0, 0), 5, 5))
		th.set_stylebox("grabber_highlight", kind, _pad(_flat(EMBER_LO, 6, Color(0, 0, 0, 0), 0, 0, 0), 5, 5))
		th.set_stylebox("grabber_pressed", kind, _pad(_flat(EMBER, 6, Color(0, 0, 0, 0), 0, 0, 0), 5, 5))
	th.set_constant("h_separation", "FlowContainer", 10)
	th.set_constant("v_separation", "FlowContainer", 10)
	th.set_constant("separation", "HBoxContainer", 12)
	th.set_constant("h_separation", "GridContainer", 8)
	th.set_constant("v_separation", "GridContainer", 10)


static func _panels(th: Theme) -> void:
	# A card for grouping (no screen asks for one yet; see REQUESTS.md)
	var card := _pad(_flat(SURFACE, 18, Color("33477a"), 2, 10, 4), 18, 16)
	th.set_stylebox("panel", "PanelContainer", card)
	th.set_type_variation("Card", "PanelContainer")
	th.set_stylebox("panel", "Card", card)
	th.set_type_variation("Banner", "PanelContainer")
	th.set_stylebox("panel", "Banner", _pad(_flat(Color("3a1f26"), 14, Color("ff7a6b"), 2, 8, 3), 16, 10))
	var tip := _pad(_flat(INK_DEEP, 10, EDGE, 1, 6, 2), 12, 8)
	th.set_stylebox("panel", "TooltipPanel", tip)
	th.set_color("font_color", "TooltipLabel", PAPER)


static func _stage(th: Theme) -> void:
	# The reveal's named colours. Light-on-dark; each is told apart from its neighbours by shape in the Stage's own
	# drawing as well (disc, ring, cross, diamond), so none carries meaning alone.
	var c := {
		"text": PAPER,
		"home": Color("4f69a3"),         # another camp's shelter: slate blue, 3:1 against the sky
		"home_me": EMBER,                # mine: ember, much lighter than the rest (also labelled with my food)
		"food": Color("ffd56b"),         # rations in motion: gold
		"loss": Color("ff7466"),         # a loss, a bandit ring: coral
		"shield": Color("6fdcf0"),       # a guard: cyan
		"marked": Color("d9a8ff"),       # caught or exposed: violet
	}
	for k in c:
		th.set_color(k, "Stage", c[k])


# ---------------- stylebox helpers ----------------

## A rounded flat box with an optional border and a soft drop shadow.
static func _flat(bg: Color, radius: int, border: Color, border_w: int, shadow: int, shadow_dy: int) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(radius)
	if border_w > 0:
		s.border_color = border
		s.set_border_width_all(border_w)
	if shadow > 0:
		s.shadow_size = shadow
		s.shadow_offset = Vector2(0, shadow_dy)
		s.shadow_color = Color(0, 0, 0, 0.5)
	return s


## Content margins (a press shifts the label down `sink` pixels by moving a margin from the bottom to the top).
static func _pad(s: StyleBoxFlat, x: float, y: float, sink := 0.0) -> StyleBoxFlat:
	s.content_margin_left = x
	s.content_margin_right = x
	s.content_margin_top = y + sink
	s.content_margin_bottom = y - sink
	return s


## The primary button's body: a fill and a darker lip along the bottom edge (a pressed button has a thin lip).
static func _lip(fill: Color, lip: Color, lip_w: int, glow: bool) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = fill
	s.set_corner_radius_all(16)
	s.border_color = lip
	s.border_width_bottom = lip_w
	s.content_margin_left = 22
	s.content_margin_right = 22
	s.content_margin_top = 12 + (5 - lip_w)           # a pressed button sinks onto its thin lip: the label moves down
	s.content_margin_bottom = 12 - (5 - lip_w)
	if glow:
		s.shadow_size = 12
		s.shadow_offset = Vector2(0, 4)
		s.shadow_color = Color(EMBER, 0.28)
	return s


## The keyboard focus ring: an outline only, drawn just outside the button.
static func _ring(radius: int) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.draw_center = false
	s.set_corner_radius_all(radius)
	s.border_color = FOCUS
	s.set_border_width_all(3)
	s.set_expand_margin_all(3)
	return s
