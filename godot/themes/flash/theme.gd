extends RefCounted
## The "flash" theme: a camp on a dark island, ten nights long. A painted night scene behind everything, wooden
## buttons, card panels with a lit edge, medallion moves, huts and a campfire on the reveal.
##
## The look in one line each:
##  - World: parallax backdrop, drifting fog, twinkling stars, rising embers, a vignette (stage/backdrop.gd draws them
##    from art ids and the "ambient" / "embers" / "flicker" effect settings below).
##  - Chrome: wood buttons (button_wood nine-slice), card_frame panels, one ember accent for "the thing you act on".
##  - Accessibility: every text colour is 7:1 or better on its surface; state is never colour alone (words, shapes and
##    icons carry it); a 3 px cyan focus ring on keyboard focus; "reduced motion" turns off shake, particles, drift.
##
## Everything visual lives in this folder. Screens name a type variation, an art id or an effect name only. Art comes
## from FlashArt (art/<id>.png first, art_standin/<id>.png second). Regenerate words with tools/gen_flash_words.py,
## icons with tools/gen_flash_icons.py and stand-in art with tools/gen_flash_standins.py.

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
const DISABLED_TEXT := Color("9aa6bf")
const WOOD_TEXT := Color("2b1608")         # text on the light wood of a primary button
const CARD_X := 34.0                       # content margins of every card_frame panel (clear of the frame art, see build())
const CARD_Y := 28.0
const SHORT_TOP := 34                    # fixed top edge (texture px) of the ordinary, 56 px wood button
const SHORT_BOTTOM := 20                   # fixed bottom edge: the rim and the lip
const SHORT_CTOP := 3.0                    # content margins of that button: tuned so the label sits on the lit face
const SHORT_CBOTTOM := 19.0                # (their SUM stays 22 in both states, so a press never changes the button's height)
const SHORT_CTOP_DOWN := 6.5
const SHORT_CBOTTOM_DOWN := 15.5
const PLAYER_X := 16.0                    # a person card you can press: the same margins selected or not
const PLAYER_Y := 10.0

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
	# the end screen's marks
	"mark.seat": preload("res://themes/flash/icons/helicopter.svg"),
	# what the round screen asks for by model id (a resource, a status)
	"resource.ration": preload("res://themes/flash/icons/food.svg"),
	"status.shield": preload("res://themes/flash/icons/shield.svg"),
	"status.outcast": preload("res://themes/flash/icons/bandit.svg"),
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
	t.texture_source = FlashArt.load_texture
	t.clear_color = Color("0b1120")
	t.colors = _colors()
	t.fx = _fx()
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

	var wood := FlashArt.load_texture("button_wood")
	var wood_down := FlashArt.load_texture("button_wood_pressed")
	var frame := FlashArt.load_texture("card_frame")
	if frame != null:
		# The frame art is about 23 px thick with brackets reaching further in at the corners. Content must clear all of it,
		# so every card (normal, lit, a pick) shares these margins: a highlighted row differs by COLOUR only, never by layout.
		t.nine_patches["card_frame"] = _nine(frame, 40, 40, 40, 40, CARD_X, CARD_Y, CARD_X, CARD_Y)
	if wood != null:
		# Measured on the art (tools: see the face rows in the notes): the lit face of the normal button spans rows 6..80 of
		# the 96 px (1x) texture, so its centre is 5 px ABOVE the texture's middle (the lip is underneath). A label centred
		# in the content rect lands at h/2 + (top - bottom)/2, so top - bottom = -10 puts it on the face; -12 was the value the
		# render probe (tests/perf/button_centre.gd) found centres the capitals best (text 2 px low before, <= 1 px now).
		t.nine_patches["button_wood"] = _nine(wood, 36, 30, 36, 30, 26, 5, 26, 17)
	if wood_down != null:
		# the pressed face spans rows 11..86: centre 0.5 px below the middle, so top - bottom = +1 (5.5 px lower than normal)
		t.nine_patches["button_wood_pressed"] = _nine(wood_down, 36, 30, 36, 30, 26, 12, 26, 11)
	if wood != null and wood_down != null:
		# The ordinary buttons are 56 px high, LESS than the 60 px of fixed edge above (30 + 30): Godot then shrinks both edges and
		# drops the stretch zone, so the lower, darker plank is drawn right under the label and the word sits low on a face that
		# looks 20 px high. Short fixed edges (top 34 = the lit face to its seam, bottom 20 = the rim and the lip) leave a stretch
		# zone at 56 px, so the lit face keeps its proportions. Measured by tests/perf/button_centre.gd.
		t.nine_patches["button_wood_short"] = _nine(wood, 36, SHORT_TOP, 36, SHORT_BOTTOM, 26, SHORT_CTOP, 26, SHORT_CBOTTOM)
		t.nine_patches["button_wood_short_pressed"] = _nine(wood_down, 36, SHORT_TOP, 36, SHORT_BOTTOM, 26, SHORT_CTOP_DOWN, 26, SHORT_CBOTTOM_DOWN)

	_labels(th, bold, spaced)
	_buttons(th, bold, t)
	_cards(th, t, bold)
	_timer_bar(th)
	_inputs(th)
	_scroll(th)
	_stage(th, t)
	return t


