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
var _dot: PulseDot
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
	_banner_panel = _wrap(_banner, "Banner")
	_dot = PulseDot.new()
	(_banner.get_parent() as Control).add_child(_dot)
	(_banner.get_parent() as Control).move_child(_dot, 0)
	_notice_panel = _wrap(_notice, "BannerAlert")
	_notice.visible = false                              # nothing to say until a notice arrives
	_notice_panel.visible = false
	Feed.status_changed.connect(_on_status)
	Feed.notice_raised.connect(_on_notice)
	_on_status(Feed.status())


## A label inside a banner panel (in a row, so a marker can sit before it); all of it ignores the mouse.
func _wrap(label: Label, variation: String) -> PanelContainer:
	var panel := Ui.card(variation)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var row := Ui.hbox(10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(label)
	panel.add_child(row)
	add_child(panel)
	return panel


## Which look the connection banner has: calm while the app is still trying (connecting, reconnecting: nothing is wrong
## yet), alert once it has given up or been stopped. Only the variation's NAME is chosen here; the theme owns the colours.
static func variation_for(st: Dictionary) -> String:
	if st.terminal != "" or st.net in ["unreachable", "offline", "stopped"]:
		return "BannerAlert"
	return "Banner"


## What the connection banner says and how it looks, from the connection state, the reason the connection ended (if any) and
## the screen. Rules: a reason that ended the connection is worded as that reason, never as the connection's own state (a
## red box saying "Connected" was a lie); the title screen already says the reason in its page, so the banner hides there
## instead of repeating it; with no reason, only trouble (not "online", not a plain "offline") is shown.
## Returns {"show": bool, "key": translation key, "variation": "Banner" | "BannerAlert"}.
static func banner_for(st: Dictionary) -> Dictionary:
	var terminal: String = st.terminal
	if terminal != "":
		var key := "notice." + terminal if terminal in UiKeys.NOTICE_CODES else "ui.net.stopped"
		return {"show": st.get("screen", "") != "title", "key": key, "variation": "BannerAlert"}
	var quiet: bool = st.net in ["online", "offline"]
	return {"show": not quiet, "key": st.net_key, "variation": variation_for(st)}


## For tests: the variation the connection banner currently wears.
func banner_variation() -> String:
	return _banner_panel.theme_type_variation


func _on_status(st: Dictionary) -> void:
	var b := banner_for(st)
	var quiet: bool = not b.show
	var was_quiet := not _banner.visible
	_banner.visible = not quiet
	_banner_panel.visible = not quiet
	_banner.text = Words.render(b.key, {"text": ""})
	var variation: String = b.variation
	if _banner_panel.theme_type_variation != variation:
		_banner_panel.theme_type_variation = variation
	_dot.visible = variation == "Banner"                     # the breathing dot says "still trying"; an alert has no dot
	if was_quiet and not quiet:
		_drop_in(_banner_panel)


func _on_notice(n: Dictionary) -> void:
	# The title screen writes its own notices into the page (and re-reads a terminal reason from state), so a toast saying the
	# same sentence in the corner is a duplicate (stranger pass #11).
	if Feed.status().screen == "title":
		return
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
