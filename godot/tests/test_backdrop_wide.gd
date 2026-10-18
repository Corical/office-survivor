extends BaseTest
## The backdrop never stretches its art past 1.25x: a wide window switches to the sharp, mirrored layout (and the haze-cutting
## shader that leaves no edge); a phone-shaped window keeps the original cover layout with no shader.

var _made: Array = []


func teardown() -> void:
	super.teardown()
	for b in _made:
		if is_instance_valid(b):
			b.free()
	_made.clear()


func _backdrop(sz: Vector2) -> Backdrop:
	var holder := Control.new()                      # the backdrop fills its parent, so the parent has the size under test
	holder.size = sz
	add_child(holder)
	_made.append(holder)
	var b := Backdrop.new()
	b.screen_scale_override = 1.0                    # one logical unit is one pixel
	holder.add_child(b)
	_resize(b, sz)
	return b


func _resize(b: Backdrop, sz: Vector2) -> void:
	(b.get_parent() as Control).size = sz
	b.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	b._update_near_mode()


func test_a_phone_shaped_window_keeps_the_plain_cover_layout() -> void:
	var b := _backdrop(Vector2(540, 960))
	check(b.has_art(), "the flash theme has backdrop art")
	check(b._front.material == null, "no shader on a phone")
	check(b._cover_scale(b._tex_far, 8.0) <= b._max_scale(), "the art covers it without stretching past the limit")


func test_wide_windows_switch_to_the_sharp_layout_at_every_size() -> void:
	for sz in [Vector2(1400, 720), Vector2(1707, 960), Vector2(2293, 960), Vector2(3000, 600)]:
		var b := _backdrop(sz)
		check(b._cover_scale(b._tex_far, 8.0) > b._max_scale(), "%s needs more than the limit if it were stretched" % sz)
		check(b._front.material != null, "%s: the near layer wears the haze-cutting shader" % sz)


func test_going_back_to_a_narrow_window_removes_the_shader() -> void:
	var b := _backdrop(Vector2(2000, 960))
	check(b._front.material != null, "wide")
	_resize(b, Vector2(540, 960))
	check(b._front.material == null, "narrow again")


func test_the_haze_shader_compiles_and_keeps_solid_pixels() -> void:
	var sh := Shader.new()
	sh.code = Backdrop.HAZE_CUT
	check(sh.get_mode() == Shader.MODE_CANVAS_ITEM, "a canvas item shader")
	check(Backdrop.HAZE_CUT.contains("smoothstep(0.08, 0.3"), "it removes the faint haze")
