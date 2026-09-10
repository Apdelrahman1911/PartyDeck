# GodotPlugin registration reflects methods and their runtime annotations.
-keepattributes RuntimeVisibleAnnotations
-keepclassmembers class dev.partydeck.godot.android.PartyDeckBridgePlugin {
    @org.godotengine.godot.plugin.UsedByGodot <methods>;
}

# Godot 4.7.2 native code resolves these callbacks by exact JVM name and descriptor.
# NativeBridge @Keep does not retain the names of its descriptor classes.
# https://developer.android.com/topic/performance/app-optimization/keep-rule-examples#java-native-interface-jni
# https://github.com/godotengine/godot/tree/4.7.2-stable/platform/android

# java_godot_wrapper.cpp
-keepclassmembers,includedescriptorclasses class org.godotengine.godot.nativeapi.GodotNativeBridge {
    org.godotengine.godot.GodotRenderView getRenderView();
}

# java_godot_io_wrapper.cpp
-keepclassmembers,includedescriptorclasses class org.godotengine.godot.GodotIO {
    int openURI(java.lang.String);
    java.lang.String getCacheDir();
    java.lang.String getTempDir();
    java.lang.String getDataDir();
    int[] getDisplayCutouts();
    int[] getDisplaySafeArea();
    java.lang.String getLocale();
    java.lang.String getModel();
    int getScreenDPI();
    float getScaledDensity();
    double getScreenRefreshRate(double);
    java.lang.String getUniqueID();
    void showKeyboard(java.lang.String, int, int, int, int);
    void hideKeyboard();
    boolean hasHardwareKeyboard();
    void setScreenOrientation(int);
    int getScreenOrientation();
    java.lang.String getSystemDir(int, boolean);
    int getDisplayRotation();
}

# net_socket_android.cpp
-keepclassmembers,includedescriptorclasses class org.godotengine.godot.utils.GodotNetUtils {
    void multicastLockAcquire();
    void multicastLockRelease();
}

# dir_access_jandroid.cpp
-keepclassmembers,includedescriptorclasses class org.godotengine.godot.io.directory.DirectoryAccessHandler {
    int dirOpen(int, java.lang.String);
    java.lang.String dirNext(int);
    void dirClose(int);
    boolean dirIsDir(int);
    boolean dirExists(int, java.lang.String);
    boolean fileExists(int, java.lang.String);
    int getDriveCount(int);
    java.lang.String getDrive(int, int);
    boolean makeDir(int, java.lang.String);
    long getSpaceLeft(int);
    boolean rename(int, java.lang.String, java.lang.String);
    boolean remove(int, java.lang.String);
    boolean isCurrentHidden(int);
}

# file_access_filesystem_jandroid.cpp
-keepclassmembers,includedescriptorclasses class org.godotengine.godot.io.file.FileAccessHandler {
    int fileOpen(java.lang.String, int);
    long fileGetSize(int);
    long fileGetPosition(int);
    boolean isFileEof(int);
    void setFileEof(int, boolean);
    void fileSeek(int, long);
    void fileSeekFromEnd(int, long);
    int fileRead(int, java.nio.ByteBuffer);
    void fileClose(int);
    boolean fileWrite(int, java.nio.ByteBuffer);
    void fileFlush(int);
    boolean fileExists(java.lang.String);
    long fileLastModified(java.lang.String);
    long fileLastAccessed(java.lang.String);
    int fileResize(int, long);
    long fileSize(java.lang.String);
}

# java_godot_view_wrapper.cpp looks up these members on the concrete render view.
-keepclassmembers class org.godotengine.godot.** implements org.godotengine.godot.GodotRenderView {
    void configurePointerIcon(int, java.lang.String, float, float);
    void setPointerIcon(int);
    void requestPointerCapture();
    void releasePointerCapture();
    boolean canCapturePointer();
}
