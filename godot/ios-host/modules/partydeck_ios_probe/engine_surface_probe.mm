// A compile-time source probe, not an EmbeddedGameFactory or a runtime success signal.
// The exact upstream sources and lifecycle limits are recorded in ../../README.md.
#include "register_types.h"

#import "drivers/apple_embedded/app_delegate_service.h"
#import "drivers/apple_embedded/godot_view_apple_embedded.h"
#import "drivers/apple_embedded/godot_view_controller.h"
#import "drivers/apple_embedded/godot_view_renderer.h"
#import "drivers/apple_embedded/os_apple_embedded.h"

#include <type_traits>

// These are the actual definitions in platform/ios/main_ios.mm. They are
// internal C++ export-template entry points, not the desktop LibGodot C API.
extern int apple_embedded_main(int argc, char **argv);
extern void apple_embedded_finish();

using AppleBootstrap = int (*)(int, char **);
using AppleFinish = void (*)();
static_assert(std::is_same_v<decltype(&apple_embedded_main), AppleBootstrap>);
static_assert(std::is_same_v<decltype(&apple_embedded_finish), AppleFinish>);

// Keep real symbol references in the combined archive for the compile/link audit.
__attribute__((used)) static AppleBootstrap bootstrap_reference = &apple_embedded_main;
__attribute__((used)) static AppleFinish finish_reference = &apple_embedded_finish;

@interface PDGodotHostViewController : GDTViewController
@end

@implementation PDGodotHostViewController

- (void)propagateUIPreferencesToRootViewController {
    // The host owns its root controller. Upstream otherwise replaces methods on
    // that controller's class, affecting views outside the engine presentation.
}

@end

void initialize_partydeck_ios_probe_module(ModuleInitializationLevel level) {
    // Runtime host wiring is a separate execution gate. No engine, native view,
    // success event, or game registration is created by this source-only probe.
}

void uninitialize_partydeck_ios_probe_module(ModuleInitializationLevel level) {
}
