# Android 3D failure investigation — run 34439587132

Both retained Android 3D cases failed. The 100% text case reached Ready and a foreground frame but timed out waiting for diagnostic request 2. The 200% text case completed Reveal, selection, Hide, Home, and Recents observations, then its existing Godot process crashed during resume. Neither case executed a play, challenge, or next-round intent.

This is a read-only investigation of existing artifacts. It made no project source changes, ran no new native session, and captured no new screenshots. All ten original runtime PNGs and all runtime logs are copied byte-for-byte under `runtime/`; `provenance.json` records their original paths and hashes. Failed cases remain failed.

## Exact inputs

- PartyDeck commit: `ff6e0ac04f917c2830c98cf25cee2b3220b151e4`.
- Debug APK: `8be9d3f1714895c541b6e3936e411df61a6f332cb1f8e66308148d3548795b51`.
- Embedded PCK: `6599f825a418f9d2a7049b3ba9325e8e0dcb474685262899079231b7ec955938`.
- Checker `run.py`: `037536435de365752a1863c5128bbfb9254d0cb9d53f2bb7c585e100928ce89d`.
- Native logs identify Godot `4.7.2.stable.official.ed1daf0bf`, GLES compatibility, API 35 x86_64 emulator with ANGLE/SwiftShader.
- Godot tag `4.7.2-stable` resolves to `ed1daf0bf001b61586d9930840f2f1394092c079` in the retained authoritative tag response.
- Project sources come from the already retained exact-run archive, not the changing workspace. Java sources match individual entries in the pinned Maven sources JAR. Native source URLs and hashes are recorded in the manifest.

## 100% text: a real diagnostic timeout after Ready

`runtime/font-1.0/result.json` reports `A native diagnostic request timed out.` at `3d match entry`.

The host accepted Ready. Evidence revision 11 has request 2 pending, response 1/sequence 0 retained, and `foregroundFrameReady=false`. By revision 13 a foreground frame is ready and the cover has gone, but `diagnosticsTimedOut=true` and response 1 remains. Response 1 contains initial unlaid-out control rectangles, including Reveal `[0, 0, 32, 52]`; it is not a fresh laid-out response to request 2.

The retained process log has:

| Time on 2026-09-10 UTC | Observation |
| --- | --- |
| 05:11:54.189 | `OnGodotMainLoopStarted` |
| 05:11:54.472 | Previous EGL frame-stat report |
| 05:11:56.231 | `WARNING: Failed to load cached shader, recompiling.` |
| 05:11:57.233 | A single observed render interval of `2761.75ms` |

Exact-run `GodotGameActivity.kt:473–487` arms a 2,000 ms watchdog immediately after `requestDiagnostics` accepts a queued request. `scheduleDiagnostics` checks Ready/foreground but not foreground-frame delivery. It is called on Ready and foreground changes, before the two-draw cover callback. The plugin posts diagnostics through the render-thread event queue. After timeout, it clears `diagnosticsExpected`; a subsequent response is dropped by `PartyDeckBridgePlugin.kt:134–139`.

These facts are consistent with a request expiring while queued behind initial rendering/shader work. The original records have no exact per-request enqueue, delivery, or response timestamps, so the specific latency attribution is not proven. The bounded correction to assess is to schedule initial diagnostics after delivered foreground draws, preserving the strict checker and its failure result. Merely increasing the timeout would not establish delivery.

## 200% text: native resume crash

`runtime/font-2.0/result.json` reports `Native or renderer failure appeared in the actual engine process log.` at `3d background privacy`. That stage includes the attempted return from Home/Recents. The process trace establishes a native crash, independently of the checker classification:

| Time on 2026-09-10 UTC | PID/TID | Observation |
| --- | --- | --- |
| 05:13:18.887 | 3106/3106 | `OnStop` |
| 05:13:19.062 | 3106/3141 | Abandoned BufferQueue and `EGL_BAD_SURFACE` |
| 05:13:32.985 | 3106/3106 | `OnStart` of the existing Godot fragment |
| 05:13:32.995 | 3106/3106 | `OnResume` |
| 05:13:33.013 | 3106/3141 | `call to OpenGL ES API with no current context` |
| 05:13:33.328–333 | 3106/3141 | Repeated GL error `0x502` in `s_glVertexAttribPointer`, condition `currentVertexArrayObject() != 0 && ptr` |
| 05:13:33.333 | 3106/3141 | `SIGSEGV`, address `0x230`, thread `GLThread 44` |

The full tombstone is retained in `runtime/font-2.0/logcat.log:27895`. It reports `memcpy`, `glVertexAttribPointerData_enc`, `GL2Encoder::sendVertexAttributes`, `GL2Encoder::s_glDrawArrays`, and `base.apk!libgodot_android.so` PC `0x22b045a`.