# ---------------- colours and effects ----------------

static func _colors() -> Dictionary:
	return {
		"white": Color.WHITE, "clear": Color(1, 1, 1, 0), "shade": Color(0.02, 0.04, 0.09, 0.62), "ink": INK_DEEP,
		"warm": Color("ff9a3c"), "cold": Color("5a8cff"), "hit": Color("ff3b3b"), "glow": Color("ffb45a"),
		"star": Color("dfe8ff"), "ember": EMBER, "fog": Color("b8c4ee"), "gold": Color("ffd56b"),
		"gain": Color("ffe27a"), "loss": Color("ff7466"), "shield": Color("6fdcf0"), "mark": Color("d9a8ff"),
		"ring_track": Color("0a0f1c", 0.78), "ring_fill": Color("bfe6ff"), "ring_warn": EMBER, "ring_urgent": Color("ff5a4a"),
		"lock_fill": Color(1.0, 0.93, 0.7, 0.32),
	}


## Effect settings. Durations in seconds; "motion": true effects vanish under reduced motion (Themes.fx returns {}).
## The names are the only contract with stage/ and screens/: grep Themes.fx there for every consumer.
static func _fx() -> Dictionary:
	return {
		# the persistent scene behind every screen (stage/backdrop.gd)
		"ambient": {"stars": 46, "fog_layers": 2, "parallax_px": 16.0, "drift_px": 10.0, "motion": true},
		"embers": {"amount": 34, "lifetime": 6.0, "motion": true},
		"flicker": {"strength": 0.2, "motion": true},
		# screen-to-screen
		"transition": {"fade": 0.18, "slide": 24.0},
		# buttons and entrances (screens/ui.gd)
		"press": {"down": 0.93, "up": 1.07, "time": 0.2},
		"intro": {"time": 0.38, "rise": 28.0, "stagger": 0.07},
		"logo": {"bob_px": 7.0, "bob_s": 2.8, "glow_s": 1.9, "has_title": true},
		"pulse": {"scale": 0.05, "time": 0.45, "last_s": 10},
		# the clock's stages (seconds left): running short, urgent; and when an unpicked player is called to act
		"timer": {"warn_s": 30, "urgent_s": 10, "prompt_s": 20},
		"lift": {"scale": 1.12, "time": 0.24},
		# the reveal (stage/stage.gd)
		"stage.crumbs": {"max": 8, "flight": 0.62, "stagger": 0.07, "arc": 0.3, "size": 24.0, "trail_every": 0.03,
			"motion": true},
		"stage.float": {"rise": 52.0, "time": 1.0},
		"stage.burst": {"sparks": 12, "speed": 190.0, "motion": true},
		"stage.pop": {"time": 0.55},
		# which colour a kind of movement is tinted by (the ruleset's style ids -> colour names; the rest is untinted)
		"stage.style": {"steal": "loss", "robbed": "loss", "hit": "loss", "fine": "mark", "bounty": "mark", "return": "gold",
			"gift": "gold", "default": "white"},
		"beat.blocked.impact": {"shake": 12.0, "flash": 0.32, "pause_ms": 80, "motion": true},
		"beat.blocked.impact.idol": {"shake": 3.0, "flash": 0.0, "pause_ms": 0, "motion": true},
		"wash": {"alpha": 0.26, "default": "cold", "feast": "warm"},
	}


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
	th.set_constant("outline_size", "BigLabel", 6)
	th.set_color("font_outline_color", "BigLabel", Color("1c0f08"))
	# CodeLabel: the camp code on the lobby sign, the biggest thing on that screen; letters spaced so it reads at arm's length
	var code_font := FontVariation.new()
	code_font.base_font = ThemeDB.fallback_font
	code_font.variation_embolden = 0.75
	code_font.spacing_glyph = 10
	th.set_type_variation("CodeLabel", "Label")
	th.set_font("font", "CodeLabel", code_font)
	th.set_font_size("font_size", "CodeLabel", 84)
	th.set_color("font_color", "CodeLabel", EMBER_HI)
	th.set_color("font_shadow_color", "CodeLabel", Color(0, 0, 0, 0.6))
	th.set_constant("shadow_offset_y", "CodeLabel", 4)
	th.set_constant("outline_size", "CodeLabel", 8)
	th.set_color("font_outline_color", "CodeLabel", Color("1c0f08"))
	# YouLabel: who you are, in the heads-up card: ember, big enough to find first, smaller than the app name
	th.set_type_variation("YouLabel", "Label")
	th.set_font("font", "YouLabel", bold)
	th.set_font_size("font_size", "YouLabel", 30)
	th.set_color("font_color", "YouLabel", EMBER_HI)
	th.set_color("font_shadow_color", "YouLabel", Color(0, 0, 0, 0.6))
	th.set_constant("shadow_offset_y", "YouLabel", 3)
	th.set_constant("outline_size", "YouLabel", 5)
	th.set_color("font_outline_color", "YouLabel", Color("1c0f08"))
	# TimerWarn / TimerUrgent: the clock's number as time runs short: amber, then bigger and red (never colour alone)
	th.set_type_variation("TimerWarn", "HeaderLabel")
	th.set_color("font_color", "TimerWarn", EMBER)
	th.set_type_variation("TimerUrgent", "HeaderLabel")
	th.set_font_size("font_size", "TimerUrgent", 34)
	th.set_color("font_color", "TimerUrgent", Color("ff8a7a"))
	th.set_constant("outline_size", "TimerUrgent", 6)
	th.set_color("font_outline_color", "TimerUrgent", Color("3a0f0c"))
	# PromptLabel: the line above the moves when time is short and nothing is picked: a call to act
	th.set_type_variation("PromptLabel", "Label")
	th.set_font("font", "PromptLabel", bold)
	th.set_font_size("font_size", "PromptLabel", 24)
	th.set_color("font_color", "PromptLabel", EMBER_HI)
	th.set_constant("outline_size", "PromptLabel", 6)
	th.set_color("font_outline_color", "PromptLabel", Color("2a1206"))
	# NameLabel: a player's name on a card: one line, never broken mid-word
	th.set_type_variation("NameLabel", "Label")
	th.set_font("font", "NameLabel", bold)
	th.set_font_size("font_size", "NameLabel", 22)
	th.set_color("font_shadow_color", "NameLabel", Color(0, 0, 0, 0.5))
	th.set_constant("shadow_offset_y", "NameLabel", 2)
	# StatLabel: a number on a results card
	th.set_type_variation("StatLabel", "Label")
	th.set_font("font", "StatLabel", bold)
	th.set_font_size("font_size", "StatLabel", 26)
	th.set_color("font_shadow_color", "StatLabel", Color(0, 0, 0, 0.5))
	th.set_constant("shadow_offset_y", "StatLabel", 2)
	# StatLabelHot: the highest number of its column (also bracketed in the text, so colour is never the only sign)
	th.set_type_variation("StatLabelHot", "StatLabel")
	th.set_color("font_color", "StatLabelHot", EMBER_HI)
	# RankLabel: the big numeral on a podium step
	th.set_type_variation("RankLabel", "Label")
	th.set_font("font", "RankLabel", bold)
	th.set_font_size("font_size", "RankLabel", 44)
	th.set_color("font_color", "RankLabel", EMBER_HI)
	th.set_constant("outline_size", "RankLabel", 8)
	th.set_color("font_outline_color", "RankLabel", Color("1c0f08"))
	# MutedLabel: small spaced labels above a group, and quiet notes
	th.set_type_variation("MutedLabel", "Label")
	th.set_font("font", "MutedLabel", spaced)
	th.set_font_size("font_size", "MutedLabel", 16)
	th.set_color("font_color", "MutedLabel", MUTED)
	th.set_color("font_shadow_color", "MutedLabel", Color(0, 0, 0, 0.5))
	th.set_constant("shadow_offset_y", "MutedLabel", 1)


