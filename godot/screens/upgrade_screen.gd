class_name UpgradeScreen
extends Control
## The server needs a newer app. Nothing else on this screen works, so it says so and offers nothing.


func _ready() -> void:
	var col := Ui.page(self)
	col.add_child(Ui.label(Words.render("ui.app_name"), "app_name", "BigLabel"))
	col.add_child(Ui.label(Words.render("notice.upgrade_required"), "upgrade"))
