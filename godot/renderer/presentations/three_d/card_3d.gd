extends Node3D

const PAPER := Color("#f4f0e8")
const CITRON := Color("#d6ef82")

class SharedResources:
	extends RefCounted
	var border_mesh: BoxMesh
	var body_mesh: BoxMesh
	var face_mesh: PlaneMesh
	var border_material: StandardMaterial3D
	var body_material: StandardMaterial3D

var face: MeshInstance3D
var _border: MeshInstance3D
var _shared_resources: SharedResources


static func create_shared_resources() -> SharedResources:
	# These resources contain no card state and remain immutable after construction.
	var resources := SharedResources.new()
	resources.border_mesh = BoxMesh.new()
	resources.border_mesh.size = Vector3(1.11, 0.018, 1.65)
	resources.body_mesh = BoxMesh.new()
	resources.body_mesh.size = Vector3(1.035, 0.035, 1.575)
	resources.face_mesh = PlaneMesh.new()
	resources.face_mesh.size = Vector2(1.06, 1.59)
	resources.border_material = StandardMaterial3D.new()
	resources.border_material.albedo_color = CITRON
	resources.border_material.roughness = 0.9
	resources.body_material = StandardMaterial3D.new()
	resources.body_material.albedo_color = PAPER.darkened(0.09)
	resources.body_material.roughness = 0.9
	return resources


func set_shared_resources(resources: SharedResources) -> void:
	assert(not is_inside_tree() and resources != null)
	_shared_resources = resources


func _ready() -> void:
	assert(_shared_resources != null)
	_border = _box(_shared_resources.border_mesh, _shared_resources.border_material)
	_border.position.y = -0.023
	_border.visible = false
	_box(_shared_resources.body_mesh, _shared_resources.body_material)
	face = MeshInstance3D.new()
	face.mesh = _shared_resources.face_mesh
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


func _box(mesh: BoxMesh, material: StandardMaterial3D) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	instance.material_override = material
	add_child(instance)
	return instance