static func _buttons(th: Theme, bold: Font, t: ThemeDef) -> void:
	var wood: StyleBox = t.nine_patches.get("button_wood")
	var wood_down: StyleBox = t.nine_patches.get("button_wood_pressed")
	var short_up: StyleBox = t.nine_patches.get("button_wood_short")
	var short_down: StyleBox = t.nine_patches.get("button_wood_short_pressed")

	# Secondary buttons: dark wood (or raised slate with no art)
	th.set_font("font", "Button", bold)
	th.set_font_size("font_size", "Button", 21)
	th.set_color("font_color", "Button", PAPER)
	th.set_color("font_hover_color", "Button", Color.WHITE)
	th.set_color("font_pressed_color", "Button", EMBER_HI)
	th.set_color("font_hover_pressed_color", "Button", EMBER_HI)
	th.set_color("font_focus_color", "Button", PAPER)
	th.set_color("font_disabled_color", "Button", DISABLED_TEXT)
	th.set_color("font_outline_color", "Button", Color("1c0f08"))
	th.set_constant("outline_size", "Button", 4)
	th.set_constant("h_separation", "Button", 10)
	if wood != null:
		var dark := Color(0.66, 0.6, 0.68)
		th.set_stylebox("normal", "Button", _tint(short_up, dark))
		th.set_stylebox("hover", "Button", _tint(short_up, Color(0.8, 0.74, 0.8)))
		th.set_stylebox("pressed", "Button", _tint(short_down, dark))
		th.set_stylebox("hover_pressed", "Button", _tint(short_down, Color(0.8, 0.74, 0.8)))
		th.set_stylebox("disabled", "Button", _tint(short_up, Color(0.36, 0.36, 0.44, 0.92)))
	else:
		th.set_stylebox("normal", "Button", _pad(_flat(RAISED, 14, EDGE, 2, 4, 3), 18, 12))
		th.set_stylebox("hover", "Button", _pad(_flat(RAISED_HI, 14, EMBER, 2, 6, 4), 18, 12))
		th.set_stylebox("pressed", "Button", _pad(_flat(INK_DEEP, 14, EMBER, 2, 0, 0), 18, 12, 2))
		th.set_stylebox("hover_pressed", "Button", _pad(_flat(INK_DEEP, 14, EMBER, 2, 0, 0), 18, 12, 2))
		th.set_stylebox("disabled", "Button", _pad(_flat(Color("141d33"), 14, Color("26334f"), 2, 0, 0), 18, 12))
	th.set_stylebox("focus", "Button", _ring(18))

	# PrimaryButton: light, warm wood, big dark lettering; pressing sinks it onto its lip
	th.set_type_variation("PrimaryButton", "Button")
	th.set_font("font", "PrimaryButton", bold)
	th.set_font_size("font_size", "PrimaryButton", 26)
	for k in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
		th.set_color(k, "PrimaryButton", WOOD_TEXT if wood != null else ON_EMBER)
	th.set_color("font_disabled_color", "PrimaryButton", Color("d0c6b8") if wood != null else Color("b4bdd0"))
	th.set_constant("outline_size", "PrimaryButton", 0)
	if wood != null:
		th.set_stylebox("normal", "PrimaryButton", _tint(wood, Color(1.18, 1.08, 0.9)))
		th.set_stylebox("hover", "PrimaryButton", _tint(wood, Color(1.3, 1.2, 1.0)))
		th.set_stylebox("pressed", "PrimaryButton", _tint(wood_down, Color(1.1, 1.0, 0.85)))
		th.set_stylebox("hover_pressed", "PrimaryButton", _tint(wood_down, Color(1.1, 1.0, 0.85)))
		th.set_stylebox("disabled", "PrimaryButton", _tint(wood, Color(0.5, 0.48, 0.5, 0.95)))
	else:
		th.set_stylebox("normal", "PrimaryButton", _lip(EMBER, EMBER_LIP, 5, true))
		th.set_stylebox("hover", "PrimaryButton", _lip(EMBER_HI, EMBER_LIP, 5, true))
		th.set_stylebox("pressed", "PrimaryButton", _lip(EMBER_LO, EMBER_LIP, 2, false))
		th.set_stylebox("hover_pressed", "PrimaryButton", _lip(EMBER_LO, EMBER_LIP, 2, false))
		th.set_stylebox("disabled", "PrimaryButton", _lip(Color("2b3550"), Color("1a2238"), 5, false))
	th.set_stylebox("focus", "PrimaryButton", _ring(18))

	# ChosenButton: the pick you made (an amount): a lit ember frame on a warm dark fill, thick enough to read in greyscale
	th.set_type_variation("ChosenButton", "Button")
	th.set_font("font", "ChosenButton", bold)
	th.set_font_size("font_size", "ChosenButton", 22)
	for k in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_focus_color"]:
		th.set_color(k, "ChosenButton", EMBER_HI)
	th.set_color("font_disabled_color", "ChosenButton", Color("e0b878"))
	var chosen := _pad(_flat(Color("33281a"), 16, EMBER, 4, 10, 0), 20, 12)
	chosen.shadow_color = Color(EMBER, 0.34)
	for s in ["normal", "hover", "pressed", "hover_pressed"]:
		th.set_stylebox(s, "ChosenButton", chosen)
	th.set_stylebox("disabled", "ChosenButton", _pad(_flat(Color("2a2218"), 16, Color("a8782f"), 4, 0, 0), 20, 12))
	th.set_stylebox("focus", "ChosenButton", _ring(16))

	# MoveButton: a medallion with its word underneath. No box of its own: the picture is the button.
	th.set_type_variation("MoveButton", "Button")
	th.set_font("font", "MoveButton", bold)
	th.set_font_size("font_size", "MoveButton", 17)
	th.set_constant("outline_size", "MoveButton", 5)
	th.set_constant("h_separation", "MoveButton", 4)
	th.set_constant("icon_max_width", "MoveButton", 92)
	th.set_color("font_color", "MoveButton", PAPER)
	th.set_color("font_hover_color", "MoveButton", Color.WHITE)
	th.set_color("font_pressed_color", "MoveButton", EMBER_HI)
	th.set_color("font_hover_pressed_color", "MoveButton", EMBER_HI)
	th.set_color("font_disabled_color", "MoveButton", Color("b6bfd4"))
	var empty := StyleBoxEmpty.new()
	empty.content_margin_left = 2
	empty.content_margin_right = 2
	empty.content_margin_top = 4
	empty.content_margin_bottom = 32                   # room for the caption (a label laid over the foot of the button)
	for s in ["normal", "hover", "pressed", "hover_pressed", "disabled"]:
		th.set_stylebox(s, "MoveButton", empty)
	th.set_stylebox("focus", "MoveButton", _ring(20))
	# MoveCaption: the word under a medallion; one line, shrunk to fit by the screen (FitLabel)
	th.set_type_variation("MoveCaption", "Label")
	th.set_font("font", "MoveCaption", bold)
	th.set_font_size("font_size", "MoveCaption", 17)
	th.set_constant("outline_size", "MoveCaption", 5)
	th.set_color("font_color", "MoveCaption", PAPER)
	th.set_color("font_outline_color", "MoveCaption", Color("0a0f1c"))
	th.set_type_variation("MoveCaptionChosen", "MoveCaption")
	th.set_color("font_color", "MoveCaptionChosen", EMBER_HI)
	# MoveButtonChosen: the medallion you picked (its glow ring and lift are the screen's; this adds the word)
	th.set_type_variation("MoveButtonChosen", "MoveButton")
	for k in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_disabled_color"]:
		th.set_color(k, "MoveButtonChosen", EMBER_HI)

	# PlayerCard: a person you can pick: avatar, name, band (a card you can press)
	th.set_type_variation("PlayerCard", "Button")
	th.set_font("font", "PlayerCard", bold)
	th.set_font_size("font_size", "PlayerCard", 20)
	th.set_constant("outline_size", "PlayerCard", 4)
	th.set_constant("icon_max_width", "PlayerCard", 52)
	th.set_constant("h_separation", "PlayerCard", 12)
	# Flat dark cards with a brass rim, NOT the ornate frame: a compact card cannot hold two lines inside a frame that is 24 px
	# thick. Normal, hover, pressed and picked share the same padding, so a pick changes colour and rim, never layout.
	th.set_stylebox("normal", "PlayerCard", _pad(_flat(Color(0.06, 0.09, 0.17, 0.9), 14, Color("a8803a"), 2, 4, 2), PLAYER_X, PLAYER_Y))
	th.set_stylebox("hover", "PlayerCard", _pad(_flat(Color(0.12, 0.16, 0.28, 0.95), 14, EMBER_HI, 2, 6, 2), PLAYER_X, PLAYER_Y))
	th.set_stylebox("pressed", "PlayerCard", _pad(_flat(Color(0.03, 0.05, 0.1, 0.95), 14, EMBER, 2, 0, 0), PLAYER_X, PLAYER_Y))
	th.set_stylebox("hover_pressed", "PlayerCard", _pad(_flat(Color(0.03, 0.05, 0.1, 0.95), 14, EMBER, 2, 0, 0), PLAYER_X, PLAYER_Y))
	th.set_stylebox("disabled", "PlayerCard", _pad(_flat(Color(0.05, 0.07, 0.12, 0.7), 14, Color("5a4a2a"), 2, 0, 0), PLAYER_X, PLAYER_Y))
	th.set_stylebox("focus", "PlayerCard", _ring(18))
	th.set_type_variation("PlayerCardChosen", "PlayerCard")
	for k in ["font_color", "font_hover_color", "font_pressed_color", "font_hover_pressed_color", "font_disabled_color"]:
		th.set_color(k, "PlayerCardChosen", EMBER_HI)
	var picked := _pad(_flat(Color("33281a"), 18, EMBER, 4, 10, 0), PLAYER_X, PLAYER_Y)
	picked.shadow_color = Color(EMBER, 0.34)
	for s in ["normal", "hover", "pressed", "hover_pressed", "disabled"]:
		th.set_stylebox(s, "PlayerCardChosen", picked)

	# CampCard: one open camp in the title screen's list: the same flat card as a person card (its content is laid on top
	# by screens/open_camps.gd using this style's own margins)
	th.set_type_variation("CampCard", "PlayerCard")

	# SkipPill: small and unobtrusive
	th.set_type_variation("SkipPill", "Button")
	th.set_font("font", "SkipPill", bold)
	th.set_font_size("font_size", "SkipPill", 15)
	th.set_constant("outline_size", "SkipPill", 0)
	th.set_color("font_color", "SkipPill", MUTED)
	th.set_color("font_hover_color", "SkipPill", Color.WHITE)
	th.set_color("font_pressed_color", "SkipPill", EMBER_HI)
	var pill := _flat(Color(0.04, 0.06, 0.12, 0.62), 22, Color(0.8, 0.85, 0.95, 0.35), 1, 0, 0)
	pill.content_margin_left = 16
	pill.content_margin_right = 16
	pill.content_margin_top = 6
	pill.content_margin_bottom = 6
	var pill_hi := pill.duplicate() as StyleBoxFlat
	pill_hi.bg_color = Color(0.1, 0.14, 0.26, 0.85)
	pill_hi.border_color = EMBER
	for s in ["normal", "disabled"]:
		th.set_stylebox(s, "SkipPill", pill)
	for s in ["hover", "pressed", "hover_pressed"]:
		th.set_stylebox(s, "SkipPill", pill_hi)
	th.set_stylebox("focus", "SkipPill", _ring(22))


