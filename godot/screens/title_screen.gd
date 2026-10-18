class_name TitleScreen
extends Control
## Create a room, join one by code, resume a stored seat, and set the server address. Builds only from Feed.status()
## and talks only through Intents.

var _notice := ""
var _code_text := ""
var _show_settings := false


func _ready() -> void:
	Feed.status_changed.connect(func(_s): _build())
	Feed.notice_raised.connect(_on_notice)
	_build()


func _on_notice(n: Dictionary) -> void:
	_notice = Words.render(n.key, {"text": n.text})
	_build()


func _build() -> void:
	for c in get_children():
		remove_child(c)
		c.queue_free()
	var st := Feed.status()
	var col := Ui.page(self)
	col.add_child(Ui.label(Words.render("ui.app_name"), "app_name", "BigLabel"))
	if _notice != "":
		col.add_child(Ui.label(_notice, "notice"))
	if st.has_seat:
		var resume := Ui.button(Words.render("ui.resume"), "resume", func(): _show(Intents.resume()), false, "PrimaryButton")
		col.add_child(resume)
	col.add_child(Ui.button(Words.render("ui.create_room"), "create", func(): _reason(Intents.create_room()), false,
		"PrimaryButton"))
	var row := Ui.flow()
	var code := LineEdit.new()
	code.set_meta("id", "code")
	code.placeholder_text = Words.render("ui.enter_code")
	code.text = _code_text
	code.max_length = 8
	code.custom_minimum_size = Vector2(160, 48)
	code.text_changed.connect(func(t): _code_text = t)
	row.add_child(code)
	row.add_child(Ui.button(Words.render("ui.join_room"), "join", func(): _reason(Intents.join_room(_code_text))))
	col.add_child(row)
	col.add_child(Ui.button(Words.render("ui.hide_settings") if _show_settings else Words.render("ui.settings"),
		"settings_toggle", func():
			_show_settings = not _show_settings
			_build()))
	if _show_settings:
		col.add_child(Ui.label(Words.render("ui.server_address"), "", "MutedLabel"))
		var url := LineEdit.new()
		url.set_meta("id", "server_url")
		url.text = st.server_url
		url.text_changed.connect(func(t): Intents.set_server_url(t))
		col.add_child(url)
		var ids: Array = Themes.ids()
		var label := "%s: %s" % [Words.render("ui.theme"), Themes.current.title]
		col.add_child(Ui.button(label, "theme_toggle", func():
			Themes.use(ids[(ids.find(Themes.current.id) + 1) % ids.size()])))


func _show(started: bool) -> void:
	if not started:
		_notice = Words.render("notice.no_server_url")
		_build()


## An intent came back refused: show the reason in the theme's words.
func _reason(why: String) -> void:
	if why == "":
		return
	_notice = Words.render(UiKeys.notice_key("", why), {"text": why})
	_build()
