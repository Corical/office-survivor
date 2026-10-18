extends Control
## What does a frame of the title cost, and which ingredient is it? Windowed, run with vsync off so the frame time is the
## real cost, not the monitor's refresh:
##   godot --path godot --disable-vsync res://tests/perf/perf.tscn
## For each variant it switches one ingredient off, lets 60 frames settle, then averages 240 frames (ms per frame) and
## reads the renderer's draw-call count. Prints "PERF <variant> <ms> ms  <draw calls> draws  <objects> objects".

const FRAMES := 240
const SETTLE := 60

var router: Control


func _ready() -> void:
	await get_tree().process_frame
	Session.reset(MemorySessionStore.new())
	Feed.reset()
	Themes.use("flash")
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	router = (load("res://main.tscn") as PackedScene).instantiate()
	add_child(router)
	get_window().size = Vector2i(540, 960)
	await _frames(SETTLE)
	await _measure("full title")
	var bd: Backdrop = router.backdrop
	bd.visible = false
	await _measure("backdrop hidden")
	bd.visible = true
	var embers: CPUParticles2D = bd._embers
	embers.emitting = false
	embers.visible = false
	await _measure("embers off")
	embers.visible = true
	embers.emitting = true
	bd.set_process(false)
	await _measure("backdrop not redrawn per frame")
	bd.set_process(true)
	for t in router.get_children():
		if t is TextureRect:
			t.visible = false
	await _measure("vignette off")
	var logo := Ui.find(router.current, "logo")
	if logo != null:
		logo.visible = false
	await _measure("logo hidden (glow and bob gone)")
	print("PERF DONE")
	get_tree().quit(0)


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func _measure(label: String) -> void:
	await _frames(SETTLE)
	var t0 := Time.get_ticks_usec()
	for i in FRAMES:
		await get_tree().process_frame
	var ms := float(Time.get_ticks_usec() - t0) / 1000.0 / float(FRAMES)
	var draws := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	var objs := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)
	print("PERF %s: %.2f ms  %d draws  %d objects" % [label, ms, draws, objs])