static func _timer_bar(th: Theme) -> void:
	var track := _flat(INK_DEEP, 8, Color("33477a"), 2, 0, 0)
	var fill := _flat(EMBER, 8, Color("ffe2b0"), 0, 0, 0)       # a lit top edge and an ember glow: the clock is the hot thing
	fill.border_width_top = 3
	fill.shadow_size = 7
	fill.shadow_color = Color(EMBER, 0.4)
	th.set_stylebox("background", "ProgressBar", track)
	th.set_stylebox("fill", "ProgressBar", fill)
	th.set_color("font_color", "ProgressBar", PAPER)
	th.set_type_variation("UrgentBar", "ProgressBar")
	th.set_stylebox("background", "UrgentBar", track)
	var hot := _flat(Color("ff7466"), 8, Color("ffc2ba"), 0, 0, 0)
	hot.border_width_top = 3
	hot.shadow_size = 8
	hot.shadow_color = Color(1.0, 0.45, 0.4, 0.5)
	th.set_stylebox("fill", "UrgentBar", hot)
	# ChargeFill: the Lock button's filling light (screens/charge_fill.gd draws it)
	var charge := _flat(Color(1.0, 0.93, 0.7, 0.34), 14, Color(0, 0, 0, 0), 0, 0, 0)
	th.set_stylebox("fill", "ChargeFill", charge)


