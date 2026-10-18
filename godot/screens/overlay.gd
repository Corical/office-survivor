class_name Overlay
extends VBoxContainer
## Always on top of the current screen: the connection banner (only when something is wrong) and the latest notice.

var _banner: Label
var _notice: Label


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE            # never blocks a tap on the screen below
	set_anchors_preset(Control.PRESET_TOP_WIDE)
	_banner = Ui.label("", "net_banner", "MutedLabel")
	_notice = Ui.label("", "notice_toast")
	_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_notice.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_banner)
	add_child(_notice)
	Feed.status_changed.connect(_on_status)
	Feed.notice_raised.connect(_on_notice)
	_on_status(Feed.status())


func _on_status(st: Dictionary) -> void:
	var quiet: bool = st.net in ["online", "offline"] and st.terminal == ""
	_banner.visible = not quiet
	_banner.text = Words.render(st.net_key)


func _on_notice(n: Dictionary) -> void:
	_notice.text = Words.render(n.key, {"text": n.text})
	_notice.visible = true
