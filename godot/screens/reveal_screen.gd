class_name RevealScreen
extends Control
## What happened in the night: the animated Stage (huts, fire, the beats as they happen) with a small Skip pill, the
## written log as game panels (the line being played is lit, the ones still to come are dimmed), the radio, and
## Continue at the foot. The log is always complete: it shows every line, including the ones the animation skips.
## Phone: Stage on top, log below. Wide window: Stage on the left, log and Continue on the right.

const WIDE_PX := 900
const LOG_MIN_H := 150.0              # chosen: room for about two log lines on a phone; the Stage gets the rest
const STAGE_MIN_H := 360.0
const FADE_PX := 30.0                 # chosen: the soft edge of the log

var _timer_label: Label
var _skip_pill: Button
var _log: ScrollContainer
var _fade_top: TextureRect
var _fade_foot: TextureRect
var _cards: Array = []                # one panel per log line, in order
var _hot := -2                        # the log line lit right now
var _sig := ""
var _wide := false
var _building := false


func _ready() -> void:
	Feed.model_changed.connect(_on_model)
	resized.connect(_on_resized)
	_build()


## Skip the animation: the log below is always complete, so nothing is lost.
func _skip() -> void:
	if Feed.player.timeline != null:
		Feed.player.timeline.snap_to_end()


func _on_resized() -> void:
	if not _building and (size.x >= WIDE_PX) != _wide:
		_build()


func _process(_delta: float) -> void:
	if _timer_label != null:
		_timer_label.text = Words.render("ui.seconds", {"n": Feed.seconds_left()})
	var tl := Feed.player.timeline
	if _skip_pill != null and tl != null:
		_skip_pill.visible = not tl.finished
	_light_log()
	_update_fades()


## An identical push (the server re-sends the same view on every action) must not rebuild the screen under a finger.
func _on_model(kind: String, m: Dictionary) -> void:
	if kind != "reveal":
		return
	if _sig_of(m) != _sig:
		_build()


func _sig_of(m: Dictionary) -> String:
	return JSON.stringify(m.get("lines", m)) + JSON.stringify(m.get("radio", [])) + str(m.get("is_host", "")) + str(m.get("seats_taken", ""))


func _build() -> void:
	if _building:
		return
	_building = true
	_wide = size.x >= WIDE_PX
	_sig = _sig_of(Feed.models.get("reveal", {}))
	for c in get_children():
		remove_child(c)
		c.queue_free()
	_timer_label = null
	_skip_pill = null
	_log = null
	_fade_top = null
	_fade_foot = null
	_cards = []
	_hot = -2
	var m: Dictionary = Feed.models.get("reveal", {})
	if m.is_empty():
		var empty := Ui.page(self)
		empty.add_child(Ui.label(Words.render("ui.nothing_to_show"), "empty"))
		_building = false
		return
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 12)
	add_child(margin)
	var stage_box := _stage_box()
	var head := _head()
	_log = _log_panel(m)
	var log_box := _log_box(_log)
	var dock := _dock()
	if _wide:
		var cols := HBoxContainer.new()
		cols.add_theme_constant_override("separation", 24)
		stage_box.size_flags_stretch_ratio = 3.0
		cols.add_child(stage_box)
		var right := VBoxContainer.new()
		right.add_theme_constant_override("separation", 10)
		right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		right.size_flags_stretch_ratio = 2.0
		right.add_child(head)
		log_box.size_flags_vertical = Control.SIZE_EXPAND_FILL
		right.add_child(log_box)
		right.add_child(dock)
		cols.add_child(right)
		margin.add_child(cols)
	else:
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 8)
		col.add_child(head)
		stage_box.size_flags_stretch_ratio = 4.0
		col.add_child(stage_box)
		log_box.custom_minimum_size = Vector2(0, LOG_MIN_H)
		log_box.size_flags_vertical = Control.SIZE_EXPAND_FILL
		log_box.size_flags_stretch_ratio = 2.0
		col.add_child(log_box)
		col.add_child(dock)
		margin.add_child(col)
	_building = false
	_light_log()


func _head() -> Control:
	var plate := Ui.card("Scrim")
	var row := Ui.hbox(10)
	plate.add_child(row)
	var title := Ui.label(Words.render("ui.reveal_title"), "reveal_title", "HeaderLabel")
	title.autowrap_mode = TextServer.AUTOWRAP_OFF
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(title)
	_timer_label = Ui.label("", "timer_label", "HeaderLabel")
	_timer_label.size_flags_horizontal = Control.SIZE_SHRINK_END
	_timer_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	_timer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(_timer_label)
	return plate


