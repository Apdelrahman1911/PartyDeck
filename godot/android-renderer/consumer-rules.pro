# GodotPlugin registration reflects methods and their runtime annotations.
-keepattributes RuntimeVisibleAnnotations
-keepclassmembers class dev.partydeck.godot.android.PartyDeckBridgePlugin {
    @org.godotengine.godot.plugin.UsedByGodot <methods>;
}