static func _inputs(th: Theme) -> void:
	th.set_font_size("font_size", "LineEdit", 22)
	th.set_color("font_color", "LineEdit", PAPER)
	th.set_color("font_placeholder_color", "LineEdit", Color("8d9ab3"))
	th.set_color("font_uneditable_color", "LineEdit", MUTED)
	th.set_color("caret_color", "LineEdit", EMBER)
	th.set_color("selection_color", "LineEdit", Color(EMBER, 0.4))
	th.set_constant("caret_width", "LineEdit", 3)
	th.set_stylebox("normal", "LineEdit", _pad(_flat(Color(0.04, 0.06, 0.12, 0.85), 14, EDGE, 2, 0, 0), 16, 12))
	th.set_stylebox("focus", "LineEdit", _pad(_flat(Color(0.04, 0.06, 0.12, 0.92), 14, EMBER, 3, 0, 0), 16, 12))
	th.set_stylebox("read_only", "LineEdit", _pad(_flat(Color("141d33"), 14, Color("26334f"), 2, 0, 0), 16, 12))


static func _scroll(th: Theme) -> void:
	# The scene behind is the persistent backdrop (stage/backdrop.gd), so a page paints nothing of its own.
	th.set_stylebox("panel", "ScrollContainer", StyleBoxEmpty.new())
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


