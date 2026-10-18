class_name Ui
extends RefCounted
## Small builders shared by the screens. Everything a screen shows is a Words key plus slots; looks come from the
## Theme through type variations, never from here.


static func clear(n: Node) -> void:
	for c in n.get_children():
		n.remove_child(c)
		c.queue_free()


static func label(text: String, id := "", variation := "") -> Label:
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if id != "":
		l.set_meta("id", id)
	if variation != "":
		l.theme_type_variation = variation
	return l


static func button(text: String, id: String, cb: Callable, disabled := false, variation := "") -> Button:
	var b := Button.new()
	b.text = text
	b.disabled = disabled
	b.set_meta("id", id)
	b.custom_minimum_size = Vector2(0, 48)               # a thumb-sized target
	if variation != "":
		b.theme_type_variation = variation
	b.pressed.connect(cb)
	return b


static func vbox(gap := 8) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", gap)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return v


static func flow() -> HFlowContainer:
	var f := HFlowContainer.new()
	f.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return f


## The page every screen builds into: a scrolling column with a side margin.
static func page(owner_control: Control) -> VBoxContainer:
	owner_control.set_anchors_preset(Control.PRESET_FULL_RECT)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 16)
	owner_control.add_child(margin)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroll)
	var col := vbox(12)
	scroll.add_child(col)
	return col


## The first node anywhere below `n` carrying meta id `id` (screens and tests find controls by id, not by text).
static func find(n: Node, id: String) -> Node:
	if n.has_meta("id") and n.get_meta("id") == id:
		return n
	for c in n.get_children():
		var hit := find(c, id)
		if hit != null:
			return hit
	return null


static func find_all(n: Node, prefix: String) -> Array:
	var out: Array = []
	if n.has_meta("id") and str(n.get_meta("id")).begins_with(prefix):
		out.append(n)
	for c in n.get_children():
		out.append_array(find_all(c, prefix))
	return out


## Every visible piece of text below `n` (for tests and for the leak check).
static func texts(n: Node) -> Array:
	var out: Array = []
	if n is Label or n is Button:
		out.append(n.text)
	for c in n.get_children():
		out.append_array(texts(c))
	return out
