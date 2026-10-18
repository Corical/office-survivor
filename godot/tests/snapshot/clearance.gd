class_name Clearance
extends RefCounted
## One automatic check for a whole class of defect: content (text, icons) sitting ON a panel's ornate frame instead of
## inside it. It walks the live scene tree of a screen and reports, with the node path:
##   - every frame-styled panel or button whose content margins do not clear the frame art, and
##   - every Label / icon inside such a panel whose rectangle is not inside the panel's inner rect, and
##   - every item a Stage says it drew over a plate (Stage.plate_items()) that is not inside its plate's inner rect.
## "Clear" = the frame's visible thickness plus CLEARANCE px. The frame art is recognised by its (halved) texture size.
## Returns an Array of strings; empty means clean. Used by the snapshot tool at several window sizes.

const FRAME_ART_SIZE := Vector2(128, 128)      # card_frame after FlashArt halves it
const FRAME_PX := 24.0                          # measured: the visible border of card_frame is about 23 px at 1x
const CLEARANCE := 4.0                          # chosen: the least gap that reads as "inside"
const TOLERANCE := 0.5
const FLOAT_CLEARANCE := 6.0                    # a floating number keeps this far from every plate


static func check(root: Node) -> Array[String]:
	var out: Array[String] = []
	_walk(root, out)
	return out


static func _is_frame(sb: StyleBox) -> bool:
	if not (sb is StyleBoxTexture):
		return false
	var tex: Texture2D = (sb as StyleBoxTexture).texture
	return tex != null and tex.get_size() == FRAME_ART_SIZE


static func _walk(n: Node, out: Array[String]) -> void:
	if n is Control and not (n as Control).visible:
		return
	if n is PanelContainer:
		var sb := (n as Control).get_theme_stylebox("panel")
		if _is_frame(sb):
			_check_panel(n as Control, sb, out)
	elif n is Button:
		var sb := (n as Control).get_theme_stylebox("normal")
		if _is_frame(sb):
			_check_margins(n as Control, sb, out)
	if n is Label and (n as Label).clip_text:
		_check_trim(n as Label, out)
	if n.has_method("plate_items"):
		_check_plates(n, out)
	if n.has_method("float_items"):
		_check_floats(n, out)
	for c in n.get_children():
		_walk(c, out)


## A clipped label (a name, a number) must show ALL of its text: on one line, or on its two lines. If the text is wider than the
## room it has, it is being cut ("You are Quie...") and that is a defect at any size a player can have.
static func _check_trim(l: Label, out: Array[String]) -> void:
	if l.text == "" or l.size.x < 8.0:
		return
	var s := l.label_settings.font_size if l.label_settings != null else l.get_theme_font_size("font_size")
	var font := l.label_settings.font if (l.label_settings != null and l.label_settings.font != null) else l.get_theme_font("font")
	var w := font.get_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, -1, s).x
	var room := l.size.x
	if l.autowrap_mode == TextServer.AUTOWRAP_OFF:
		if w > room + TOLERANCE:
			out.append("%s: label '%s' is cut off: its text is %.0f px wide and it has %.0f px" % [l.get_path(), l.text, w, room])
	elif l.max_lines_visible > 0 and w > room * float(l.max_lines_visible) - 4.0:
		out.append("%s: label '%s' does not fit even on %d lines (%.0f px of text, %.0f px a line)" % [l.get_path(), l.text,
			l.max_lines_visible, w, room])


static func _check_margins(c: Control, sb: StyleBox, out: Array[String]) -> void:
	var need := FRAME_PX + CLEARANCE
	for side in [SIDE_LEFT, SIDE_TOP, SIDE_RIGHT, SIDE_BOTTOM]:
		var m := sb.get_margin(side)
		if m + TOLERANCE < need:
			out.append("%s: frame-styled content margin %s is %.0f px, needs %.0f" % [c.get_path(), _side(side), m, need])


static func _check_panel(panel: Control, sb: StyleBox, out: Array[String]) -> void:
	_check_margins(panel, sb, out)
	var inner := panel.get_global_rect().grow(-(FRAME_PX + CLEARANCE))
	for d in _content(panel):
		var r: Rect2 = (d as Control).get_global_rect()
		if not inner.grow(TOLERANCE).encloses(r):
			out.append("%s: %s rect %s is outside the frame's inner rect %s" % [d.get_path(), _what(d), r, inner])


## Labels with text and pictures below `panel`, not looking inside a nested frame (it checks its own).
static func _content(panel: Node) -> Array:
	var found: Array = []
	for c in panel.get_children():
		if c is Control and not (c as Control).visible:
			continue
		if c is Label and (c as Label).text != "":
			found.append(c)
		elif c is TextureRect and (c as TextureRect).texture != null:
			found.append(c)
		if not (c is PanelContainer and _is_frame((c as Control).get_theme_stylebox("panel"))):
			found.append_array(_content(c))
	return found


static func _check_plates(stage: Node, out: Array[String]) -> void:
	for it in stage.plate_items():
		var inner: Rect2 = (it.frame as Rect2).grow(-(float(it.edge) + CLEARANCE))
		if not inner.grow(TOLERANCE).encloses(it.rect):
			out.append("%s: %s rect %s is outside the plate's inner rect %s" % [it.path, it.what, it.rect, inner])


## Floating numbers (+N / -N) must never touch a plate (6 px clear) nor another number.
static func _check_floats(stage: Node, out: Array[String]) -> void:
	var floats: Array = stage.float_items()
	if floats.is_empty():
		return
	var plates: Array = []
	for it in stage.plate_items():
		var f: Rect2 = it.frame
		if not plates.has(f):
			plates.append(f)
	for i in floats.size():
		var r: Rect2 = floats[i].rect
		for p in plates:
			if (p as Rect2).grow(FLOAT_CLEARANCE).intersects(r):
				out.append("%s: rect %s is within %.0f px of a plate %s" % [floats[i].path, r, FLOAT_CLEARANCE, p])
				break
		for j in range(i + 1, floats.size()):
			if r.intersects(floats[j].rect):
				out.append("%s: rect %s overlaps another floating number %s" % [floats[i].path, r, floats[j].path])


static func _side(side: int) -> String:
	return ["left", "top", "right", "bottom"][side]


static func _what(n: Node) -> String:
	return "label '%s'" % (n as Label).text if n is Label else "icon"