static func _cards(th: Theme, t: ThemeDef, _bold: Font) -> void:
	var frame: StyleBox = t.nine_patches.get("card_frame")
	var card: StyleBox = frame if frame != null else _pad(_flat(SURFACE, 18, Color("33477a"), 2, 10, 4), 18, 16)
	th.set_stylebox("panel", "PanelContainer", card)
	th.set_type_variation("Card", "PanelContainer")
	th.set_stylebox("panel", "Card", card)
	# CardHot: the line being played right now (a log line): an ember rim around the same card
	th.set_type_variation("CardHot", "PanelContainer")
	if frame != null:
		th.set_stylebox("panel", "CardHot", _tint(frame, Color(1.7, 1.35, 0.95)))          # same margins as Card, by construction
	else:
		th.set_stylebox("panel", "CardHot", _pad(_flat(Color("33281a"), 18, EMBER, 3, 10, 4), 18, 16))   # the plain look: border inside the margin
	# LogLine / LogLineHot: one line of the night's written log: a card, the newest one lit
	th.set_type_variation("LogLine", "PanelContainer")
	th.set_type_variation("LogLineHot", "PanelContainer")
	# a flat dark panel with a brass rim: roomy padding so the words never touch the rim, and the lit line (ember rim, warm
	# fill, same padding so nothing jumps) stays as readable as the rest
	th.set_stylebox("panel", "LogLine", _pad(_flat(Color(0.06, 0.09, 0.17, 0.88), 14, Color("a8803a"), 2, 4, 2), 18, 12))
	th.set_stylebox("panel", "LogLineHot", _pad(_flat(Color(0.2, 0.15, 0.09, 0.94), 14, EMBER, 3, 8, 2), 18, 12))
	# Scrim: a dark plate behind loose text that sits over the scene (a screen title, a clock)
	th.set_type_variation("Scrim", "PanelContainer")
	th.set_stylebox("panel", "Scrim", _pad(_flat(Color(0.03, 0.05, 0.1, 0.8), 14, Color(0.66, 0.5, 0.23, 0.6), 1, 0, 0), 14, 7))
	# Veil: the dimmed backdrop behind a sheet (the "new camp" form) so the screen below reads as put aside
	th.set_type_variation("Veil", "PanelContainer")
	th.set_stylebox("panel", "Veil", _flat(Color(0.02, 0.03, 0.07, 0.8), 0, Color(0, 0, 0, 0), 0, 0, 0))
	# Plate: a small name plate: flat with a brass rim (the ornate frame is too thick for a plate two lines high)
	th.set_type_variation("Plate", "PanelContainer")
	th.set_stylebox("panel", "Plate", _pad(_flat(Color(0.04, 0.06, 0.12, 0.88), 12, Color("a8803a"), 2, 3, 2), 14, 7))
	# Plinth: a podium step
	th.set_type_variation("Plinth", "PanelContainer")
	var step := _flat(Color("3a2a1e"), 10, Color("1c0f08"), 3, 8, 3)
	step.border_width_top = 8
	step.border_color = Color("e0a24a")
	step.content_margin_left = 8
	step.content_margin_right = 8
	step.content_margin_top = 14
	step.content_margin_bottom = 8
	th.set_stylebox("panel", "Plinth", step)
	th.set_type_variation("PlinthFirst", "Plinth")
	var step1 := step.duplicate() as StyleBoxFlat
	step1.bg_color = Color("5a3d1c")
	step1.border_color = Color("ffd56b")
	th.set_stylebox("panel", "PlinthFirst", step1)
	# Dock: the bar at the foot of a screen that holds the main action
	th.set_type_variation("Dock", "PanelContainer")
	var dock := _flat(Color(0.03, 0.05, 0.1, 0.78), 0, Color("e0a24a", 0.55), 0, 0, 0)
	dock.border_width_top = 3
	dock.content_margin_left = 16
	dock.content_margin_right = 16
	dock.content_margin_top = 12
	dock.content_margin_bottom = 14
	th.set_stylebox("panel", "Dock", dock)
	# Banner: a calm notice (still trying to connect): night blue with an amber edge. BannerAlert: something is wrong.
	th.set_type_variation("Banner", "PanelContainer")
	th.set_stylebox("panel", "Banner", _pad(_flat(Color(0.07, 0.1, 0.19, 0.94), 14, Color("e0a24a"), 2, 8, 3), 16, 10))
	th.set_type_variation("BannerAlert", "PanelContainer")
	th.set_stylebox("panel", "BannerAlert", _pad(_flat(Color("3a1f26"), 14, Color("ff7a6b"), 2, 8, 3), 16, 10))
	var tip := _pad(_flat(INK_DEEP, 10, EDGE, 1, 6, 2), 12, 8)
	th.set_stylebox("panel", "TooltipPanel", tip)
	th.set_color("font_color", "TooltipLabel", PAPER)


