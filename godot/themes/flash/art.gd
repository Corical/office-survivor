class_name FlashArt
extends RefCounted
## Where the flash theme's pictures come from. One id, two places, in this order:
##   1. res://themes/flash/art/<id>.png          the real art (delivered by the art designer)
##   2. res://themes/flash/art_standin/<id>.png  the stand-in made by tools/gen_flash_standins.py
## so dropping a real file into art/ replaces its stand-in with no code change. A theme asks by id only.

const REAL := "res://themes/flash/art/%s.png"
const STANDIN := "res://themes/flash/art_standin/%s.png"

## Every art id the screens and the Stage may ask for (a test checks each resolves to something).
const IDS := ["backdrop_far", "backdrop_near", "logo", "move_scavenge", "move_guard", "move_steal", "move_investigate",
	"move_gift", "hut", "hut_me", "campfire", "campfire_glow", "avatar_0", "avatar_1", "avatar_2", "avatar_3", "avatar_4",
	"avatar_5", "avatar_6", "avatar_7", "fx_spark", "fx_crumb", "fx_ring", "fx_shield", "card_frame", "button_wood",
	"button_wood_pressed"]
## Ids only the stand-in set carries. Without them a screen draws a plain shape or nothing.
const EXTRAS := ["cloud", "vignette", "crown", "lantern_on", "lantern_off"]


## The first path that exists for `id`; `exists` is injectable so a test can prove the order without touching disk.
static func path_for(id: String, exists: Callable = Callable()) -> String:
	for template in [REAL, STANDIN]:
		var p: String = template % id
		var found: bool = exists.call(p) if exists.is_valid() else ResourceLoader.exists(p)
		if found:
			return p
	return ""


static func load_texture(id: String) -> Texture2D:
	var p := path_for(id)
	if p == "":
		return null
	var t: Variant = load(p)
	return t if t is Texture2D else null