The exact APK's `lib/x86_64/libgodot_android.so` has SHA-256 `7ce311ee6319c21d11740c29d636720ab219db13c7d17de4847fb6dd778e860f` and the tombstone BuildId `ae8c6200a500554c8ea0a5ca4317c45b008d28e3`. Its disassembly places a `glDrawArrays@plt` call at `0x22b0456`, covering the reported PC. It has neither `.symtab` nor `.debug_info`. `addr2line` prints the distant preceding exported symbol `WebPPictureRescale`; that output does **not** identify the crashing function. Raw inspection outputs are retained under `native-binary-inspection/`; the large original extracted binary remains outside this receipt, with its path recorded in the manifest.

The last persisted host facts are revision 36, background, foreground false, cover visible, and three submitted commands. They retain pre-background diagnostic 12/sequence 11, which had a revealed hand and one selected card. No resumed diagnostic was accepted. That stale response is neither evidence of a resumed privacy leak nor proof that no resume command was attempted before process death prevented further evidence writes.

## Source-proven unsafe allocation path

The pinned engine and exact-run project establish a synchronous path that can allocate OpenGL resources while the Java GL thread has no current EGL context:

1. `GodotGLRenderView.java:119–124` queues resume work that calls `GodotRenderer.onActivityResumed()` and then `GodotLib.focusin()` immediately. Its pause path also queues focus notification work. Preserving the EGL context (`:244`) does not keep that context current after the surface is destroyed.
2. `GLSurfaceView.java:1364–1367` removes queued Runnables before its pause/surface checks. It executes the Runnable and continues at `:1535–1538`, before `createSurface` and its `eglMakeCurrent` path. Pause destroys/unbinds the EGL surface. Thus being on the GL thread does not establish a current context.
3. `GodotRenderer.java:89–92` explicitly delays `onRendererResumed()` until its draw callback to guarantee a valid context/surface. That delay does not cover the separate `focusin()` invocation above.
4. `java_godot_lib_jni.cpp:501–506` calls `OS_Android::main_loop_focusin` synchronously. `os_android.cpp:456–462` sends the application focus notification, and `scene_tree.cpp:934–946` propagates it immediately to nodes.
5. Exact-run `main.gd:146–152` immediately calls `controller.set_window_foreground`. `renderer_controller.gd:188–195` publishes state even if effective foreground remains false. Both main and the 3D table receive that state synchronously. `three_d/table.gd:52–77` rebuilds layout and cards on every nonclosed state update; `_cylinder` at `:604–619` assigns a newly created primitive mesh.
6. `mesh_instance_3d.cpp:120–134` calls the primitive mesh's `get_rid`; `primitive_meshes.cpp:234–238` runs its pending `_update`; `:128–130` calls `mesh_add_surface_from_arrays`. `rendering_server.cpp:1395–1401` immediately dispatches `mesh_add_surface`.
7. `rendering_server_default.h:117` queues a call only when the caller differs from `server_thread`. `FUNC2` in `server_wrap_mt_common.h:267–275` otherwise flushes pending commands and calls mesh storage directly. `RenderingServerDefault::init` uses `Thread::MAIN_ID` when separate rendering is disabled. The exact-run project and Activity set no separate-thread override; the default is safe rendering on the main engine thread. Android runs `Main::setup2` from `GodotLib.step`, and `main.cpp:3037` marks that same Java GL draw thread as `Thread::MAIN_ID`.
8. GLES3 `mesh_storage.cpp:221–269` directly calls `glGenBuffers`, `glBindBuffer`, and buffer allocation. Later vertex-array setup binds these buffers and uses attribute byte offsets at `:1019–1045`. Missing a valid context during allocation is a concrete resource hazard consistent with the later invalid vertex attribute handling.

There is another entry to the same synchronous project code. Exact-run `PartyDeckBridgePlugin.kt:69–86` schedules native commands through `engine.runOnRenderThread`. The pinned `GodotPlugin.emitSignal` itself queues a second Runnable (`GodotPlugin.java:456`), which invokes the directly connected `main.gd` command receiver. Scheduling only the outer native queue from a draw callback would not remove this second queued path or Godot's independent focus notification path.

The specific callback that made the first context-free GL call was not instrumented in this run. The call path is source-proven and closely matches the native chronology, but this receipt does not claim that a corrective patch has been validated.

## Correction contract to coordinate and verify

The bounded candidate is to keep controller privacy/input state changes synchronous, and move scene/resource reconciliation to an always-processing main engine frame. Reconcile the latest controller state using one dirty indication; do not queue private state dictionaries for later replay. Both tables' direct resource-building state callbacks and main's scene mount/removal path must obey the boundary, including focus notifications, bridge commands, and close.

Ready must continue to mean successful initial presentation setup. Native input must remain blocked and its cover opaque until the concealed latest state has been reconciled and the required foreground draws completed. `GodotRenderer.onDrawFrame` dispatches each plugin's `onGLDrawFrame` after `GodotLib.step`, but the paused SceneTree/low-processor semantics, command acknowledgments, Ready ordering, diagnostics timing, and existing renderer checks need explicit review before implementation. `/root/ui_game` is independently examining those frame semantics; `/root/android_platform` owns the diagnostic scheduling finding.

A fresh native execution is required to qualify any correction. It must preserve strict process-log checks and verify resume/privacy, layout diagnostics, and actual authority-backed actions at the required text scales. Desktop behavior or a source review alone cannot replace that evidence.
