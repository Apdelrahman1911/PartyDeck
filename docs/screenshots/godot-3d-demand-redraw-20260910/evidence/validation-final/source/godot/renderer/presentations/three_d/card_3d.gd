extends Node3D

const PAPER := Color("#f4f0e8")
const CITRON := Color("#d6ef82")
var face: MeshInstance3D
var _border: MeshInstance3D


func _ready() -> void:
	_border = _box(Vector3(1.11, 0.018, 1.65), CITRON)
	_border.position.y = -0.023
	_border.visible = false
	_box(Vector3(1.035, 0.035, 1.575), PAPER.darkened(0.09))
	face = MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(1.06, 1.59)
	face.mesh = plane
	face.position.y = 0.02
	add_child(face)


func configure(rank: String, face_up: bool, selected: bool, private_card: bool) -> void:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	material.albedo_texture = load("res://assets/textures/cards/face_%s.png" % rank.to_lower()
		if face_up else "res://assets/textures/cards/back.png")
	face.material_override = material
	if private_card and face_up:
		face.add_to_group("partydeck_private_face")
	_border.visible = selected


func lift(selected: bool, reduce_motion: bool) -> void:
	if not selected:
		return
	var destination := position + Vector3(0, 0.18, 0)
	if reduce_motion:
		position = destination
	else:
		create_tween().tween_property(self, "position", destination, 0.14).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func corners() -> Array[Vector3]:
	return [to_global(Vector3(-0.53, 0.03, -0.795)), to_global(Vector3(0.53, 0.03, -0.795)),
		to_global(Vector3(0.53, 0.03, 0.795)), to_global(Vector3(-0.53, 0.03, 0.795))]


func _box(dimensions: Vector3, color: Color) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = dimensions
	instance.mesh = mesh
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.9
	instance.material_override = material
	add_child(instance)
	return instance
