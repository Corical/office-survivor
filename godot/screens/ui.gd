class_name Ui
extends RefCounted
## Small builders shared by the screens. Everything a screen shows is a Words key plus slots; looks come from the
## Theme through type variations, art ids (Themes.texture) and effect settings (Themes.fx), never from here.

const AVATARS := 8                    # chosen: the art set has avatar_0 .. avatar_7


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


## A name: it shrinks to fit the room it has (a 12-letter name must read in full on a phone), then wraps to two lines, and
## only a name longer than that ends in an ellipsis. See FitLabel.
static func name_label(text: String, id := "", variation := "NameLabel") -> Label:
	var l := FitLabel.new()
	l.text = text
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if id != "":
		l.set_meta("id", id)
	if variation != "":
		l.theme_type_variation = variation
	return l


static func button(text: String, id: String, cb: Callable, disabled := false, variation := "", icon_id := "") -> Button:
	var b := Button.new()
	b.text = text
	b.disabled = disabled
	b.set_meta("id", id)
	b.custom_minimum_size = Vector2(0, 72 if variation == "PrimaryButton" else 56)       # a thumb-sized target
	if variation != "":
		b.theme_type_variation = variation
	if icon_id != "":
		var tex := Themes.icon(icon_id)
		if tex != null:
			b.icon = tex
			b.expand_icon = true
			b.add_theme_constant_override("icon_max_width", 30)
	b.pressed.connect(cb)
	juice(b)
	return b


static func vbox(gap := 8) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", gap)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return v


static func hbox(gap := 8) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", gap)
	h.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return h


static func flow() -> HFlowContainer:
	var f := HFlowContainer.new()
	f.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return f


## Fill a card-shaped Button with a face, a fitted name and a quieter line under it. The content sits inside the style's own
## content margins (read from the style, not written here) and ignores the mouse, so the whole card is the tap target.
static func fill_person_card(b: Button, face: Texture2D, who: String, sub: String, face_px := 52.0) -> void:
	var build := func():
		var sb := b.get_theme_stylebox("normal")
		var pad := MarginContainer.new()
		pad.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		pad.mouse_filter = Control.MOUSE_FILTER_IGNORE
		pad.add_theme_constant_override("margin_left", int(sb.get_margin(SIDE_LEFT)))
		pad.add_theme_constant_override("margin_right", int(sb.get_margin(SIDE_RIGHT)))
		pad.add_theme_constant_override("margin_top", int(sb.get_margin(SIDE_TOP)))
		pad.add_theme_constant_override("margin_bottom", int(sb.get_margin(SIDE_BOTTOM)))
		b.add_child(pad)
		var row := hbox(10)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		pad.add_child(row)
		if face != null:
			row.add_child(picture(face, Vector2(face_px, face_px)))
		var words := vbox(0)
		words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		words.mouse_filter = Control.MOUSE_FILTER_IGNORE
		words.add_child(name_label(who, "", "NameLabel"))
		if sub != "":
			words.add_child(name_label(sub, "", "MutedLabel"))
		row.add_child(words)
	if b.is_inside_tree():
		build.call()
	else:
		b.ready.connect(build, CONNECT_ONE_SHOT)


## A panel in the theme's card style (`variation` names another: "CardHot", "Plate"...). It lets drags through, so a card
## never stops a finger scrolling the page.
static func card(variation := "Card") -> PanelContainer:
	var p := PanelContainer.new()
	p.theme_type_variation = variation
	p.mouse_filter = Control.MOUSE_FILTER_PASS
	p.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return p


## A picture that scales to its box without distortion.
static func picture(tex: Texture2D, min_size: Vector2, id := "") -> TextureRect:
	var r := TextureRect.new()
	r.texture = tex
	r.custom_minimum_size = min_size
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if id != "":
		r.set_meta("id", id)
	return r


## The page every screen builds into: a scrolling column with a side margin.
static func page(owner_control: Control) -> VBoxContainer:
	owner_control.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var margin := _margin(owner_control)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroll)
	var col := vbox(12)
	scroll.add_child(col)
	return col


## A page with a dock: the scrolling column above and a bar fixed at the foot of the screen (the main action lives in
## it, so it is always in reach of a thumb). Returns {"col": the scrolling column, "dock": the bar's inner column}.
static func page_docked(owner_control: Control) -> Dictionary:
	owner_control.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var root := VBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_theme_constant_override("separation", 0)
	owner_control.add_child(root)
	var margin := MarginContainer.new()
	margin.size_flags_vertical = Control.SIZE_EXPAND_FILL
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 16 if side != "bottom" else 4)
	root.add_child(margin)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroll)
	var col := vbox(12)
	scroll.add_child(col)
	var dock := card("Dock")
	dock.mouse_filter = Control.MOUSE_FILTER_STOP
	root.add_child(dock)
	var dock_col := vbox(8)
	dock.add_child(dock_col)
	return {"col": col, "dock": dock_col}