static func _stage(th: Theme, t: ThemeDef) -> void:
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
	th.set_font_size("plate_size", "Stage", 17)
	# the name plates on the Stage: flat, with a 2-3 px rim; the Stage sizes each one from its content plus these margins
	th.set_constant("plate_edge", "Stage", 3)
	th.set_stylebox("plate", "Stage", _pad(_flat(Color(0.04, 0.06, 0.12, 0.9), 12, Color("a8803a"), 2, 3, 2), 14, 7))
	th.set_stylebox("plate_me", "Stage", _pad(_flat(Color(0.18, 0.12, 0.06, 0.92), 12, EMBER, 3, 4, 2), 14, 7))


# ---------------- stylebox helpers ----------------

## A nine-slice from a texture: texture margins (what must not stretch) and the content margins inside.
static func _nine(tex: Texture2D, ml: int, mt: int, mr: int, mb: int, cl: float, ct: float, cr: float, cb: float) -> StyleBoxTexture:
	var s := StyleBoxTexture.new()
	s.texture = tex
	s.texture_margin_left = ml
	s.texture_margin_top = mt
	s.texture_margin_right = mr
	s.texture_margin_bottom = mb
	s.content_margin_left = cl
	s.content_margin_top = ct
	s.content_margin_right = cr
	s.content_margin_bottom = cb
	s.draw_center = true
	return s


## A copy of a nine-slice, multiplied by a colour; optionally with other content margins.
static func _tint(src: StyleBox, mod: Color, content_x := -1.0, content_y := -1.0) -> StyleBoxTexture:
	var s := (src as StyleBoxTexture).duplicate() as StyleBoxTexture
	s.modulate_color = mod
	if content_x >= 0.0:
		s.content_margin_left = content_x
		s.content_margin_right = content_x
		s.content_margin_top = content_y
		s.content_margin_bottom = content_y
	return s


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


## The primary button's body with no art: a fill and a darker lip along the bottom edge.
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
