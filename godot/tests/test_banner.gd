extends BaseTest
## The connection banner's words and look for EVERY combination of connection state, reason the connection ended, and screen
## (stranger pass 2, N9: a red alert box that said "Connected").

const NETS := ["connecting", "online", "reconnecting", "unreachable", "offline", "stopped"]
const REASONS := ["", "seat_gone", "taken_over", "too_big", "flapping", "upgrade_required", "invalid", "something_new_and_unknown"]
const SCREENS := ["title", "lobby", "round", "reveal", "end"]


func _st(net: String, terminal: String, screen: String) -> Dictionary:
	return {"net": net, "net_key": UiKeys.net_key(net), "terminal": terminal, "screen": screen}


func test_a_red_banner_never_says_connected_or_any_other_state_word_that_contradicts_it() -> void:
	var connected := Words.render("ui.net.online")
	var n := 0
	for net in NETS:
		for reason in REASONS:
			for screen in SCREENS:
				var tag := "%s / '%s' / %s" % [net, reason, screen]
				var b := Overlay.banner_for(_st(net, reason, screen))
				n += 1
				if not b.show:
					continue
				var words := Words.render(b.key, {"text": ""})
				check(words != "", "%s: the banner has words" % tag)
				check(words.find("{") < 0, "%s: no raw slot in '%s'" % [tag, words])
				if b.variation == "BannerAlert":
					check(words != connected, "%s: an alert must not say '%s'" % [tag, connected])
				if reason != "":
					check(words != connected, "%s: a reason ended the connection, so the banner cannot say it is connected" % tag)
					eq(b.variation, "BannerAlert", "%s: a reason is an alert" % tag)
	eq(n, NETS.size() * REASONS.size() * SCREENS.size(), "every combination was looked at")


func test_the_title_says_the_reason_itself_so_the_banner_hides_there() -> void:
	for net in NETS:
		for reason in REASONS:
			if reason == "":
				continue
			check(not Overlay.banner_for(_st(net, reason, "title")).show, "%s / %s: hidden on the title" % [net, reason])
			check(Overlay.banner_for(_st(net, reason, "lobby")).show, "%s / %s: shown elsewhere" % [net, reason])


func test_without_a_reason_only_trouble_is_shown_and_online_is_quiet() -> void:
	for screen in SCREENS:
		check(not Overlay.banner_for(_st("online", "", screen)).show, "online is quiet on %s" % screen)
		check(not Overlay.banner_for(_st("offline", "", screen)).show, "plain offline is quiet on %s" % screen)
		for net in ["connecting", "reconnecting"]:
			var b := Overlay.banner_for(_st(net, "", screen))
			check(b.show, "%s is shown on %s" % [net, screen])
			eq(b.variation, "Banner", "%s is calm" % net)
		for net in ["unreachable", "stopped"]:
			var b := Overlay.banner_for(_st(net, "", screen))
			check(b.show, "%s is shown on %s" % [net, screen])
			eq(b.variation, "BannerAlert", "%s is an alert" % net)


func test_the_overlay_applies_what_the_function_says() -> void:
	var o := Overlay.new()
	add_child(o)
	for reason in REASONS:
		for screen in ["title", "lobby"]:
			var st := _st("online", reason, screen)
			o._on_status(st)
			var b := Overlay.banner_for(st)
			eq(o.banner_variation(), b.variation, "%s/%s: the look" % [reason, screen])
			eq((o.get_node_or_null("../") == null), false, "attached")
	o.free()