static func _margin(owner_control: Control) -> MarginContainer:
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 16)
	owner_control.add_child(margin)
	return margin


## A column for a menu: centred on the page and no wider than a phone, so it reads on a desktop window too.
static func menu_column(col: VBoxContainer, width := 500.0) -> VBoxContainer:
	col.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.alignment = BoxContainer.ALIGNMENT_CENTER
	var inner := vbox(14)
	inner.custom_minimum_size = Vector2(width, 0)
	inner.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	col.add_child(inner)
	return inner


# ---------------- motion ----------------

## Press feedback: squash on touch-down, bounce back on release. A theme with no "press" settings gets none.
static func juice(b: Control) -> void:
	var p := Themes.fx("press")
	if p.is_empty():
		return
	b.pivot_offset = b.size * 0.5
	b.resized.connect(func(): b.pivot_offset = b.size * 0.5)
	var bb := b as BaseButton
	if bb != null:
		bb.button_down.connect(func(): _scale_to(b, float(p.down), 0.06, Tween.TRANS_SINE))
		bb.button_up.connect(func(): _scale_to(b, 1.0, float(p.time), Tween.TRANS_BACK))


static func _scale_to(n: Control, s: float, time: float, trans: Tween.TransitionType) -> void:
	if not n.is_inside_tree():
		return
	if n.has_meta("_scale_tween"):
		var old: Tween = n.get_meta("_scale_tween")
		if old != null and old.is_valid():
			old.kill()
	var tw := n.create_tween()
	tw.tween_property(n, "scale", Vector2(s, s), time).set_trans(trans).set_ease(Tween.EASE_OUT)
	n.set_meta("_scale_tween", tw)


## Pop a freshly built control in: it fades up and settles from slightly small. Call after it is in the tree.
static func intro(n: Control, delay := 0.0) -> void:
	var p := Themes.fx("intro")
	if p.is_empty() or not n.is_inside_tree():
		return
	n.modulate.a = 0.0
	n.scale = Vector2(0.9, 0.9)
	n.pivot_offset = n.size * 0.5
	n.resized.connect(func(): n.pivot_offset = n.size * 0.5)
	var tw := n.create_tween().set_parallel(true)
	tw.tween_property(n, "modulate:a", 1.0, float(p.time)).set_delay(delay)
	tw.tween_property(n, "scale", Vector2.ONE, float(p.time) * 1.4).set_delay(delay).set_trans(Tween.TRANS_BACK) \
		.set_ease(Tween.EASE_OUT)


## `intro` for each child in turn, `stagger` seconds apart.
static func intro_all(nodes: Array, first_delay := 0.0) -> void:
	var p := Themes.fx("intro")
	var step: float = float(p.get("stagger", 0.0))
	for i in nodes.size():
		intro(nodes[i], first_delay + step * i)


# ---------------- people ----------------

## alias -> avatar number, from the alias alone: each person starts from a stable hash of their name, and when two
## names land on the same face the one that sorts later moves to the next free one. Join order never matters.
static func avatar_ids(aliases: Array) -> Dictionary:
	var names: Array = []
	for a in aliases:
		if str(a) != "" and not names.has(str(a)):
			names.append(str(a))
	names.sort()
	var taken := {}
	var out := {}
	for a in names:
		var i: int = a.hash() % AVATARS
		var tries := 0
		while taken.has(i) and tries < AVATARS:
			i = (i + 1) % AVATARS
			tries += 1
		taken[i] = true
		out[a] = i
	return out


static func avatar(alias: String, ids: Dictionary) -> Texture2D:
	return Themes.texture("avatar_%d" % int(ids.get(alias, alias.hash() % AVATARS)))


## A row of little lanterns, `lit` of `total` burning. Null when the theme has no lantern art.
static func lanterns(total: int, lit: int, id := "") -> HBoxContainer:
	if Themes.texture("lantern_on") == null or Themes.texture("lantern_off") == null:
		return null
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 4)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if id != "":
		row.set_meta("id", id)
	for i in total:
		row.add_child(picture(null, Vector2(30, 38)))
	set_lit(row, lit)
	return row


static func set_lit(row: HBoxContainer, lit: int) -> void:
	var on := Themes.texture("lantern_on")
	var off := Themes.texture("lantern_off")
	var i := 0
	for c in row.get_children():
		(c as TextureRect).texture = on if i < lit else off
		i += 1


# ---------------- finding things ----------------

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
