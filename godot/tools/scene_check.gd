extends SceneTree

# Structural validation only. Rules and accepted intents belong to the Kotlin
# authority/comparison driver; this script neither invents nor accepts actions.
const SCENES: Array[String] = [
	"res://main.tscn",
	"res://presentations/two_d/table.tscn",
	"res://presentations/three_d/table.tscn",
]


func _initialize() -> void:
	call_deferred("_check_scenes")


func _check_scenes() -> void:
	var checked: Array[String] = []
	for path in SCENES:
		var resource: Resource = ResourceLoader.load(path, "PackedScene")
		if not resource is PackedScene:
			push_error("Required renderer scene did not load: " + path)
			quit(1)
			return
		var scene: PackedScene = resource as PackedScene
		if not scene.can_instantiate():
			push_error("Required renderer scene cannot instantiate: " + path)
			quit(1)
			return
		var instance: Node = scene.instantiate()
		if instance == null:
			push_error("Required renderer scene returned no instance: " + path)
			quit(1)
			return
		instance.free()
		checked.append(path)
	print("PARTYDECK_SCENE_CHECK=" + JSON.stringify({"ok": true, "scenes": checked}))
	quit(0)
