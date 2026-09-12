extends Node3D

const PAPER := Color("#f4f0e8")
const CITRON := Color("#d6ef82")
const FACE_SIZE := Vector2(1.06, 1.59)
# Same quadratic corner as the shared card artwork's 160 by 240 viewBox.
const CORNER_INSET := 1.06 * 12.0 / 160.0
const CORNER_STEPS := 8

class SharedResources:
	extends RefCounted
	var border_mesh: ArrayMesh
	var body_mesh: ArrayMesh
	var face_mesh: ArrayMesh
	var border_material: StandardMaterial3D
	var body_material: StandardMaterial3D
	var back_material: StandardMaterial3D
	var face_materials: Dictionary = {}

var face: MeshInstance3D
var _border: MeshInstance3D
var _shared_resources: SharedResources


static func create_shared_resources() -> SharedResources:
	# These resources contain no card state and remain immutable after construction.
	var resources := SharedResources.new()
	resources.border_mesh = _rounded_mesh(Vector2(1.11, 1.65), CORNER_INSET + 0.0275, 0.018)
	resources.body_mesh = _rounded_mesh(Vector2(1.035, 1.575), CORNER_INSET, 0.035)
	resources.face_mesh = _rounded_mesh(FACE_SIZE, CORNER_INSET)
	resources.border_material = StandardMaterial3D.new()
	resources.border_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	resources.border_material.albedo_color = CITRON
	resources.border_material.roughness = 0.9
	resources.body_material = StandardMaterial3D.new()
	resources.body_material.albedo_color = PAPER.darkened(0.09)
	resources.body_material.roughness = 0.9
	resources.back_material = _art_material("res://assets/textures/cards/back.png")
	# A fixed set of generic artwork, never a cache keyed by private card identities.
	for rank in ["CROWN", "MOON", "STAR", "WILD"]:
		resources.face_materials[rank] = _art_material("res://assets/textures/cards/face_%s.png" % rank.to_lower())
	return resources


static func _art_material(texture_path: String) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	# The outline is geometry, so MSAA smooths it without alpha-scissor aliasing.
	# Alpha-to-coverage is a no-op in the pinned Compatibility renderer:
	# https://github.com/godotengine/godot/blob/4.7.2-stable/drivers/gles3/rasterizer_scene_gles3.cpp#L3445
	material.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	material.texture_repeat = false
	material.albedo_texture = load(texture_path)
	return material


static func _rounded_mesh(size: Vector2, corner_inset: float, thickness: float = 0.0) -> ArrayMesh:
	var outline := _rounded_outline(size, corner_inset)
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var top := thickness * 0.5
	for index in range(outline.size()):
		var next := (index + 1) % outline.size()
		var point := outline[index]
		var following := outline[next]
		# Clockwise front faces, matching Godot's PlaneMesh orientation and UVs.
		_mesh_vertex(surface, Vector2.ZERO, top, Vector3.UP, size)
		_mesh_vertex(surface, point, top, Vector3.UP, size)
		_mesh_vertex(surface, following, top, Vector3.UP, size)
		if thickness == 0.0:
			continue
		_mesh_vertex(surface, Vector2.ZERO, -top, Vector3.DOWN, size)
		_mesh_vertex(surface, following, -top, Vector3.DOWN, size)
		_mesh_vertex(surface, point, -top, Vector3.DOWN, size)
		var normal := _edge_normal(outline, index)
		var next_normal := _edge_normal(outline, next)
		_mesh_vertex(surface, point, top, normal, size)
		_mesh_vertex(surface, point, -top, normal, size)
		_mesh_vertex(surface, following, top, next_normal, size)
		_mesh_vertex(surface, following, top, next_normal, size)
		_mesh_vertex(surface, point, -top, normal, size)
		_mesh_vertex(surface, following, -top, next_normal, size)
	return surface.commit()


static func _rounded_outline(size: Vector2, inset: float) -> PackedVector2Array:
	var half := size * 0.5
	var corners := [
		PackedVector2Array([Vector2(half.x - inset, -half.y), Vector2(half.x, -half.y), Vector2(half.x, -half.y + inset)]),
		PackedVector2Array([Vector2(half.x, half.y - inset), Vector2(half.x, half.y), Vector2(half.x - inset, half.y)]),
		PackedVector2Array([Vector2(-half.x + inset, half.y), Vector2(-half.x, half.y), Vector2(-half.x, half.y - inset)]),
		PackedVector2Array([Vector2(-half.x, -half.y + inset), Vector2(-half.x, -half.y), Vector2(-half.x + inset, -half.y)]),
	]
	var outline := PackedVector2Array()
	for corner: PackedVector2Array in corners:
		for step in range(CORNER_STEPS + 1):
			var weight := float(step) / CORNER_STEPS
			outline.append(corner[0].lerp(corner[1], weight).lerp(corner[1].lerp(corner[2], weight), weight))
	return outline


static func _edge_normal(outline: PackedVector2Array, index: int) -> Vector3:
	var tangent := outline[(index + 1) % outline.size()] - outline[(index + outline.size() - 1) % outline.size()]
	return Vector3(tangent.y, 0.0, -tangent.x).normalized()


static func _mesh_vertex(surface: SurfaceTool, point: Vector2, height: float, normal: Vector3, size: Vector2) -> void:
	surface.set_normal(normal)
	surface.set_uv(point / size + Vector2(0.5, 0.5))
	surface.add_vertex(Vector3(point.x, height, point.y))


func set_shared_resources(resources: SharedResources) -> void:
	assert(not is_inside_tree() and resources != null)
	_shared_resources = resources


func _ready() -> void:
	assert(_shared_resources != null)
	_border = _mesh_instance(_shared_resources.border_mesh, _shared_resources.border_material)
	_border.position.y = -0.023
	_border.visible = false
	_mesh_instance(_shared_resources.body_mesh, _shared_resources.body_material)
	face = MeshInstance3D.new()
	face.mesh = _shared_resources.face_mesh
	face.material_override = _shared_resources.back_material
	face.position.y = 0.02
	add_child(face)


func configure(rank: String, face_up: bool, selected: bool, private_card: bool) -> void:
	var material := _shared_resources.back_material
	var showing_face := false
	if face_up:
		var face_material: StandardMaterial3D = _shared_resources.face_materials.get(rank.to_upper())
		if face_material != null:
			material = face_material
			showing_face = true
	face.material_override = material
	if private_card and showing_face:
		face.add_to_group("partydeck_private_face")
	elif face.is_in_group("partydeck_private_face"):
		face.remove_from_group("partydeck_private_face")
	_border.visible = selected and showing_face


func lift(selected: bool, reduce_motion: bool) -> void:
	if not selected or not _border.visible:
		return
	var destination := position + Vector3(0, 0.18, 0)
	if reduce_motion:
		position = destination
	else:
		create_tween().tween_property(self, "position", destination, 0.14).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func corners() -> Array[Vector3]:
	return [to_global(Vector3(-0.53, 0.03, -0.795)), to_global(Vector3(0.53, 0.03, -0.795)),
		to_global(Vector3(0.53, 0.03, 0.795)), to_global(Vector3(-0.53, 0.03, 0.795))]


func _mesh_instance(mesh: Mesh, material: StandardMaterial3D) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	instance.material_override = material
	add_child(instance)
	return instance
