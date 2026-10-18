class_name Overlay
extends VBoxContainer
## Always on top of the current screen: the connection banner (only when something is wrong) and the latest notice,
## each in a banner panel inset from the window edge. Nothing here ever takes a tap.

const SIDE := 16                      # chosen: the same gutter as a page
const TOP := 14
const NOTICE_SHOWN_S := 7.0           # chosen: a toast stays long enough to read, then goes (only with motion allowed)

var _banner: Label
var _banner_panel: PanelContainer
var _notice: Label
var _notice_panel: PanelContainer
var _hide: Tween


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE            # never blocks a tap on the screen below
	set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	offset_left = SIDE
	offset_right = -SIDE
	offset_top = TOP
	add_theme_constant_override("separation", 8)
	_banner = Ui.label("", "net_banner", "MutedLabel")
	_notice = Ui.label("", "notice_toast")
	_banner_panel = _wrap(_banner)
	_notice_panel = _wrap(_notice)
	_notice.visible = false                              # nothing to say until a notice arrives
	_notice_panel.visible = false
	Feed.status_changed.connect(_on_status)
	Feed.notice_raised.connect(_on_notice)
	_on_status(Feed.status())


## A label inside a banner panel; both ignore the mouse.
func _wrap(label: Label) -> PanelContainer:
	var panel := Ui.card("Banner")
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(label)
	add_child(panel)
	return panel


func _on_status(st: Dictionary) -> void:
	var quiet: bool = st.net in ["online", "offline"] and st.terminal == ""
	var was_quiet := not _banner.visible
	_banner.visible = not quiet
	_banner_panel.visible = not quiet
	_banner.text = Words.render(st.net_key)
	if was_quiet and not quiet:
		_drop_in(_banner_panel)


func _on_notice(n: Dictionary) -> void:
	_notice.text = Words.render(n.key, {"text": n.text})
	_notice.visible = true
	_notice_panel.visible = true
	_drop_in(_notice_panel)
	if Themes.fx("transition").is_empty():
		return
	if _hide != null and _hide.is_valid():
		_hide.kill()
	_hide = create_tween()
	_hide.tween_interval(NOTICE_SHOWN_S)
	_hide.tween_property(_notice_panel, "modulate:a", 0.0, 0.4)
	_hide.tween_callback(func():
		_notice_panel.visible = false
		_notice.visible = false)


## A panel that appears fades in and settles from a little small (the theme's "intro" settings; none = it just shows).
func _drop_in(panel: Control) -> void:
	panel.modulate.a = 1.0
	if Themes.fx("intro").is_empty() or not panel.is_inside_tree():
		return
	panel.modulate.a = 0.0
	var tw := panel.create_tween()
	tw.tween_property(panel, "modulate:a", 1.0, 0.22)