## The Stage, with the Skip pill laid over its top right corner.
func _stage_box() -> Control:
	var holder := Control.new()
	holder.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	holder.size_flags_vertical = Control.SIZE_EXPAND_FILL
	holder.custom_minimum_size = Vector2(0, STAGE_MIN_H)
	holder.mouse_filter = Control.MOUSE_FILTER_PASS
	var stage := Stage.new()
	stage.set_meta("id", "stage")
	stage.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	holder.add_child(stage)
	_skip_pill = Ui.button(Words.render("ui.skip"), "skip", func(): _skip(), false, "SkipPill")
	_skip_pill.custom_minimum_size = Vector2(96, 44)
	holder.add_child(_skip_pill)
	# pinned to the top right corner and growing leftwards, so the pill's own text width can never push it off the edge
	_skip_pill.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_skip_pill.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_skip_pill.offset_right = -10.0
	_skip_pill.offset_top = 10.0
	return holder


## The log with a soft edge at the top and at the foot that shows while there is more to scroll to, so a line cut by the edge
## fades out instead of being sliced.
func _log_box(scroll: ScrollContainer) -> Control:
	var box := Control.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.clip_contents = true
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(scroll)
	_fade_top = _edge_fade(true)
	_fade_foot = _edge_fade(false)
	box.add_child(_fade_top)
	box.add_child(_fade_foot)
	return box


func _edge_fade(top: bool) -> TextureRect:
	var g := Gradient.new()
	var solid := Themes.color_a("ink", 0.95)
	var clear := Themes.color_a("ink", 0.0)
	g.colors = PackedColorArray([solid, clear] if top else [clear, solid])
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill_from = Vector2(0, 0)
	tex.fill_to = Vector2(0, 1)
	tex.width = 4
	tex.height = 64
	var r := TextureRect.new()
	r.texture = tex
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_SCALE
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	r.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE if top else Control.PRESET_BOTTOM_WIDE)
	if top:
		r.offset_bottom = FADE_PX
	else:
		r.offset_top = -FADE_PX
	r.visible = false
	return r


func _update_fades() -> void:
	if _log == null or _fade_top == null:
		return
	var bar := _log.get_v_scroll_bar()
	_fade_top.visible = bar.value > 4.0
	_fade_foot.visible = bar.value + bar.page < bar.max_value - 4.0


## The written night: one panel per line, then the radio.
func _log_panel(m: Dictionary) -> ScrollContainer:
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var col := Ui.vbox(8)
	scroll.add_child(col)
	for i in m.lines.size():
		var ln: Dictionary = m.lines[i]
		var card := Ui.card("LogLine")
		card.add_child(Ui.label(Words.render(ln.key, ln.slots), "line_%d" % i))
		col.add_child(card)
		_cards.append(card)
	if not m.radio.is_empty():
		col.add_child(Ui.label(Words.render("ui.radio_heard"), "", "MutedLabel"))
		for i in m.radio.size():
			var card := Ui.card("LogLine")
			card.add_child(Ui.label(Words.render(m.radio[i].key, m.radio[i].slots), "radio_%d" % i))
			col.add_child(card)
	return scroll


func _dock() -> Control:
	var dock := Ui.card("Dock")
	dock.mouse_filter = Control.MOUSE_FILTER_STOP
	dock.add_child(Ui.button(Words.render("ui.continue"), "continue", func(): Intents.proceed(), false, "PrimaryButton"))
	return dock


## The line being played right now.
func _current_line() -> int:
	var tl := Feed.player.timeline
	if tl == null or tl.finished:
		return _cards.size() - 1                         # all played: the newest is the last
	var li: int = int(tl.current().get("line_index", -1))
	return li if li >= 0 else maxi(_hot, 0)


## Light the line being played, dim the lines still to come, and keep the lit one in view.
func _light_log() -> void:
	if _cards.is_empty():
		return
	var hot := clampi(_current_line(), 0, _cards.size() - 1)
	if hot == _hot:
		return
	_hot = hot
	for i in _cards.size():
		var card: PanelContainer = _cards[i]
		var variation := "LogLineHot" if i == hot else "LogLine"
		if card.theme_type_variation != variation:
			card.theme_type_variation = variation
		card.modulate.a = 1.0 if i <= hot else 0.5
	if _log != null and _log.is_inside_tree():
		_log.ensure_control_visible.call_deferred(_cards[hot])
