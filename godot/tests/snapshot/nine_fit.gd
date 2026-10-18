class_name NineFit
extends RefCounted
## A nine-patch drawn smaller than its own fixed edges overlaps itself and squashes the art (the Settings and Join buttons were
## 56 px high wearing 30 + 30 px edges: left cap, lip and label all drawn wrong). This walks a live scene tree and reports, with
## the node path, every visible Control that wears a StyleBoxTexture in ANY of its states (normal, hover, pressed,
## hover_pressed, disabled, panel) and is smaller than that style's texture margins: height < top + bottom, or
## width < left + right. Returns an Array of strings; empty means clean.

const STATES := ["normal", "hover", "pressed", "hover_pressed", "disabled"]


static func check(root: Node) -> Array[String]:
	var out: Array[String] = []
	_walk(root, out)
	return out


static func _walk(n: Node, out: Array[String]) -> void:
	if n is Control and not (n as Control).visible:
		return
	if n is Button:
		for s in STATES:
			_test(n as Control, s, (n as Control).get_theme_stylebox(s), out)
	elif n is PanelContainer:
		_test(n as Control, "panel", (n as Control).get_theme_stylebox("panel"), out)
	for c in n.get_children():
		_walk(c, out)


static func _test(c: Control, state: String, sb: StyleBox, out: Array[String]) -> void:
	if not (sb is StyleBoxTexture):
		return
	var t := sb as StyleBoxTexture
	var need_h := t.texture_margin_top + t.texture_margin_bottom
	var need_w := t.texture_margin_left + t.texture_margin_right
	if c.size.y + 0.01 < need_h or c.size.x + 0.01 < need_w:
		out.append("%s [%s]: %.0fx%.0f is smaller than its edges %.0fx%.0f" % [c.get_path(), state, c.size.x, c.size.y, need_w, need_h])
