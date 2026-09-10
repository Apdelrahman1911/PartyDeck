# Runtime GodotPlugin registration reflects declared methods and their annotations.
-keepattributes RuntimeVisibleAnnotations
-keepclassmembers class dev.partydeck.godot.compare.PartyDeckBridgePlugin {
    @org.godotengine.godot.plugin.UsedByGodot <methods>;
}
