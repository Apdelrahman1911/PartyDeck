// Source-coupled iOS experiment against the exact engine recorded in README.md.
// Real bootstrap, SceneTree, input, rendering and cleanup; one attempt/process.
#include "register_types.h"
#include "strict_json.h"
#import "PDGodotRuntime.h"
#import "PDGodotEngineOwner.h"

#include "core/config/engine.h"
#include "core/config/project_settings.h"
#include "core/input/input.h"
#include "core/io/resource_loader.h"
#include "core/object/class_db.h"
#include "core/object/message_queue.h"
#include "core/os/main_loop.h"
#include "core/os/os.h"
#include "main/main.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"
#include "scene/resources/packed_scene.h"
#include "servers/rendering/rendering_server.h"
#include "drivers/coreaudio/audio_driver_coreaudio.h"

#import <AVFoundation/AVFoundation.h>
#import <CommonCrypto/CommonDigest.h>
#import <CoreMotion/CoreMotion.h>
#import <OpenGLES/EAGL.h>
#import <OpenGLES/ES3/gl.h>

#import "drivers/apple_embedded/app_delegate_service.h"
#import "drivers/apple_embedded/display_layer_apple_embedded.h"
#import "drivers/apple_embedded/display_server_apple_embedded.h"
#import "drivers/apple_embedded/godot_view_controller.h"
#import "drivers/apple_embedded/godot_view_renderer.h"
#import "drivers/apple_embedded/os_apple_embedded.h"
#import "platform/ios/display_layer_ios.h"
#import "platform/ios/godot_view_ios.h"

#include <cmath>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

extern int apple_embedded_main(int argc, char **argv);
extern void apple_embedded_finish();

static const NSUInteger PDCommandLimit = 65536;
static const NSUInteger PDEventLimit = 4096;
static const NSUInteger PDDiagnosticsLimit = 16384;
static const NSUInteger PDQueueCountLimit = 16;
static const NSUInteger PDQueueByteLimit = 262144;
static const NSUInteger PDSceneNodeLimit = 4096;
static const NSUInteger PDEmptyFrameLimit = 3;
static const NSUInteger PDConcealedSampleLimit = 8;
static const NSTimeInterval PDDormantObservationInterval = 0.6;

// Fixed numeric diagnostics owned by the native main thread. These inclusive
// scopes overlap (drawView contains renderOnView, which contains iterate); their
// durations must not be added. No scope stores scene, input or bridge data.
struct PDNativeStageTiming {
	uint64_t completed_count = 0;
	uint64_t current_depth = 0;
	uint64_t max_depth = 0;
	double active_started_uptime = 0;
	double last_seconds = 0;
	double max_seconds = 0;
	double last_completed_uptime = 0;
	double max_completed_uptime = 0;

	void begin(double now) {
		if (current_depth == 0) { active_started_uptime = now; }
		++current_depth;
		if (current_depth > max_depth) { max_depth = current_depth; }
	}

	void finish(double started, double now) {
		--current_depth;
		if (current_depth == 0) { active_started_uptime = 0; }
		last_seconds = now >= started ? now - started : 0;
		last_completed_uptime = now;
		if (completed_count == 0 || last_seconds > max_seconds) {
			max_seconds = last_seconds;
			max_completed_uptime = now;
		}
		if (completed_count != UINT64_MAX) { ++completed_count; }
	}
};

struct PDNativeTimings {
	PDNativeStageTiming draw_view;
	PDNativeStageTiming uikit_pump;
	PDNativeStageTiming setup_view;
	PDNativeStageTiming render_on_view;
	PDNativeStageTiming iterate;
	PDNativeStageTiming present_renderbuffer;
	PDNativeStageTiming drain;
};

static double PDNativeTimingUptime() {
	return NSProcessInfo.processInfo.systemUptime;
}

class PDNativeTimingScope {
	PDNativeStageTiming &stage;
	const double started;

public:
	explicit PDNativeTimingScope(PDNativeStageTiming &p_stage) : stage(p_stage), started(PDNativeTimingUptime()) {
		stage.begin(started);
	}
	~PDNativeTimingScope() {
		stage.finish(started, PDNativeTimingUptime());
	}
	PDNativeTimingScope(const PDNativeTimingScope &) = delete;
	PDNativeTimingScope &operator=(const PDNativeTimingScope &) = delete;
};

// Dictionary allocation stays in the existing snapshot path, outside the timed
// hot path. Uptime marks completion/publication, not a renderer freshness grant.
static NSDictionary *PDNativeStageTimingSnapshot(const PDNativeStageTiming &stage) {
	return @{
		@"completedCount": @(stage.completed_count), @"currentDepth": @(stage.current_depth), @"maxDepth": @(stage.max_depth),
		@"activeStartedUptime": @(stage.active_started_uptime),
		@"lastSeconds": @(stage.last_seconds), @"maxSeconds": @(stage.max_seconds),
		@"lastCompletedUptime": @(stage.last_completed_uptime), @"maxCompletedUptime": @(stage.max_completed_uptime)
	};
}

static BOOL processConsumed = NO;
static NSUInteger processBootstrapCount = 0;
static PDGodotRuntime *activeRuntime = nil;
#ifdef SDL_ENABLED
static const BOOL PDSDLEnabled = YES;
#else
static const BOOL PDSDLEnabled = NO;
#endif

// This lifecycle is audited for the frozen trusted content, including its
// imported resources. A different pack requires a new content/source review.
static NSString *const PDQualifiedRetainedPackSHA256 = @"557b2297bed133a433acc25efa4837462465dd4e06da659ae5a4cbd792f77fe0";

static NSString *PDPackSHA256(NSString *path) {
	NSDictionary *attributes = [NSFileManager.defaultManager attributesOfItemAtPath:path error:nil];
	if (!attributes || [attributes[NSFileSize] unsignedLongLongValue] > 8 * 1024 * 1024) { return nil; }
	NSData *data = [NSData dataWithContentsOfFile:path options:NSDataReadingMappedIfSafe error:nil];
	if (!data) { return nil; }
	unsigned char digest[CC_SHA256_DIGEST_LENGTH];
	CC_SHA256(data.bytes, static_cast<CC_LONG>(data.length), digest);
	NSMutableString *value = [NSMutableString stringWithCapacity:CC_SHA256_DIGEST_LENGTH * 2];
	for (unsigned char byte : digest) { [value appendFormat:@"%02x", byte]; }
	return value;
}

static AudioDriverCoreAudio *PDCoreAudioDriver() {
	// AudioDriver's upstream static pointer is not cleared by its destructor.
	// Never inspect it after terminal OS/AudioServer cleanup.
	if (!OS::get_singleton() || !AudioServer::get_singleton()) { return nullptr; }
	AudioDriver *driver = AudioDriver::get_singleton();
	// The pinned build registers this exact concrete driver under this name.
	return driver && std::strcmp(driver->get_name(), "CoreAudio") == 0 ? static_cast<AudioDriverCoreAudio *>(driver) : nullptr;
}

static BOOL PDAudioStopped(const AudioDriverCoreAudio::PartyDeckOutputState &state) {
	return state.observed_on_main_thread && state.output_unit_present && !state.input_unit_present && !state.active &&
			state.output_callbacks_in_flight == 0 && state.start_attempts > 0 && state.stop_attempts > 0 &&
			state.last_stop_status == noErr && state.stopped_start_attempt == state.start_attempts;
}

static NSDictionary *PDAudioSnapshot() {
	AudioDriverCoreAudio *driver = PDCoreAudioDriver();
	if (!driver) { return @{ @"driver": @"unavailable_or_unsupported", @"observed": @NO }; }
	auto state = driver->get_partydeck_output_state();
	return @{ @"driver": @"CoreAudio", @"observed": @(state.observed_on_main_thread),
		@"outputUnitPresent": @(state.output_unit_present), @"inputUnitPresent": @(state.input_unit_present),
		@"active": @(state.active), @"callbackEntries": @(state.output_callback_entries).stringValue,
		@"callbacksInFlight": @(state.output_callbacks_in_flight), @"startAttempts": @(state.start_attempts),
		@"stopAttempts": @(state.stop_attempts), @"lastStartStatus": @(state.last_start_status),
		@"lastStopStatus": @(state.last_stop_status), @"stoppedStartAttempt": @(state.stopped_start_attempt) };
}

static NSUInteger PDBridgeConnectionCount(Object *object) {
	if (!object) { return 0; }
	List<Object::Connection> commands;
	List<Object::Connection> diagnostics;
	object->get_signal_connection_list("command_received", &commands);
	object->get_signal_connection_list("diagnostics_requested", &diagnostics);
	return commands.size() + diagnostics.size();
}

static void PDConfigureFreshTree(SceneTree *tree) {
	// Reapply the Main::start root settings for the fixed non-editor project.
	// The native shell owns quit and supplies a fresh scene explicitly.
	Window *root = tree->get_root();
	String mode = GLOBAL_GET("display/window/stretch/mode");
	String aspect = GLOBAL_GET("display/window/stretch/aspect");
	String stretch = GLOBAL_GET("display/window/stretch/scale_mode");
	root->set_content_scale_mode(mode == "canvas_items" ? Window::CONTENT_SCALE_MODE_CANVAS_ITEMS :
			mode == "viewport" ? Window::CONTENT_SCALE_MODE_VIEWPORT : Window::CONTENT_SCALE_MODE_DISABLED);
	root->set_content_scale_aspect(aspect == "keep" ? Window::CONTENT_SCALE_ASPECT_KEEP :
			aspect == "keep_width" ? Window::CONTENT_SCALE_ASPECT_KEEP_WIDTH :
			aspect == "keep_height" ? Window::CONTENT_SCALE_ASPECT_KEEP_HEIGHT :
			aspect == "expand" ? Window::CONTENT_SCALE_ASPECT_EXPAND : Window::CONTENT_SCALE_ASPECT_IGNORE);
	root->set_content_scale_stretch(stretch == "integer" ? Window::CONTENT_SCALE_STRETCH_INTEGER : Window::CONTENT_SCALE_STRETCH_FRACTIONAL);
	root->set_content_scale_size(Size2i(GLOBAL_GET("display/window/size/viewport_width"), GLOBAL_GET("display/window/size/viewport_height")));
	root->set_content_scale_factor(GLOBAL_GET("display/window/stretch/scale"));
	root->set_snap_controls_to_pixels(GLOBAL_GET("gui/common/snap_controls_to_pixels"));
	root->set_drag_threshold(GLOBAL_GET("gui/common/drag_threshold"));
	root->set_use_oversampling(GLOBAL_GET("gui/fonts/dynamic_fonts/use_oversampling"));
	root->set_default_canvas_item_texture_filter(Viewport::DefaultCanvasItemTextureFilter(int(GLOBAL_GET("rendering/textures/canvas_textures/default_texture_filter"))));
	root->set_default_canvas_item_texture_repeat(Viewport::DefaultCanvasItemTextureRepeat(int(GLOBAL_GET("rendering/textures/canvas_textures/default_texture_repeat"))));
	root->set_embedding_subwindows(true);
	tree->set_auto_accept_quit(false);
	tree->set_quit_on_go_back(false);
	tree->set_pause(false);
}

static BOOL PDReject(NSError **error, NSString *message) {
	if (error) {
		*error = [NSError errorWithDomain:@"dev.partydeck.godot.ios-probe" code:1 userInfo:@{ NSLocalizedDescriptionKey: message }];
	}
	return NO;
}

static NSDictionary *PDObject(NSString *document, NSUInteger limit) {
	if (![document isKindOfClass:NSString.class] || document.length > limit) {
		return nil;
	}
	NSData *bytes = [document dataUsingEncoding:NSUTF8StringEncoding allowLossyConversion:NO];
	if (!bytes || !partydeck::ios_probe::StrictJson(std::string_view(static_cast<const char *>(bytes.bytes), bytes.length)).valid_object(limit)) {
		return nil;
	}
	id object = [NSJSONSerialization JSONObjectWithData:bytes options:0 error:nil];
	return [object isKindOfClass:NSDictionary.class] ? object : nil;
}

static BOOL PDKeys(NSDictionary *object, NSArray<NSString *> *keys) {
	return [object isKindOfClass:NSDictionary.class] && [[NSSet setWithArray:object.allKeys] isEqualToSet:[NSSet setWithArray:keys]];
}

static BOOL PDBoolean(id value) {
	return [value isKindOfClass:NSNumber.class] && CFGetTypeID((__bridge CFTypeRef)value) == CFBooleanGetTypeID();
}

static BOOL PDVersion(id value) {
	return [value isKindOfClass:NSNumber.class] && !PDBoolean(value) &&
			!CFNumberIsFloatType((__bridge CFNumberRef)value) && [value longLongValue] == 1;
}

static BOOL PDIdentifier(id value, NSUInteger maximum) {
	return [value isKindOfClass:NSString.class] && [value length] <= maximum &&
			[[value stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet] length] > 0 &&
			[value rangeOfCharacterFromSet:NSCharacterSet.controlCharacterSet].location == NSNotFound;
}

static BOOL PDCounter(id value) {
	if (![value isKindOfClass:NSString.class] || [value length] == 0 || [value length] > 19) {
		return NO;
	}
	NSString *string = value;
	if (string.length > 1 && [string characterAtIndex:0] == '0') {
		return NO;
	}
	for (NSUInteger index = 0; index < string.length; ++index) {
		unichar character = [string characterAtIndex:index];
		if (character < '0' || character > '9') {
			return NO;
		}
	}
	return string.length < 19 || [string compare:@"9223372036854775807" options:NSLiteralSearch] != NSOrderedDescending;
}

static NSComparisonResult PDCompareCounter(NSString *left, NSString *right) {
	if (left.length != right.length) {
		return left.length < right.length ? NSOrderedAscending : NSOrderedDescending;
	}
	return [left compare:right options:NSLiteralSearch];
}

static BOOL PDPayload(NSDictionary *payload) {
	if (!PDKeys(payload, @[ @"game", @"controls" ]) || ![payload[@"game"] isKindOfClass:NSDictionary.class]) {
		return NO;
	}
	NSDictionary *controls = payload[@"controls"];
	if (!PDKeys(controls, @[ @"isHost", @"canSendAction", @"canAdvanceRound", @"canReturnToLobby" ])) {
		return NO;
	}
	for (id value in controls.allValues) {
		if (!PDBoolean(value)) {
			return NO;
		}
	}
	return YES;
}

static BOOL PDLaunch(NSDictionary *object) {
	if (!PDKeys(object, @[ @"protocolVersion", @"type", @"gameId", @"presentationId", @"presentationMode", @"revision", @"schemaId", @"payload", @"preferences" ]) ||
			!PDVersion(object[@"protocolVersion"]) || ![object[@"type"] isEqual:@"launch"] || ![object[@"gameId"] isEqual:@"last-light"] ||
			!PDIdentifier(object[@"presentationId"], 128) || ![@[ @"2d", @"3d" ] containsObject:object[@"presentationMode"]] ||
			!PDCounter(object[@"revision"]) || ![object[@"schemaId"] isEqual:@"last-light-view-v1"] || !PDPayload(object[@"payload"])) {
		return NO;
	}
	NSDictionary *preferences = object[@"preferences"];
	if (!PDKeys(preferences, @[ @"reduceMotion", @"soundEnabled", @"textScale" ]) || !PDBoolean(preferences[@"reduceMotion"]) || !PDBoolean(preferences[@"soundEnabled"])) {
		return NO;
	}
	id scale = preferences[@"textScale"];
	return [scale isKindOfClass:NSNumber.class] && !PDBoolean(scale) && std::isfinite([scale doubleValue]) && [scale doubleValue] >= 1 && [scale doubleValue] <= 2;
}

static BOOL PDIntent(NSDictionary *object) {
	if (!PDKeys(object, @[ @"protocolVersion", @"type", @"presentationId", @"sequence", @"expectedRevision", @"schemaId", @"payload" ]) ||
			!PDCounter(object[@"expectedRevision"]) || ![object[@"schemaId"] isEqual:@"last-light-intent-v1"]) {
		return NO;
	}
	NSDictionary *payload = object[@"payload"];
	if (![payload isKindOfClass:NSDictionary.class]) {
		return NO;
	}
	if ([@[ @"challenge", @"advance_round", @"return_to_lobby" ] containsObject:payload[@"type"]]) {
		return PDKeys(payload, @[ @"type" ]);
	}
	if (![payload[@"type"] isEqual:@"play"] || !PDKeys(payload, @[ @"type", @"cardIds" ]) || ![payload[@"cardIds"] isKindOfClass:NSArray.class]) {
		return NO;
	}
	NSArray *cards = payload[@"cardIds"];
	if (cards.count < 1 || cards.count > 3 || [NSSet setWithArray:cards].count != cards.count) {
		return NO;
	}
	for (id card in cards) {
		if (!PDIdentifier(card, 64)) {
			return NO;
		}
	}
	return YES;
}

static BOOL PDNumberInRange(id value, double minimum, double maximum, BOOL integer) {
	if (![value isKindOfClass:NSNumber.class] || PDBoolean(value)) {
		return NO;
	}
	double number = [value doubleValue];
	return std::isfinite(number) && number >= minimum && number <= maximum && (!integer || number == std::floor(number));
}

static NSArray<NSNumber *> *PDDiagnosticRect(id value) {
	if (![value isKindOfClass:NSArray.class] || [value count] != 4) {
		return nil;
	}
	NSMutableArray<NSNumber *> *result = [NSMutableArray arrayWithCapacity:4];
	for (NSUInteger index = 0; index < 4; ++index) {
		if (!PDNumberInRange(value[index], index < 2 ? -32768 : 0, 32768, NO)) {
			return nil;
		}
		[result addObject:@([value[index] doubleValue])];
	}
	return result;
}

static NSDictionary *PDSanitizedDiagnostics(NSDictionary *value, NSString *presentationID, NSString *mode) {
	if (!PDKeys(value, @[ @"schemaVersion", @"requestId", @"sequence", @"presentationId", @"revision", @"presentationMode",
			@"coordinateSpace", @"foreground", @"sceneStateApplied", @"viewport", @"handConcealed", @"selectedCount", @"privateFaceCount", @"privateLabelCount", @"controls" ]) ||
			!PDVersion(value[@"schemaVersion"]) || ![value[@"presentationId"] isEqual:presentationID] || ![value[@"presentationMode"] isEqual:mode] ||
			![value[@"coordinateSpace"] isEqual:@"root_viewport"] || !PDCounter(value[@"requestId"]) || !PDCounter(value[@"sequence"]) || !PDCounter(value[@"revision"]) ||
			!PDBoolean(value[@"foreground"]) || !PDBoolean(value[@"sceneStateApplied"]) || !PDBoolean(value[@"handConcealed"]) ||
			!PDNumberInRange(value[@"selectedCount"], 0, 3, YES) || !PDNumberInRange(value[@"privateFaceCount"], 0, 30, YES) ||
			!PDNumberInRange(value[@"privateLabelCount"], 0, 60, YES)) {
		return nil;
	}
	NSDictionary *viewport = value[@"viewport"];
	NSArray *controls = value[@"controls"];
	if (!PDKeys(viewport, @[ @"width", @"height" ]) || !PDNumberInRange(viewport[@"width"], 1, 32768, NO) ||
			!PDNumberInRange(viewport[@"height"], 1, 32768, NO) || ![controls isKindOfClass:NSArray.class] || controls.count > 32) {
		return nil;
	}
	NSArray<NSString *> *groups = @[ @"partydeck_action_reveal", @"partydeck_action_hide", @"partydeck_action_play",
		@"partydeck_action_challenge", @"partydeck_action_next_round", @"partydeck_action_lobby", @"partydeck_action_exit",
		@"partydeck_action_lobby_confirm", @"partydeck_action_lobby_cancel", @"partydeck_hand_card" ];
	NSMutableArray *safeControls = [NSMutableArray arrayWithCapacity:controls.count];
	for (NSDictionary *control in controls) {
		if (!PDKeys(control, @[ @"group", @"cardIndex", @"rect", @"clipRect", @"visible", @"enabled", @"selected" ]) ||
				![groups containsObject:control[@"group"]] || !PDNumberInRange(control[@"cardIndex"], -1, 4, YES) ||
				!PDBoolean(control[@"visible"]) || !PDBoolean(control[@"enabled"]) || !PDBoolean(control[@"selected"])) {
			return nil;
		}
		NSArray *rect = PDDiagnosticRect(control[@"rect"]);
		NSArray *clip = PDDiagnosticRect(control[@"clipRect"]);
		if (!rect || !clip) {
			return nil;
		}
		[safeControls addObject:@{ @"group": control[@"group"], @"cardIndex": @([control[@"cardIndex"] intValue]),
			@"rect": rect, @"clipRect": clip, @"visible": control[@"visible"], @"enabled": control[@"enabled"], @"selected": control[@"selected"] }];
	}
	// Copy only the fixed diagnostic schema. No arbitrary renderer string, card
	// value, or state document can enter the native receipt through this channel.
	return @{ @"schemaVersion": @1, @"requestId": value[@"requestId"], @"sequence": value[@"sequence"],
		@"presentationId": presentationID, @"revision": value[@"revision"], @"presentationMode": mode,
		@"coordinateSpace": @"root_viewport", @"foreground": value[@"foreground"], @"sceneStateApplied": value[@"sceneStateApplied"],
		@"handConcealed": value[@"handConcealed"],
		@"viewport": @{ @"width": @([viewport[@"width"] doubleValue]), @"height": @([viewport[@"height"] doubleValue]) },
		@"selectedCount": @([value[@"selectedCount"] intValue]), @"privateFaceCount": @([value[@"privateFaceCount"] intValue]),
		@"privateLabelCount": @([value[@"privateLabelCount"] intValue]), @"controls": safeControls };
}

@class PDGodotHostViewController;
@class PDGodotContainerViewController;
@class PDGuardedGodotView;

@interface PDGodotEngineOwner ()
- (void)presentationFinished:(NSDictionary *)snapshot;
- (BOOL)isCurrentPresentation:(PDGodotPresentation *)presentation;
- (PDGodotRuntime *)ownedRuntime;
- (void)invalidatePresentationForFailure:(BOOL)failure;
- (void)reportLifecycleGeneration:(uint64_t)generation foreground:(BOOL)foreground backgrounded:(BOOL)backgrounded;
@end

@interface PDGodotPresentation ()
@property(nonatomic, weak) PDGodotEngineOwner *owner;
@property(nonatomic, readwrite, copy) NSString *presentationID;
@property(nonatomic, readwrite) uint64_t nativeGeneration;
@property(nonatomic, readwrite, nullable) UIViewController *viewController;
@property(nonatomic, strong) NSDictionary *closedSnapshot;
@property(nonatomic) BOOL invalidated;
@property(nonatomic, copy, nullable) void (^closeCompletion)(BOOL dormant);
@end

@interface PDNativeDelivery : NSObject
@property(nonatomic, copy, nullable) NSString *document;
@property(nonatomic) uint64_t lifecycleGeneration;
@property(nonatomic) BOOL confirmReady;
@property(nonatomic, copy, nullable) void (^completion)(BOOL delivered);
@end

@implementation PDNativeDelivery
@end

@interface PDGodotRuntime () {
	PDGodotContainerViewController *_container;
	PDGodotHostViewController *_godotController;
	UIView *_privacyCover;
	__weak PDGuardedGodotView *_observedView;
	__weak PDGodotHostViewController *_observedController;
	NSString *_projectPath, *_packPath, *_launchDocument, *_presentationID, *_presentationMode, *_revision, *_lastSequence;
	NSString *_diagnosticsRequest, *_lastDiagnosticsSequence;
	NSDictionary *_rendererDiagnostics;
	NSString *_state, *_failure, *_renderingLayerClass;
	NSMutableArray<PDNativeDelivery *> *_commands;
	NSMutableArray<PDNativeDelivery *> *_cancelledDeliveries;
	NSMutableArray<NSDictionary<NSString *, id> *> *_events;
	NSUInteger _queuedBytes, _drawDepth, _engineDepth, _deliveryDepth, _drawCalls, _iterations;
	PDNativeTimings _nativeTimings;
	NSUInteger _cleanupCount, _cleanupDepth, _readyEvents, _exitEvents, _intentEvents, _rejectedEvents;
	NSUInteger _backgroundTransitions, _closeDuringDraw, _closeDuringInitialization, _coverUntilIteration, _privacyCoverCount;
	NSUInteger _foregroundGeneration;
	NSUInteger _presentedFrames, _failedPresentations;
	int64_t _diagnosticsRequests;
	NSUInteger _acceptedDiagnostics, _rejectedDiagnostics, _unansweredDiagnostics;
	double _displayScale;
	int _bootstrapExitCode, _setup2ErrorCode, _mainStartExitCode;
	BOOL _prepared, _bootstrapAttempted, _bootstrapSucceeded, _setup2Succeeded, _started;
	BOOL _foreground, _appliedForeground, _lifecycleApplied, _closeRequested, _closed, _quarantined;
	BOOL _drainScheduled, _eventTerminal, _readySeen, _closeOnNextDraw, _pendingForegroundLoss, _closeAfterSetup;
	BOOL _concealFramePending;
	BOOL _surfaceLayoutRequested;
	NSUInteger _concealAfterIteration;
	BOOL _idleTimerPolicyCaptured, _idleTimerPolicyRestored, _previousIdleTimerDisabled, _idleTimerDisabledAfterSetup;
	// These fields are used only by PDGodotEngineOwner. The public one-shot
	// runtime keeps its terminal close contract and the original probe suite.
	__weak PDGodotEngineOwner *_retainedOwner;
	BOOL _retainedPolicy, _presentationActive, _leaveRequested, _dormant, _emptyTree;
	BOOL _applicationActive, _applicationBackgrounded, _requestedForeground, _audioInterrupted, _maintenanceCompleted;
	BOOL _oldSceneObjectsAbsent, _audioQuiescenceObserved, _neutralFramePresented;
	BOOL _authorityReadyConfirmed;
	BOOL _authorityForeground;
	BOOL _lifecycleAnnounced, _announcedForeground, _announcedBackgrounded;
	NSString *_maintenance, *_fixedPackSHA256;
	id _audioInterruptionObserver;
	uint64_t _interruptionObserverGeneration;
	EAGLContext *_retainedContext;
	uint64_t _presentationGeneration, _lifecycleGeneration;
	NSUInteger _presentationCount, _suspensionCount, _maintenanceStartIteration, _emptyFrames;
	NSUInteger _warmupFrames, _neutralFrames, _retiredNodeCount, _retirementDepth;
	NSUInteger _concealedDiagnosticIteration;
	NSUInteger _lastStateMutationIteration, _concealedSampleAttempts;
	NSUInteger _audioInterruptions, _ignoredInterruptionCallbacks;
	NSTimeInterval _dormantObservationStarted;
	std::vector<ObjectID> _retiringObjects;
	ObjectID _previousTreeID, _previousSceneID, _presentationSceneID;
	AudioDriverCoreAudio::PartyDeckOutputState _audioObservationStart;
	AudioDriverCoreAudio::PartyDeckRetirement _audioRetirement;
	int _audioRetirementError;
}
- (void)startInContainer;
- (void)startFromContainer:(PDGodotContainerViewController *)container;
- (BOOL)canDraw;
- (BOOL)canReceiveInput;
- (PDNativeTimings *)nativeTimings;
- (void)beginDraw;
- (void)endDrawPresented:(BOOL)presented;
- (void)requestSurfaceLayout;
- (BOOL)hasCurrentRenderContext;
- (BOOL)establishRenderContext;
- (BOOL)applicationAllowsGraphics;
- (BOOL)applicationIsBackgrounded;
- (BOOL)requiresFreshFrame;
- (void)failNativePresentation;
- (BOOL)hasConcealedCurrentDiagnostics;
- (void)iterate;
- (NSString *)launchDocument;
- (BOOL)receiveRendererDocument:(NSString *)document;
- (BOOL)receiveRendererDiagnostics:(NSString *)document;
- (void)scheduleDrain;
- (void)drain;
- (BOOL)emitCommand:(NSDictionary *)command;
- (void)coverPrivateSurface;
- (NSUInteger)inputGeneration;
- (uint64_t)lifecycleGeneration;
- (void)applyRendererForeground:(BOOL)foreground;
- (BOOL)applyPendingLifecycleForce:(BOOL)force;
- (BOOL)enqueueDocument:(NSString *)document lifecycleGeneration:(uint64_t)generation confirmReady:(BOOL)confirmReady
			 completion:(void (^)(BOOL delivered))completion error:(NSError **)error;
- (void)cancelQueuedDeliveries;
- (void)completeCancelledDeliveries;
- (void)completeDelivery:(PDNativeDelivery *)delivery success:(BOOL)success;
- (BOOL)usesRetainedPolicy;
- (BOOL)prepareRetainedWithProjectPath:(NSString *)projectPath packPath:(NSString *)packPath
						 launchDocument:(NSString *)launchDocument generation:(uint64_t)generation
								 owner:(PDGodotEngineOwner *)owner error:(NSError **)error;
- (BOOL)acceptsGeneration:(uint64_t)generation;
- (BOOL)confirmRetainedReady;
- (void)leavePresentation;
- (void)setApplicationActive:(BOOL)active;
- (void)setApplicationActive:(BOOL)active backgrounded:(BOOL)backgrounded;
- (void)drainRetainedLeave;
- (void)finishDormantObservation:(uint64_t)generation;
- (void)quarantineRetained:(NSString *)reason;
- (void)installRetainedScene;
- (void)beginMaintenance:(NSString *)kind;
- (void)removeAudioInterruptionObserver;
- (void)installAudioInterruptionObserver;
- (NSDictionary *)retainedSnapshot;
@end

// drawView is implemented, but not publicly declared, in the exact GDTView
// source inspected by source_audit.py. This declaration records that coupling.
@interface GDTView (PDInspectedPrivateDrawSelector)
- (void)drawView;
- (void)clearTouches;
- (CMMotionManager *)motionManager;
- (CADisplayLink *)displayLink;
- (void)layoutRenderingLayer;
- (void)handleMotion;
@end

@interface GDTViewController (PDInspectedKeyboardSetup)
- (void)observeKeyboard;
@end

// Exact private framebuffer helpers in the pinned iOS layer implementation.
// Owning context setup here avoids the unchecked assignment in layer layout.
@interface GDTOpenGLLayer (PDInspectedFramebufferSelectors)
- (BOOL)createFramebuffer;
- (void)destroyFramebuffer;
@end

@interface PDGuardedGodotView : GDTViewIOS
@property(nonatomic, weak) PDGodotRuntime *runtime;
@property(nonatomic, strong) NSMapTable<UITouch *, NSNumber *> *acceptedTouches;
@property(nonatomic) BOOL nativeDelegateFinishedSetup;
@property(nonatomic) CGFloat lastNativeEDRHeadroom;
- (BOOL)performGuardedLayout;
@end

@implementation PDGuardedGodotView
- (void)drawView {
	PDGodotRuntime *runtime = self.runtime;
	if (!self.isActive || ![runtime canDraw]) {
		return;
	}
	PDNativeTimings *timings = [runtime nativeTimings];
	PDNativeTimingScope drawTiming(timings->draw_view);
	[runtime beginDraw];
	// Upstream pumps UIKit before touching its layer, but never rechecks app
	// activity afterward. Own that exact boundary so a Home/close handled in
	// the nested loop cannot reach an FBO bind or buffer presentation.
	if (self.useCADisplayLink) {
		PDNativeTimingScope pumpTiming(timings->uikit_pump);
		[self.displayLink setPaused:YES];
		while (CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.0, TRUE) == kCFRunLoopRunHandledSource) {}
		[self.displayLink setPaused:NO];
	}
	BOOL presented = NO;
	if (self.isActive && [runtime canDraw] && self.renderingLayer && self.renderer) {
		GLint attachmentType = 0, colorRenderbuffer = 0;
		if ([runtime establishRenderContext] && GLES3::TextureStorage::system_fbo != 0) {
			// The actual layer's createFramebuffer publishes this FBO. Avoid
			// upstream startRenderDisplayLayer's unchecked context assignment.
			glBindFramebuffer(GL_FRAMEBUFFER, GLES3::TextureStorage::system_fbo);
			glGetFramebufferAttachmentParameteriv(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE, &attachmentType);
			glGetFramebufferAttachmentParameteriv(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME, &colorRenderbuffer);
		}
		BOOL validDrawable = attachmentType == GL_RENDERBUFFER && colorRenderbuffer > 0 &&
				glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE && glGetError() == GL_NO_ERROR;
		if (!validDrawable) { [runtime failNativePresentation]; }
		BOOL setupPending = YES;
		if (validDrawable) {
			PDNativeTimingScope setupTiming(timings->setup_view);
			setupPending = [self.renderer setupView:self];
		}
		if (validDrawable && !setupPending) {
			if (self.delegate && !self.nativeDelegateFinishedSetup) {
				[self layoutRenderingLayer];
				self.nativeDelegateFinishedSetup = [self.delegate godotViewFinishedSetup:self];
			}
			if ((!self.delegate || self.nativeDelegateFinishedSetup) && [runtime canDraw]) {
				[self handleMotion];
				if (@available(iOS 16.0, *)) {
					CGFloat headroom = UIScreen.mainScreen.currentEDRHeadroom;
					if (headroom != self.lastNativeEDRHeadroom) {
						self.lastNativeEDRHeadroom = headroom;
						if (DisplayServerAppleEmbedded::get_singleton()) {
							DisplayServerAppleEmbedded::get_singleton()->current_edr_headroom_changed();
						}
					}
				}
				uint64_t framesBefore = Engine::get_singleton()->get_frames_drawn();
				{
					PDNativeTimingScope renderTiming(timings->render_on_view);
					[self.renderer renderOnView:self];
				}
				if (self.isActive && [runtime canDraw]) {
					// Upstream discards presentRenderbuffer's BOOL. Present this
					// actual layer attachment once, and observe its result directly.
					BOOL drew = Engine::get_singleton()->get_frames_drawn() > framesBefore;
					if (drew && [runtime hasCurrentRenderContext]) {
						glBindRenderbuffer(GL_RENDERBUFFER, static_cast<GLuint>(colorRenderbuffer));
						{
							PDNativeTimingScope presentTiming(timings->present_renderbuffer);
							presented = [EAGLContext.currentContext presentRenderbuffer:GL_RENDERBUFFER] && glGetError() == GL_NO_ERROR;
						}
					}
					if ((drew || [runtime requiresFreshFrame]) && !presented) { [runtime failNativePresentation]; }
				}
			}
		}
	}
	[runtime endDrawPresented:presented];
}
- (void)startRendering {
	if ([self.runtime canDraw]) {
		[super startRendering];
	}
}
- (void)stopRendering {
	[self.acceptedTouches removeAllObjects];
	[super stopRendering];
	[self clearTouches];
}
- (void)layoutRenderingLayer {
	[self.runtime requestSurfaceLayout];
}
- (BOOL)performGuardedLayout {
	if (![self.runtime establishRenderContext] || ![self.renderingLayer isKindOfClass:GDTOpenGLLayer.class]) { return NO; }
	GDTOpenGLLayer *layer = (GDTOpenGLLayer *)self.renderingLayer;
	layer.frame = self.bounds;
	[layer destroyFramebuffer];
	if (![layer createFramebuffer] || glGetError() != GL_NO_ERROR) { return NO; }
	if (DisplayServerAppleEmbedded::get_singleton()) {
		DisplayServerAppleEmbedded::get_singleton()->resize_window(self.bounds.size);
	}
	return YES;
}
- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
	if ([self.runtime canReceiveInput]) {
		if (!self.acceptedTouches) { self.acceptedTouches = [NSMapTable weakToStrongObjectsMapTable]; }
		for (UITouch *touch in touches) {
			[self.acceptedTouches setObject:@([self.runtime inputGeneration]) forKey:touch];
		}
		[super touchesBegan:touches withEvent:event];
	}
}
- (NSSet<UITouch *> *)acceptedTouchesFrom:(NSSet<UITouch *> *)touches ending:(BOOL)ending {
	NSMutableSet<UITouch *> *accepted = [NSMutableSet new];
	for (UITouch *touch in touches) {
		NSNumber *generation = [self.acceptedTouches objectForKey:touch];
		if (generation && [self.runtime canReceiveInput] && generation.unsignedIntegerValue == [self.runtime inputGeneration]) {
			[accepted addObject:touch];
		}
		if (ending) { [self.acceptedTouches removeObjectForKey:touch]; }
	}
	return accepted;
}
- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
	NSSet *accepted = [self acceptedTouchesFrom:touches ending:NO];
	if (accepted.count) { [super touchesMoved:accepted withEvent:event]; }
}
- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
	NSSet *accepted = [self acceptedTouchesFrom:touches ending:YES];
	if (accepted.count) { [super touchesEnded:accepted withEvent:event]; }
}
- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
	NSSet *accepted = [self acceptedTouchesFrom:touches ending:YES];
	if (accepted.count) { [super touchesCancelled:accepted withEvent:event]; }
	[self.acceptedTouches removeAllObjects];
}
@end

@interface PDGodotViewRenderer : GDTViewRenderer
@property(nonatomic, weak) PDGodotRuntime *runtime;
@end

@implementation PDGodotViewRenderer
- (BOOL)hasFinishedSetup { return [self.runtime canDraw]; }
- (BOOL)setupView:(UIView *)view { return ![self.runtime canDraw]; }
- (void)renderOnView:(UIView *)view { [self.runtime iterate]; }
@end

@interface PDGodotHostViewController : GDTViewController <GDTViewDelegate>
@property(nonatomic, weak) PDGodotRuntime *runtime;
@property(nonatomic, strong) PDGodotViewRenderer *probeRenderer;
@property(nonatomic, strong) NSMapTable<UIPress *, NSNumber *> *acceptedPresses;
- (void)invalidateInput;
@end

@implementation PDGodotHostViewController
- (void)loadView {
	PDGuardedGodotView *view = [[PDGuardedGodotView alloc] initWithFrame:CGRectZero];
	view.runtime = self.runtime;
	self.probeRenderer = [PDGodotViewRenderer new];
	self.probeRenderer.runtime = self.runtime;
	view.renderer = self.probeRenderer;
	view.delegate = self;
	self.view = view;
}
- (BOOL)godotViewFinishedSetup:(GDTView *)view { return YES; }
- (void)observeKeyboard {
	// This fixed game has no text-entry controls. Do not install the upstream
	// software-keyboard view and its independent input/notification producers.
}
- (void)invalidateInput { [self.acceptedPresses removeAllObjects]; }
- (void)pressesBegan:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event {
	if (![self.runtime canReceiveInput]) { return; }
	if (!self.acceptedPresses) { self.acceptedPresses = [NSMapTable weakToStrongObjectsMapTable]; }
	for (UIPress *press in presses) {
		[self.acceptedPresses setObject:@([self.runtime inputGeneration]) forKey:press];
	}
	[super pressesBegan:presses withEvent:event];
}
- (NSSet<UIPress *> *)acceptedPressesFrom:(NSSet<UIPress *> *)presses ending:(BOOL)ending {
	NSMutableSet<UIPress *> *accepted = [NSMutableSet new];
	for (UIPress *press in presses) {
		NSNumber *generation = [self.acceptedPresses objectForKey:press];
		if (generation && [self.runtime canReceiveInput] && generation.unsignedIntegerValue == [self.runtime inputGeneration]) {
			[accepted addObject:press];
		}
		if (ending) { [self.acceptedPresses removeObjectForKey:press]; }
	}
	return accepted;
}
- (void)pressesChanged:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event {
	NSSet *accepted = [self acceptedPressesFrom:presses ending:NO];
	if (accepted.count) { [super pressesChanged:accepted withEvent:event]; }
}
- (void)pressesEnded:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event {
	NSSet *accepted = [self acceptedPressesFrom:presses ending:YES];
	if (accepted.count) { [super pressesEnded:accepted withEvent:event]; }
}
- (void)pressesCancelled:(NSSet<UIPress *> *)presses withEvent:(UIPressesEvent *)event {
	NSSet *accepted = [self acceptedPressesFrom:presses ending:YES];
	if (accepted.count) { [super pressesEnded:accepted withEvent:event]; }
}
- (void)propagateUIPreferencesToRootViewController {
	// Upstream mutates the root controller's class. The application owns its UI.
}
- (BOOL)prefersStatusBarHidden { return NO; }
- (BOOL)prefersHomeIndicatorAutoHidden { return NO; }
- (UIRectEdge)preferredScreenEdgesDeferringSystemGestures { return UIRectEdgeNone; }
- (BOOL)shouldAutorotate { return YES; }
- (UIInterfaceOrientationMask)supportedInterfaceOrientations { return UIInterfaceOrientationMaskAllButUpsideDown; }
@end

@interface PDGodotContainerViewController : UIViewController
@property(nonatomic, weak) PDGodotRuntime *runtime;
@end

@implementation PDGodotContainerViewController
- (void)viewDidLoad {
	[super viewDidLoad];
	self.view.backgroundColor = [UIColor colorWithRed:0.07 green:0.11 blue:0.10 alpha:1];
	self.view.accessibilityIdentifier = @"godot-surface";
	self.view.isAccessibilityElement = YES;
	self.view.accessibilityLabel = @"Godot diagnostic rendering surface";
}
- (void)viewDidAppear:(BOOL)animated {
	[super viewDidAppear:animated];
	[self.runtime startFromContainer:self];
}
@end

class PartyDeckBridge : public Object {
	GDCLASS(PartyDeckBridge, Object);

protected:
	static void _bind_methods() {
		ClassDB::bind_method(D_METHOD("get_launch_document"), &PartyDeckBridge::get_launch_document);
		ClassDB::bind_method(D_METHOD("renderer_event", "document"), &PartyDeckBridge::renderer_event);
		ClassDB::bind_method(D_METHOD("get_display_scale"), &PartyDeckBridge::get_display_scale);
		ClassDB::bind_method(D_METHOD("renderer_diagnostics", "document"), &PartyDeckBridge::renderer_diagnostics);
		ADD_SIGNAL(MethodInfo("command_received", PropertyInfo(Variant::STRING, "document")));
		ADD_SIGNAL(MethodInfo("diagnostics_requested", PropertyInfo(Variant::STRING, "request_id")));
	}

public:
	String get_launch_document() const {
		if (!NSThread.isMainThread || !activeRuntime) {
			return String();
		}
		NSString *document = [activeRuntime launchDocument];
		return document ? String::utf8(document.UTF8String) : String();
	}
	bool renderer_event(const String &document) {
		if (!NSThread.isMainThread || document.length() > PDEventLimit || !activeRuntime) {
			return false;
		}
		CharString bytes = document.utf8();
		if (bytes.length() > PDEventLimit) {
			return false;
		}
		NSString *native = [[NSString alloc] initWithBytes:bytes.get_data() length:bytes.length() encoding:NSUTF8StringEncoding];
		return native && [activeRuntime receiveRendererDocument:native];
	}
	double get_display_scale() const {
		if (!NSThread.isMainThread || !activeRuntime || !DisplayServer::get_singleton()) {
			return 0;
		}
		return DisplayServer::get_singleton()->screen_get_max_scale();
	}
	bool renderer_diagnostics(const String &document) {
		if (!NSThread.isMainThread || !activeRuntime || document.length() > PDDiagnosticsLimit) {
			return false;
		}
		CharString bytes = document.utf8();
		if (bytes.length() > PDDiagnosticsLimit) {
			return false;
		}
		NSString *native = [[NSString alloc] initWithBytes:bytes.get_data() length:bytes.length() encoding:NSUTF8StringEncoding];
		return native && [activeRuntime receiveRendererDiagnostics:native];
	}
};

static PartyDeckBridge *bridge = nullptr;

void initialize_partydeck_ios_probe_module(ModuleInitializationLevel level) {
	if (level == MODULE_INITIALIZATION_LEVEL_SCENE) {
		GDREGISTER_CLASS(PartyDeckBridge);
		bridge = memnew(PartyDeckBridge);
		Engine::get_singleton()->add_singleton(Engine::Singleton("PartyDeckBridge", bridge));
	}
}

void uninitialize_partydeck_ios_probe_module(ModuleInitializationLevel level) {
	if (level == MODULE_INITIALIZATION_LEVEL_SCENE && bridge) {
		Engine::get_singleton()->remove_singleton("PartyDeckBridge");
		memdelete(bridge);
		bridge = nullptr;
	}
}

@implementation PDGodotRuntime
- (PDNativeTimings *)nativeTimings { return &_nativeTimings; }

- (instancetype)init {
	self = [super init];
	if (self) {
		_state = @"idle";
		_foreground = YES;
		_requestedForeground = YES;
		_applicationActive = UIApplication.sharedApplication.applicationState == UIApplicationStateActive;
		_applicationBackgrounded = UIApplication.sharedApplication.applicationState == UIApplicationStateBackground;
		_audioRetirementError = -1;
		_bootstrapExitCode = _setup2ErrorCode = _mainStartExitCode = -1;
		_commands = [NSMutableArray new];
		_cancelledDeliveries = [NSMutableArray new];
		_events = [NSMutableArray new];
	}
	return self;
}

- (UIViewController *)viewController { return _container; }
- (NSUInteger)inputGeneration { return _foregroundGeneration; }
- (uint64_t)lifecycleGeneration { return _lifecycleGeneration; }
- (BOOL)usesRetainedPolicy { return _retainedPolicy; }

- (BOOL)acceptsGeneration:(uint64_t)generation {
	return NSThread.isMainThread && _retainedPolicy && _presentationActive && !_leaveRequested && !_closeRequested &&
			!_closed && !_quarantined && generation == _presentationGeneration;
}

- (BOOL)prepareRetainedWithProjectPath:(NSString *)projectPath packPath:(NSString *)packPath
						 launchDocument:(NSString *)launchDocument generation:(uint64_t)generation
								 owner:(PDGodotEngineOwner *)owner error:(NSError **)error {
	if (!NSThread.isMainThread || _closed || _closeRequested || _quarantined || _presentationActive || _leaveRequested ||
			(_prepared && !_dormant) || generation == 0 || generation <= _presentationGeneration) {
		return PDReject(error, @"The retained engine cannot accept another presentation in its current state.");
	}
	if (PDSDLEnabled) { return PDReject(error, @"Retained qualification requires the audited touch/keyboard-only sdl=no build."); }
	NSString *project = projectPath.stringByResolvingSymlinksInPath;
	NSString *pack = packPath.stringByResolvingSymlinksInPath;
	NSString *bundle = NSBundle.mainBundle.resourcePath.stringByResolvingSymlinksInPath;
	NSString *hash = PDPackSHA256(pack);
	if (![project isEqual:bundle] || ![pack isEqual:[bundle stringByAppendingPathComponent:@"ProbeResources/partydeck-last-light.pck"]] ||
			![hash isEqual:PDQualifiedRetainedPackSHA256] || (_fixedPackSHA256 && ![_fixedPackSHA256 isEqual:hash]) ||
			(_projectPath && (![_projectPath isEqual:project] || ![_packPath isEqual:pack]))) {
		return PDReject(error, @"Retained entry requires the exact audited pack in the application bundle.");
	}
	NSDictionary *launch = PDObject(launchDocument, PDCommandLimit);
	if (!PDLaunch(launch)) { return PDReject(error, @"The new presentation launch envelope is invalid."); }
	if (!_prepared) {
		if (![self prepareWithProjectPath:project packPath:pack launchDocument:launchDocument error:error]) { return NO; }
	} else {
		if (!_started || !_emptyTree || _retainedOwner != owner || !OS::get_singleton() || !SceneTree::get_singleton() ||
				SceneTree::get_singleton()->get_node_count() != 1 || PDBridgeConnectionCount(bridge) != 0) {
			return PDReject(error, @"The previous presentation has not left a verified empty retained engine.");
		}
		_previousIdleTimerDisabled = UIApplication.sharedApplication.idleTimerDisabled;
		_idleTimerPolicyCaptured = YES;
		_idleTimerPolicyRestored = NO;
		_launchDocument = [launchDocument copy];
		_presentationID = [launch[@"presentationId"] copy];
		_presentationMode = [launch[@"presentationMode"] copy];
		_revision = [launch[@"revision"] copy];
		_container = [PDGodotContainerViewController new];
		_container.runtime = self;
		_state = @"prepared";
	}
	_retainedPolicy = YES;
	_retainedOwner = owner;
	_fixedPackSHA256 = hash;
	_presentationGeneration = generation;
	++_presentationCount;
	++_foregroundGeneration;
	++_lifecycleGeneration;
	_presentationActive = YES;
	_dormant = NO;
	_leaveRequested = NO;
	_requestedForeground = YES;
	_authorityForeground = YES;
	_foreground = [self applicationAllowsGraphics] && !_audioInterrupted;
	_appliedForeground = NO;
	_lifecycleApplied = NO;
	_pendingForegroundLoss = NO;
	_concealFramePending = NO;
	_readySeen = _eventTerminal = NO;
	_authorityReadyConfirmed = NO;
	_concealedSampleAttempts = 0;
	_lastStateMutationIteration = _iterations;
	_lifecycleAnnounced = YES;
	_announcedForeground = _requestedForeground && [self applicationAllowsGraphics] && !_audioInterrupted;
	_announcedBackgrounded = [self applicationIsBackgrounded];
	_readyEvents = _exitEvents = _intentEvents = _rejectedEvents = 0;
	_lastSequence = _lastDiagnosticsSequence = _diagnosticsRequest = nil;
	_rendererDiagnostics = nil;
	_diagnosticsRequests = _acceptedDiagnostics = _rejectedDiagnostics = _unansweredDiagnostics = 0;
	_presentationSceneID = ObjectID();
	_audioQuiescenceObserved = NO;
	_neutralFramePresented = NO;
	_audioRetirement = {};
	_audioRetirementError = -1;
	[self installAudioInterruptionObserver];
	return YES;
}

- (BOOL)prepareWithProjectPath:(NSString *)projectPath packPath:(NSString *)packPath launchDocument:(NSString *)launchDocument error:(NSError **)error {
	if (!NSThread.isMainThread) {
		return PDReject(error, @"The native owner must call on the main thread.");
	}
	if (_prepared || _closed || processConsumed) {
		return PDReject(error, @"A fresh process is required for another engine presentation.");
	}
	NSDictionary *launch = PDObject(launchDocument, PDCommandLimit);
	if (!PDLaunch(launch)) {
		return PDReject(error, @"The launch envelope is invalid or exceeds its byte limit.");
	}
	BOOL directory = NO;
	if (![NSFileManager.defaultManager fileExistsAtPath:projectPath isDirectory:&directory] || !directory ||
			(packPath && ![NSFileManager.defaultManager isReadableFileAtPath:packPath]) ||
			(!packPath && ![NSFileManager.defaultManager isReadableFileAtPath:[projectPath stringByAppendingPathComponent:@"project.godot"]])) {
		return PDReject(error, @"The bundled Godot project or pack is unavailable.");
	}
	// DisplayServerAppleEmbedded changes this UIKit policy during setup. The
	// shell's actual previous value belongs to this presentation's lifetime.
	_previousIdleTimerDisabled = UIApplication.sharedApplication.idleTimerDisabled;
	_idleTimerPolicyCaptured = YES;
	_prepared = YES;
	_projectPath = [projectPath copy];
	_packPath = [packPath copy];
	_launchDocument = [launchDocument copy];
	_presentationID = [launch[@"presentationId"] copy];
	_presentationMode = [launch[@"presentationMode"] copy];
	_revision = [launch[@"revision"] copy];
	_container = [PDGodotContainerViewController new];
	_container.runtime = self;
	_state = @"prepared";
	return YES;
}

- (void)startInContainer {
	if (![self applicationAllowsGraphics]) { return; }
	if (_retainedPolicy && (!_presentationActive || _leaveRequested)) { return; }
	if (_retainedPolicy && _bootstrapAttempted && _presentationActive && !_leaveRequested && !_closeRequested &&
			!_closed && !_quarantined && _emptyTree && !_maintenance && _foreground) {
		[_container addChildViewController:_godotController];
		_godotController.view.frame = _container.view.bounds;
		[_container.view addSubview:_godotController.view];
		[_godotController didMoveToParentViewController:_container];
		[self coverPrivateSurface];
		_observedView.userInteractionEnabled = YES;
		UIApplication.sharedApplication.idleTimerDisabled = _idleTimerDisabledAfterSetup;
		[self beginMaintenance:@"warming"];
		return;
	}
	if (_bootstrapAttempted || _closeRequested || _closed || !_prepared || !_foreground) {
		return;
	}
	if (processConsumed) {
		_failure = @"PROCESS_ALREADY_USED";
		[self close];
		return;
	}
	NSString *executable = NSBundle.mainBundle.executablePath;
	// Upstream change_to_launch_dir uses a fixed 512-byte path buffer; it
	// requires a slash in argv[0]. process_args has 64 slots. Our owned host
	// supplies an absolute executable and no Info.plist argument injection.
	if (!executable.isAbsolutePath || [executable lengthOfBytesUsingEncoding:NSUTF8StringEncoding] >= 512 ||
			NSBundle.mainBundle.infoDictionary[@"godot_cmdline"] != nil) {
		_failure = @"UNSUPPORTED_BOOTSTRAP_ARGUMENTS";
		[self close];
		return;
	}
	processConsumed = YES;
	++processBootstrapCount;
	_bootstrapAttempted = YES;
	activeRuntime = self;
	_state = @"initializing";
	++_engineDepth;
	std::vector<std::string> arguments = { executable.UTF8String, "--path", _projectPath.UTF8String, "--rendering-method", "gl_compatibility", "--rendering-driver", "opengl3" };
	if (_packPath) {
		arguments.push_back("--main-pack");
		arguments.push_back(_packPath.UTF8String);
	}
	std::vector<char *> argv;
	for (std::string &argument : arguments) {
		argv.push_back(argument.data());
	}
	_bootstrapExitCode = apple_embedded_main(static_cast<int>(argv.size()), argv.data());
	_bootstrapSucceeded = _bootstrapExitCode == EXIT_SUCCESS;
	if (_bootstrapSucceeded) {
		_godotController = [PDGodotHostViewController new];
		_godotController.runtime = self;
		_observedController = _godotController;
		GDTAppDelegateService.viewController = _godotController;
		[_container addChildViewController:_godotController];
		_godotController.view.frame = _container.view.bounds;
		_godotController.view.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
		[_container.view addSubview:_godotController.view];
		[_godotController didMoveToParentViewController:_container];
		_observedView = (PDGuardedGodotView *)_godotController.godotView;
		if (_retainedPolicy || !_foreground || _pendingForegroundLoss) {
			[self coverPrivateSurface];
		}
		// The actual setupProjectData stage, with its Error result checked.
		// The attached native surface exists before any display-server setup.
		_setup2ErrorCode = Main::setup2(false);
		_setup2Succeeded = _setup2ErrorCode == OK;
		if (_setup2Succeeded) { _retainedContext = EAGLContext.currentContext; }
		_displayScale = _setup2Succeeded && DisplayServer::get_singleton() ? DisplayServer::get_singleton()->screen_get_max_scale() : 0;
		_idleTimerDisabledAfterSetup = UIApplication.sharedApplication.idleTimerDisabled;
		if (_closeAfterSetup) {
			[self close];
		}
		if (_setup2Succeeded && !_closeRequested) {
			_mainStartExitCode = Main::start();
			if (_mainStartExitCode == EXIT_SUCCESS && OS::get_singleton()->get_main_loop()) {
				OS::get_singleton()->get_main_loop()->initialize();
				_started = YES;
				if (_retainedPolicy) {
					SceneTree *tree = SceneTree::get_singleton();
					if (tree && tree->get_current_scene()) {
						tree->set_auto_accept_quit(false);
						tree->set_quit_on_go_back(false);
						_presentationSceneID = tree->get_current_scene()->get_instance_id();
					}
					_coverUntilIteration = _iterations + 2;
				}
			}
		}
		_renderingLayerClass = NSStringFromClass(_observedView.renderingLayer.class);
	}
	--_engineDepth;
	if (!_bootstrapSucceeded || !_setup2Succeeded) {
		// cleanup() dereferences systems that may not yet exist. Stop the view
		// and quarantine the failed process; never guess that cleanup(true) is safe.
		_failure = @"INITIALIZATION_FAILED_BEFORE_SAFE_CLEANUP";
		_quarantined = YES;
		[self close];
	} else if (!_started && !_closeRequested) {
		_failure = @"MAIN_START_FAILED";
		[self close];
	} else if (_retainedPolicy && _started && !PDCoreAudioDriver()) {
		[self quarantineRetained:@"RETAINED_COREAUDIO_DRIVER_REQUIRED"];
	} else if (_retainedPolicy && _started && (!_retainedContext || !_presentationSceneID.is_valid())) {
		[self quarantineRetained:@"RETAINED_NATIVE_SURFACE_OR_SCENE_MISSING"];
	}
	[self scheduleDrain];
}

- (void)startFromContainer:(PDGodotContainerViewController *)container {
	if (container == _container) { [self startInContainer]; }
}

- (BOOL)canDraw {
	if (!_started || _closeRequested || _closed || _quarantined || _engineDepth != 0) { return NO; }
	if (![self applicationAllowsGraphics]) { return NO; }
	if (_retainedPolicy && _maintenance) {
		return _applicationActive && !_maintenanceCompleted && _emptyTree;
	}
	BOOL applicationActive = _retainedPolicy ? _applicationActive : UIApplication.sharedApplication.applicationState == UIApplicationStateActive;
	if (_concealFramePending && !_pendingForegroundLoss && _lifecycleApplied && !_appliedForeground && applicationActive &&
			(!_retainedPolicy || (_presentationActive && !_leaveRequested && !_emptyTree))) { return YES; }
	return _foreground && !_pendingForegroundLoss && (!_retainedPolicy || (_presentationActive && !_leaveRequested && !_dormant));
}
- (BOOL)canReceiveInput {
	return [self applicationAllowsGraphics] && _started && _foreground && _readySeen && _lifecycleApplied && _appliedForeground && !_pendingForegroundLoss &&
			!_privacyCover && !_closeRequested && !_closed && !_quarantined && DisplayServer::get_singleton() &&
			(!_retainedPolicy || (_presentationActive && !_leaveRequested && !_dormant && !_maintenance));
}
- (void)beginDraw {
	++_drawDepth;
	++_drawCalls;
	if (_closeOnNextDraw) {
		_closeOnNextDraw = NO;
		CFRunLoopPerformBlock(CFRunLoopGetMain(), kCFRunLoopDefaultMode, ^{
			[self close];
		});
		CFRunLoopWakeUp(CFRunLoopGetMain());
	}
}
- (void)endDrawPresented:(BOOL)presented {
	--_drawDepth;
	if (presented) { ++_presentedFrames; }
	if (presented && _concealFramePending && !_pendingForegroundLoss && _iterations > _concealAfterIteration) {
		_concealFramePending = NO;
		if (!_foreground) { [_observedView stopRendering]; }
	}
	if (presented && _retainedPolicy && _maintenance && _iterations > _maintenanceStartIteration) {
		_maintenanceCompleted = YES;
		++_emptyFrames;
		if ([_maintenance isEqual:@"warming"]) { ++_warmupFrames; } else { ++_neutralFrames; }
		[_observedView stopRendering];
		[self scheduleDrain];
		return;
	}
	// drawView has returned after presenting its layer. A resumed surface is
	// uncovered only after concealment commands and a subsequent real frame.
	BOOL retainedConcealed = !_retainedPolicy || (_presentationActive && !_leaveRequested && _readyEvents == 1 && _authorityReadyConfirmed &&
			[self hasConcealedCurrentDiagnostics] &&
			_iterations > _concealedDiagnosticIteration);
	if (presented && _privacyCover && _foreground && _appliedForeground && !_pendingForegroundLoss && !_closeRequested &&
			_iterations >= _coverUntilIteration && retainedConcealed) {
		[_privacyCover removeFromSuperview];
		_privacyCover = nil;
		_observedView.accessibilityElementsHidden = NO;
	}
	if (_closeRequested || _leaveRequested || _surfaceLayoutRequested || _events.count || _commands.count || _diagnosticsRequest || _pendingForegroundLoss || !_lifecycleApplied || _appliedForeground != _foreground ||
			(_retainedPolicy && _privacyCover && _foreground && _readySeen && ![self hasConcealedCurrentDiagnostics])) {
		[self scheduleDrain];
	}
}

- (void)requestSurfaceLayout {
	if (_closed || _quarantined || _closeRequested || _leaveRequested || (_retainedPolicy && !_presentationActive)) { return; }
	_surfaceLayoutRequested = YES;
	[self scheduleDrain];
}

- (BOOL)hasCurrentRenderContext {
	return _retainedContext && EAGLContext.currentContext == _retainedContext;
}

- (BOOL)establishRenderContext {
	return [self applicationAllowsGraphics] && _retainedContext && [EAGLContext setCurrentContext:_retainedContext] && [self hasCurrentRenderContext];
}

- (BOOL)applicationAllowsGraphics {
	return UIApplication.sharedApplication.applicationState == UIApplicationStateActive && (!_retainedPolicy || _applicationActive);
}

- (BOOL)applicationIsBackgrounded {
	return _applicationBackgrounded || UIApplication.sharedApplication.applicationState == UIApplicationStateBackground;
}

- (BOOL)requiresFreshFrame { return _privacyCover != nil || _maintenance != nil; }

- (void)failNativePresentation {
	++_failedPresentations;
	if (_retainedPolicy) { [self quarantineRetained:@"RETAINED_NATIVE_PRESENTATION_FAILED"]; }
	else { _failure = @"NATIVE_PRESENTATION_FAILED"; [self close]; }
}

- (BOOL)hasConcealedCurrentDiagnostics {
	return _rendererDiagnostics && [_rendererDiagnostics[@"sceneStateApplied"] boolValue] &&
			_concealedDiagnosticIteration > _lastStateMutationIteration &&
			[_rendererDiagnostics[@"handConcealed"] boolValue] && [_rendererDiagnostics[@"selectedCount"] intValue] == 0 &&
			[_rendererDiagnostics[@"privateFaceCount"] intValue] == 0 && [_rendererDiagnostics[@"privateLabelCount"] intValue] == 0 &&
			[_rendererDiagnostics[@"revision"] isEqual:_revision] && [_rendererDiagnostics[@"foreground"] boolValue];
}
- (void)iterate {
	if (![self canDraw]) {
		return;
	}
	++_engineDepth;
	if ([self requiresFreshFrame]) { Main::force_redraw(); }
	BOOL requestedQuit;
	{
		PDNativeTimingScope iterateTiming(_nativeTimings.iterate);
		requestedQuit = OS_AppleEmbedded::get_singleton()->iterate();
	}
	++_iterations;
	--_engineDepth;
	if (requestedQuit) {
		if (_retainedPolicy) { [self quarantineRetained:@"RETAINED_SCENE_REQUESTED_ENGINE_QUIT"]; }
		else { [self close]; }
	}
}
- (NSString *)launchDocument { return (_closeRequested || _leaveRequested || (_retainedPolicy && !_presentationActive)) ? nil : _launchDocument; }

- (BOOL)receiveRendererDocument:(NSString *)document {
	if (_closeRequested || _eventTerminal || _closed || _leaveRequested || (_retainedPolicy && !_presentationActive)) {
		return NO;
	}
	NSDictionary *event = PDObject(document, PDEventLimit);
	NSString *type = event[@"type"];
	BOOL valid = PDVersion(event[@"protocolVersion"]) && [event[@"presentationId"] isEqual:_presentationID] && PDCounter(event[@"sequence"]);
	if ([type isEqual:@"ready"] || [type isEqual:@"exit"]) {
		valid = valid && PDKeys(event, @[ @"protocolVersion", @"type", @"presentationId", @"sequence" ]);
	} else if ([type isEqual:@"failed"]) {
		valid = valid && PDKeys(event, @[ @"protocolVersion", @"type", @"presentationId", @"sequence", @"reason" ]) &&
				[@[ @"INITIALIZATION_FAILED", @"INVALID_PAYLOAD", @"RENDERER_LOST", @"INTERNAL_ERROR" ] containsObject:event[@"reason"]];
	} else if ([type isEqual:@"intent"]) {
		valid = valid && PDIntent(event);
	} else {
		valid = NO;
	}
	if (!valid || (_lastSequence && PDCompareCounter(event[@"sequence"], _lastSequence) != NSOrderedDescending) || ([type isEqual:@"ready"] && _readySeen)) {
		++_rejectedEvents;
		return NO;
	}
	_lastSequence = event[@"sequence"];
	if ([type isEqual:@"intent"] && (!_readySeen || !_foreground || _pendingForegroundLoss ||
			(_retainedPolicy && ![self canReceiveInput]) || ![event[@"expectedRevision"] isEqual:_revision])) {
		++_rejectedEvents;
		return NO;
	}
	if (_events.count >= PDQueueCountLimit) {
		_failure = @"EVENT_QUEUE_OVERFLOW";
		[self close];
		return NO;
	}
	_readySeen = _readySeen || [type isEqual:@"ready"];
	_eventTerminal = [type isEqual:@"exit"] || [type isEqual:@"failed"];
	[_events addObject:@{ @"document": document, @"foregroundGeneration": @(_foregroundGeneration) }];
	[self scheduleDrain];
	return YES;
}

- (BOOL)sendDocument:(NSString *)document error:(NSError **)error {
	return [self enqueueDocument:document lifecycleGeneration:_lifecycleGeneration confirmReady:NO completion:nil error:error];
}

- (BOOL)enqueueDocument:(NSString *)document lifecycleGeneration:(uint64_t)generation confirmReady:(BOOL)confirmReady
			 completion:(void (^)(BOOL))completion error:(NSError **)error {
	if (!NSThread.isMainThread || !_prepared || _closeRequested || _closed || _leaveRequested || (_retainedPolicy && !_presentationActive)) {
		return PDReject(error, @"The presentation is closed or not owned by the calling thread.");
	}
	if (_retainedPolicy && generation != _lifecycleGeneration) {
		return PDReject(error, @"The captured lifecycle generation is obsolete.");
	}
	NSDictionary *command = PDObject(document, PDCommandLimit);
	if (!PDVersion(command[@"protocolVersion"]) || ![command[@"presentationId"] isEqual:_presentationID]) {
		return PDReject(error, @"The command envelope is invalid.");
	}
	BOOL close = [command[@"type"] isEqual:@"close"] && PDKeys(command, @[ @"protocolVersion", @"type", @"presentationId" ]);
	BOOL foreground = [command[@"type"] isEqual:@"foreground"] && PDKeys(command, @[ @"protocolVersion", @"type", @"presentationId", @"isForeground" ]) && PDBoolean(command[@"isForeground"]);
	if (close && !completion) {
		if (_retainedPolicy) { [self leavePresentation]; } else { [self close]; }
		return YES;
	}
	if (foreground && !_retainedPolicy) {
		[self setForeground:[command[@"isForeground"] boolValue]];
		return YES;
	}
	BOOL view = [command[@"type"] isEqual:@"view"] && PDKeys(command, @[ @"protocolVersion", @"type", @"presentationId", @"revision", @"schemaId", @"payload" ]) &&
			PDCounter(command[@"revision"]) && PDCompareCounter(command[@"revision"], _revision) == NSOrderedDescending &&
			[command[@"schemaId"] isEqual:@"last-light-view-v1"] && PDPayload(command[@"payload"]);
	if (!close && !foreground && !view) {
		return PDReject(error, @"The command is malformed, stale, or unsupported.");
	}
	NSUInteger bytes = [document lengthOfBytesUsingEncoding:NSUTF8StringEncoding];
	if (_commands.count + _cancelledDeliveries.count >= PDQueueCountLimit || _queuedBytes + bytes > PDQueueByteLimit) {
		return PDReject(error, @"The bounded command queue is full.");
	}
	if (view) { _revision = command[@"revision"]; }
	_rendererDiagnostics = nil;
	_queuedBytes += bytes;
	PDNativeDelivery *delivery = [PDNativeDelivery new];
	delivery.document = document;
	delivery.lifecycleGeneration = generation;
	delivery.confirmReady = confirmReady;
	delivery.completion = completion;
	[_commands addObject:delivery];
	if (_retainedPolicy && (close || foreground)) {
		// Common's grant is separate from native lifecycle and cannot override
		// an application/interruption cover. It may enable covered bootstrap;
		// delivery and Ready confirmation still wait for the scene drain.
		_authorityForeground = !close && [command[@"isForeground"] boolValue];
		[self applyRendererForeground:_authorityForeground && _requestedForeground && [self applicationAllowsGraphics] && !_audioInterrupted];
		if (_foreground && (!_bootstrapAttempted || _emptyTree) && _container.viewIfLoaded.window) { [self startInContainer]; }
	}
	[self scheduleDrain];
	return YES;
}

- (void)completeDelivery:(PDNativeDelivery *)delivery success:(BOOL)success {
	void (^completion)(BOOL) = delivery.completion;
	delivery.completion = nil;
	delivery.document = nil;
	if (completion) {
		++_deliveryDepth;
		completion(success);
		--_deliveryDepth;
	}
}

- (void)cancelQueuedDeliveries {
	for (PDNativeDelivery *delivery in _commands) {
		delivery.document = nil;
		if (delivery.completion) { [_cancelledDeliveries addObject:delivery]; }
	}
	[_commands removeAllObjects];
	_queuedBytes = 0;
}

- (void)completeCancelledDeliveries {
	while (_cancelledDeliveries.count) {
		PDNativeDelivery *delivery = _cancelledDeliveries.firstObject;
		[_cancelledDeliveries removeObjectAtIndex:0];
		[self completeDelivery:delivery success:NO];
	}
}

- (void)setForeground:(BOOL)foreground {
	if (!NSThread.isMainThread || _closeRequested || _closed || _leaveRequested || (_retainedPolicy && !_presentationActive)) {
		return;
	}
	BOOL nativeForeground = foreground;
	BOOL lifecycleChanged = NO;
	if (_retainedPolicy) {
		_requestedForeground = foreground;
		nativeForeground = foreground && [self applicationAllowsGraphics] && !_audioInterrupted;
		lifecycleChanged = !_lifecycleAnnounced || nativeForeground != _announcedForeground || [self applicationIsBackgrounded] != _announcedBackgrounded;
		if (lifecycleChanged && _lifecycleAnnounced) { ++_lifecycleGeneration; ++_foregroundGeneration; }
		foreground = nativeForeground && _authorityForeground;
	}
	[self applyRendererForeground:foreground];
	if (lifecycleChanged) {
		_lifecycleAnnounced = YES;
		_announcedForeground = nativeForeground;
		_announcedBackgrounded = [self applicationIsBackgrounded];
		[_retainedOwner reportLifecycleGeneration:_lifecycleGeneration foreground:nativeForeground backgrounded:_announcedBackgrounded];
	}
	if ((!_bootstrapAttempted || (_retainedPolicy && _emptyTree)) && _foreground && _container.viewIfLoaded.window) {
		[self startInContainer];
	}
	[self scheduleDrain];
}

- (void)applyRendererForeground:(BOOL)foreground {
	if (_retainedPolicy && foreground == _foreground && _lifecycleApplied) { return; }
	if (_retainedPolicy && foreground != _foreground) { ++_foregroundGeneration; }
	_foreground = foreground;
	_rendererDiagnostics = nil;
	_lastStateMutationIteration = _iterations;
	_concealedSampleAttempts = 0;
	if (!foreground) {
		if (!_retainedPolicy) { ++_foregroundGeneration; }
		_pendingForegroundLoss = YES;
		_concealFramePending = YES;
		_coverUntilIteration = _iterations + 1;
		[self coverPrivateSurface];
		[_observedView stopRendering];
		[_godotController invalidateInput];
		if (_retainedPolicy) { [_observedView.motionManager stopDeviceMotionUpdates]; }
	}
	[self scheduleDrain];
}

- (void)coverPrivateSurface {
	if (!_container.isViewLoaded) {
		return;
	}
	if (!_privacyCover) {
		++_privacyCoverCount;
		_concealedSampleAttempts = 0;
		_privacyCover = [[UIView alloc] initWithFrame:_container.view.bounds];
		_privacyCover.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
		_privacyCover.backgroundColor = [UIColor colorWithRed:0.07 green:0.11 blue:0.10 alpha:1];
		_privacyCover.isAccessibilityElement = YES;
		_privacyCover.accessibilityLabel = @"Game paused";
		_privacyCover.accessibilityIdentifier = @"godot-privacy-cover";
		[_container.view addSubview:_privacyCover];
	}
	[_container.view bringSubviewToFront:_privacyCover];
	_observedView.accessibilityElementsHidden = YES;
}

- (void)close {
	if (!NSThread.isMainThread || _closed || _closeRequested) {
		return;
	}
	_closeRequested = YES;
	_presentationActive = NO;
	[_retainedOwner invalidatePresentationForFailure:_failure != nil];
	++_foregroundGeneration;
	[self removeAudioInterruptionObserver];
	_state = @"closing";
	_closeDuringDraw += _drawDepth > 0 ? 1 : 0;
	_closeDuringInitialization += _engineDepth > 0 && !_started ? 1 : 0;
	[self coverPrivateSurface];
	[_observedView stopRendering];
	[_observedView.motionManager stopDeviceMotionUpdates];
	_surfaceLayoutRequested = NO;
	_observedView.userInteractionEnabled = NO;
	[_godotController invalidateInput];
	if (_retainedPolicy) {
		[self cancelQueuedDeliveries];
		[_events removeAllObjects];
		_launchDocument = nil;
		_diagnosticsRequest = nil;
		_rendererDiagnostics = nil;
		_queuedBytes = 0;
		self.eventHandler = nil;
	}
	[self scheduleDrain];
}

- (void)requestCloseDuringNextDrawForProbe {
	if (NSThread.isMainThread && [self canDraw]) {
		_closeOnNextDraw = YES;
	}
}

- (void)requestCloseAfterSetupForProbe {
	if (NSThread.isMainThread && !_bootstrapAttempted) {
		_closeAfterSetup = YES;
	}
}

- (BOOL)requestRendererDiagnostics {
	if (!NSThread.isMainThread || !_started || !_readySeen || _closeRequested || _closed || _leaveRequested ||
			(_retainedPolicy && (!_presentationActive || _emptyTree)) || _diagnosticsRequest || _diagnosticsRequests == INT64_MAX) {
		return NO;
	}
	_diagnosticsRequest = @(++_diagnosticsRequests).stringValue;
	[self scheduleDrain];
	return YES;
}

- (BOOL)receiveRendererDiagnostics:(NSString *)document {
	if (!_diagnosticsRequest || _closeRequested || _closed || _leaveRequested || (_retainedPolicy && !_presentationActive)) {
		return NO;
	}
	NSDictionary *value = PDSanitizedDiagnostics(PDObject(document, PDDiagnosticsLimit), _presentationID, _presentationMode);
	if (!value || ![value[@"requestId"] isEqual:_diagnosticsRequest] || ![value[@"revision"] isEqual:_revision] ||
			[value[@"foreground"] boolValue] != _foreground || _pendingForegroundLoss ||
			(_lastDiagnosticsSequence && PDCompareCounter(value[@"sequence"], _lastDiagnosticsSequence) != NSOrderedDescending)) {
		++_rejectedDiagnostics;
		return NO;
	}
	_rendererDiagnostics = value;
	_concealedDiagnosticIteration = _iterations;
	_lastDiagnosticsSequence = value[@"sequence"];
	_diagnosticsRequest = nil;
	++_acceptedDiagnostics;
	return YES;
}

- (void)scheduleDrain {
	if (_drainScheduled || _closed) {
		return;
	}
	_drainScheduled = YES;
	dispatch_async(dispatch_get_main_queue(), ^{
		self->_drainScheduled = NO;
		[self drain];
	});
}

- (BOOL)emitCommand:(NSDictionary *)command {
	if (!bridge || !_started) {
		return NO;
	}
	NSData *bytes = [NSJSONSerialization dataWithJSONObject:command options:0 error:nil];
	NSString *document = [[NSString alloc] initWithData:bytes encoding:NSUTF8StringEncoding];
	_lastStateMutationIteration = _iterations;
	++_engineDepth;
	Error sent = bridge->emit_signal("command_received", String::utf8(document.UTF8String));
	--_engineDepth;
	return sent == OK;
}

- (BOOL)applyPendingLifecycleForce:(BOOL)force {
	if (!_started || !bridge || _closeRequested || _leaveRequested || _quarantined) { return NO; }
	// A false->true pair may arrive before this drain. Always deliver the loss
	// first so private presentation state is concealed, then apply the latest
	// foreground state. Clearing before callbacks preserves a reentrant loss.
	if (_pendingForegroundLoss) {
		_pendingForegroundLoss = NO;
		if (![self emitCommand:@{ @"protocolVersion": @1, @"type": @"foreground", @"presentationId": _presentationID, @"isForeground": @NO }]) { return NO; }
		_concealAfterIteration = _iterations;
		++_engineDepth;
		OS_AppleEmbedded::get_singleton()->on_enter_background();
		--_engineDepth;
		++_backgroundTransitions;
		_appliedForeground = NO;
		_lifecycleApplied = YES;
	}
	BOOL transition = !_lifecycleApplied || _appliedForeground != _foreground;
	if (force && !transition) {
		if (![self emitCommand:@{ @"protocolVersion": @1, @"type": @"foreground", @"presentationId": _presentationID, @"isForeground": @(_foreground) }]) { return NO; }
	}
	if (transition) {
		if (![self emitCommand:@{ @"protocolVersion": @1, @"type": @"foreground", @"presentationId": _presentationID, @"isForeground": @(_foreground) }]) { return NO; }
		++_engineDepth;
		if (_foreground) {
			if (_retainedPolicy && ![self applicationAllowsGraphics]) {
				--_engineDepth;
				[self setForeground:_requestedForeground];
				return NO;
			}
			OS_AppleEmbedded::get_singleton()->on_exit_background();
		} else {
			++_backgroundTransitions;
			OS_AppleEmbedded::get_singleton()->on_enter_background();
		}
		--_engineDepth;
		_appliedForeground = _foreground;
		_lifecycleApplied = YES;
		if (_foreground) {
			if (_retainedPolicy) {
				AudioDriverCoreAudio *audio = PDCoreAudioDriver();
				auto observed = audio ? audio->get_partydeck_output_state() : AudioDriverCoreAudio::PartyDeckOutputState{};
				if (!audio || !observed.output_unit_present || observed.input_unit_present || !observed.active || observed.last_start_status != noErr) {
					[self quarantineRetained:@"RETAINED_AUDIO_RESUME_FAILED"];
					return NO;
				}
			}
			if (_retainedPolicy && [self applicationAllowsGraphics] && _observedView.motionManager.deviceMotionAvailable) {
				[_observedView.motionManager startDeviceMotionUpdatesUsingReferenceFrame:CMAttitudeReferenceFrameXMagneticNorthZVertical];
			}
			[_observedView startRendering];
		}
	}
	_state = _foreground ? @"running" : @"paused";
	if (_concealFramePending && !_foreground) { [_observedView startRendering]; }
	return !_closeRequested && !_leaveRequested && !_quarantined;
}

- (void)drain {
	// Dispatch blocks can run inside GDTView's nested run loop. Do not requeue
	// in a busy loop there; endDraw/startInContainer arrange a later safe drain.
	if (_drawDepth || _engineDepth || _deliveryDepth || _closed || Main::is_iterating() ||
			(MessageQueue::get_singleton() && MessageQueue::get_singleton()->is_flushing())) {
		return;
	}
	PDNativeTimingScope drainTiming(_nativeTimings.drain);
	[self completeCancelledDeliveries];
	// UIKit can change its actual state before the shell's scene callback. Move
	// the native epoch/cover first, so queued work cannot complete in old facts.
	if (_retainedPolicy && _presentationActive && !_leaveRequested &&
			((_requestedForeground && [self applicationAllowsGraphics] && !_audioInterrupted) != _announcedForeground ||
			[self applicationIsBackgrounded] != _announcedBackgrounded)) {
		[self setForeground:_requestedForeground];
	}
	if (_retainedPolicy && _started && [self applicationAllowsGraphics] && !_quarantined &&
			(!_retainedContext || ![EAGLContext setCurrentContext:_retainedContext])) {
		[self quarantineRetained:@"RETAINED_RENDER_CONTEXT_UNAVAILABLE"];
	}
	if (_retainedPolicy && _closeRequested && _started && ![self applicationAllowsGraphics] && !_quarantined) {
		AudioDriverCoreAudio *audio = PDCoreAudioDriver();
		if (audio) { audio->stop(); }
		return;
	}
	if (_closeRequested) {
		[self cancelQueuedDeliveries];
		[self completeCancelledDeliveries];
		[_events removeAllObjects];
		_diagnosticsRequest = nil;
		_rendererDiagnostics = nil;
		_queuedBytes = 0;
		if (_started && _presentationID && !_quarantined) {
			[self emitCommand:@{ @"protocolVersion": @1, @"type": @"close", @"presentationId": _presentationID }];
		}
		[_observedView stopRendering];
		if (_retainedPolicy && _quarantined) {
			AudioDriverCoreAudio *audio = PDCoreAudioDriver();
			if (audio) { audio->stop(); }
		}
		[_godotController.view endEditing:YES];
		if (_godotController) {
			[NSNotificationCenter.defaultCenter removeObserver:_godotController];
		}
		if (_setup2Succeeded && !_quarantined) {
			_cleanupDepth = _drawDepth + _engineDepth + _deliveryDepth;
			++_engineDepth;
			if (_started) {
				OS_AppleEmbedded::get_singleton()->on_enter_background();
			}
			apple_embedded_finish();
			++_cleanupCount;
			--_engineDepth;
			_started = NO;
			GDTAppDelegateService.viewController = nil;
			activeRuntime = nil;
		} else if (!_bootstrapAttempted) {
			_started = NO;
		}
		if (!_quarantined) {
			_observedView.renderer = nil;
			_observedView.delegate = nil;
			[_godotController willMoveToParentViewController:nil];
			[_godotController.view removeFromSuperview];
			[_godotController removeFromParentViewController];
			_godotController = nil;
			_retainedContext = nil;
		}
		_launchDocument = nil;
		// Restore even for cancellation before bootstrap or quarantined setup
		// failure. This UIKit property does not depend on a surviving engine.
		if (_idleTimerPolicyCaptured && (!_retainedPolicy || !_dormant)) {
			UIApplication.sharedApplication.idleTimerDisabled = _previousIdleTimerDisabled;
			_idleTimerPolicyRestored = UIApplication.sharedApplication.idleTimerDisabled == _previousIdleTimerDisabled;
		}
		if (!_quarantined) {
			[_privacyCover removeFromSuperview];
			_privacyCover = nil;
		}
		self.eventHandler = nil;
		_closed = YES;
		_state = _failure ? @"failed" : @"closed";
		if (_retainedPolicy) { [_retainedOwner presentationFinished:[self snapshot]]; }
		return;
	}
	if (_retainedPolicy && _leaveRequested) {
		[self drainRetainedLeave];
		return;
	}
	if (_surfaceLayoutRequested && _started && !_quarantined && [self applicationAllowsGraphics]) {
		_surfaceLayoutRequested = NO;
		++_engineDepth;
		BOOL laidOut = [_observedView performGuardedLayout];
		--_engineDepth;
		if (!laidOut) { [self failNativePresentation]; return; }
	}
	if (_retainedPolicy && _maintenance) {
		if ([_maintenance isEqual:@"warming"] && _maintenanceCompleted) { [self installRetainedScene]; }
		else if (_applicationActive && !_maintenanceCompleted) { [_observedView startRendering]; }
		return;
	}
	if (_retainedPolicy && (!_presentationActive || _dormant || _emptyTree)) { return; }
	if (!_started) {
		return;
	}
	if (![self applyPendingLifecycleForce:NO]) { return; }
	while (_commands.count && !_closeRequested && !_leaveRequested) {
		PDNativeDelivery *delivery = _commands.firstObject;
		NSString *document = delivery.document;
		[_commands removeObjectAtIndex:0];
		_queuedBytes -= [document lengthOfBytesUsingEncoding:NSUTF8StringEncoding];
		if (_retainedPolicy && (delivery.lifecycleGeneration != _lifecycleGeneration ||
				(delivery.confirmReady && (!_readySeen || _readyEvents != 1)))) {
			[self completeDelivery:delivery success:NO];
			continue;
		}
		NSDictionary *command = PDObject(document, PDCommandLimit);
		BOOL delivered = YES;
		if (_retainedPolicy && [command[@"type"] isEqual:@"foreground"]) {
			_authorityForeground = [command[@"isForeground"] boolValue];
			[self applyRendererForeground:_authorityForeground && _requestedForeground && [self applicationAllowsGraphics] && !_audioInterrupted];
			delivered = [self applyPendingLifecycleForce:YES];
		} else {
			_lastStateMutationIteration = _iterations;
			_concealedSampleAttempts = 0;
			++_engineDepth;
			Error sent = bridge->emit_signal("command_received", String::utf8(document.UTF8String));
			--_engineDepth;
			delivered = sent == OK;
		}
		delivered = delivered && (!_retainedPolicy || ([self acceptsGeneration:_presentationGeneration] && delivery.lifecycleGeneration == _lifecycleGeneration));
		if (delivered && delivery.confirmReady) { delivered = [self confirmRetainedReady]; }
		[self completeDelivery:delivery success:delivered];
		if ([command[@"type"] isEqual:@"close"]) { [self leavePresentation]; }
	}
	while (_events.count && !_closeRequested && !_leaveRequested) {
		NSDictionary *queued = _events.firstObject;
		NSString *document = queued[@"document"];
		[_events removeObjectAtIndex:0];
		NSDictionary *event = PDObject(document, PDEventLimit);
		NSString *type = event[@"type"];
		// Enqueue validation is not final: a native view/lifecycle update can
		// arrive while an engine frame is unwinding. Authority must also validate
		// the resulting intent through the common bridge before any game action.
		if ([type isEqual:@"intent"] && (!_foreground || _pendingForegroundLoss ||
				[queued[@"foregroundGeneration"] unsignedIntegerValue] != _foregroundGeneration || ![event[@"expectedRevision"] isEqual:_revision])) {
			++_rejectedEvents;
			continue;
		}
		_readyEvents += [type isEqual:@"ready"] ? 1 : 0;
		_exitEvents += [type isEqual:@"exit"] ? 1 : 0;
		_intentEvents += [type isEqual:@"intent"] ? 1 : 0;
		++_deliveryDepth;
		if (self.eventHandler) {
			self.eventHandler(document);
		}
		--_deliveryDepth;
		if ([type isEqual:@"exit"] || [type isEqual:@"failed"]) {
			if ([type isEqual:@"failed"]) {
				_failure = event[@"reason"];
			}
			if (_retainedPolicy && [type isEqual:@"exit"]) { [self leavePresentation]; }
			else { [self close]; }
		}
	}
	if (_retainedPolicy && _privacyCover && _readySeen && _foreground && _appliedForeground && !_pendingForegroundLoss &&
			!_diagnosticsRequest && !_leaveRequested && ![self hasConcealedCurrentDiagnostics] && _iterations > _lastStateMutationIteration) {
		if (_concealedSampleAttempts >= PDConcealedSampleLimit) { [self quarantineRetained:@"RETAINED_CONCEALMENT_NOT_OBSERVED"]; return; }
		++_concealedSampleAttempts;
		[self requestRendererDiagnostics];
	}
	if (_diagnosticsRequest && !_commands.count && !_events.count && !_closeRequested && !_leaveRequested && !_pendingForegroundLoss && _appliedForeground == _foreground) {
		// The shared renderer answers this read-only request synchronously. Do
		// not query between an accepted event and its queued replacement view.
		NSString *request = _diagnosticsRequest;
		const uint64_t presentationGeneration = _presentationGeneration;
		const uint64_t lifecycleGeneration = _lifecycleGeneration;
		const NSUInteger foregroundGeneration = _foregroundGeneration;
		++_engineDepth;
		bridge->emit_signal("diagnostics_requested", String::utf8(request.UTF8String));
		--_engineDepth;
		if (!_diagnosticsRequest && [_rendererDiagnostics[@"requestId"] isEqual:request] &&
				_presentationGeneration == presentationGeneration && _lifecycleGeneration == lifecycleGeneration &&
				_foregroundGeneration == foregroundGeneration && NSThread.isMainThread &&
				_foreground && _appliedForeground && [self canDraw]) {
			// Diagnostics do not invalidate a static scene in low-processor mode.
			// Request one coalesced draw for this accepted, still-current sample;
			// the normal draw and successful layer-presentation gates remain in force.
			Main::force_redraw();
		}
		if (_diagnosticsRequest) {
			++_unansweredDiagnostics;
			_diagnosticsRequest = nil;
		}
	}
	if (_closeRequested || _leaveRequested || _events.count || _commands.count || _diagnosticsRequest || _pendingForegroundLoss || !_lifecycleApplied || _appliedForeground != _foreground) {
		[self scheduleDrain];
	}
}

- (void)setApplicationActive:(BOOL)active {
	[self setApplicationActive:active backgrounded:UIApplication.sharedApplication.applicationState == UIApplicationStateBackground];
}

- (void)setApplicationActive:(BOOL)active backgrounded:(BOOL)backgrounded {
	if (!NSThread.isMainThread || _closed || !_retainedPolicy) {
		// The owner may receive the application's first activation before entry.
		if (NSThread.isMainThread && !_closed) { _applicationActive = active && !backgrounded; _applicationBackgrounded = backgrounded; }
		return;
	}
	_applicationActive = active && !backgrounded;
	_applicationBackgrounded = backgrounded;
	if (!_applicationActive) {
		[_observedView stopRendering];
		[_observedView.motionManager stopDeviceMotionUpdates];
	}
	if (_presentationActive && !_leaveRequested) { [self setForeground:_requestedForeground]; }
	// Dormant activation performs no OS lifecycle call and cannot restart audio.
	if (_maintenance || _leaveRequested || _closeRequested) { [self scheduleDrain]; }
}

- (void)removeAudioInterruptionObserver {
	++_interruptionObserverGeneration;
	if (_audioInterruptionObserver) {
		[NSNotificationCenter.defaultCenter removeObserver:_audioInterruptionObserver];
		_audioInterruptionObserver = nil;
	}
}

- (void)installAudioInterruptionObserver {
	if (_audioInterruptionObserver) { return; }
	uint64_t generation = ++_interruptionObserverGeneration;
	__weak PDGodotRuntime *weakSelf = self;
	_audioInterruptionObserver = [NSNotificationCenter.defaultCenter addObserverForName:AVAudioSessionInterruptionNotification
			object:AVAudioSession.sharedInstance queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *notification) {
		PDGodotRuntime *runtime = weakSelf;
		if (!runtime) { return; }
		if (runtime->_closed || runtime->_closeRequested || generation != runtime->_interruptionObserverGeneration) {
			++runtime->_ignoredInterruptionCallbacks; return;
		}
		NSNumber *kind = notification.userInfo[AVAudioSessionInterruptionTypeKey];
		if (kind.unsignedIntegerValue == AVAudioSessionInterruptionTypeBegan) {
			++runtime->_audioInterruptions;
			runtime->_audioInterrupted = YES;
			if (runtime->_presentationActive && !runtime->_leaveRequested) { [runtime setForeground:runtime->_requestedForeground]; }
		} else if (kind.unsignedIntegerValue == AVAudioSessionInterruptionTypeEnded) {
			runtime->_audioInterrupted = NO;
			// Owner-lifetime facts survive shell intervals. A dormant callback
			// performs no renderer delivery, scene work or native service resume.
			if (!runtime->_presentationActive || runtime->_leaveRequested) { return; }
			NSNumber *options = notification.userInfo[AVAudioSessionInterruptionOptionKey];
			if ((options.unsignedIntegerValue & AVAudioSessionInterruptionOptionShouldResume) && [runtime applicationAllowsGraphics]) {
				[runtime setForeground:runtime->_requestedForeground];
			} else if (!(options.unsignedIntegerValue & AVAudioSessionInterruptionOptionShouldResume)) {
				runtime->_requestedForeground = NO;
			}
		}
	}];
}

- (void)leavePresentation {
	if (!NSThread.isMainThread || !_retainedPolicy || !_presentationActive || _leaveRequested || _closeRequested || _closed) { return; }
	_presentationActive = NO;
	[_retainedOwner invalidatePresentationForFailure:NO];
	_leaveRequested = YES;
	_state = @"leaving";
	++_foregroundGeneration;
	[self coverPrivateSurface];
	[_observedView stopRendering];
	[_godotController invalidateInput];
	_observedView.userInteractionEnabled = NO;
	[_observedView.motionManager stopDeviceMotionUpdates];
	_surfaceLayoutRequested = NO;
	[self cancelQueuedDeliveries];
	[_events removeAllObjects];
	_queuedBytes = 0;
	_launchDocument = nil;
	_diagnosticsRequest = nil;
	_rendererDiagnostics = nil;
	self.eventHandler = nil;
	[self scheduleDrain];
}

- (void)quarantineRetained:(NSString *)reason {
	_failure = reason;
	_quarantined = YES;
	[self coverPrivateSurface];
	[_observedView stopRendering];
	[_observedView.motionManager stopDeviceMotionUpdates];
	// close() retains the native surface in a failed process when quarantine
	// prevents proving full cleanup safe. It never grants another entry.
	[self close];
}

- (void)beginMaintenance:(NSString *)kind {
	_maintenance = kind;
	_maintenanceCompleted = NO;
	_maintenanceStartIteration = _iterations;
	_state = kind;
	Main::force_redraw();
	if (_applicationActive) { [_observedView startRendering]; }
}

- (void)drainRetainedLeave {
	if (!_bootstrapAttempted) {
		// Cancellation before bootstrap did not consume the one engine attempt.
		_prepared = NO;
		_leaveRequested = NO;
		_dormant = YES;
		_state = @"dormant";
		UIApplication.sharedApplication.idleTimerDisabled = _previousIdleTimerDisabled;
		_idleTimerPolicyRestored = UIApplication.sharedApplication.idleTimerDisabled == _previousIdleTimerDisabled;
		_container.runtime = nil;
		_container = nil;
		_privacyCover = nil;
		[_retainedOwner presentationFinished:[self snapshot]];
		return;
	}
	if (!_started || !_setup2Succeeded || !OS_AppleEmbedded::get_singleton() || !SceneTree::get_singleton()) {
		[self quarantineRetained:@"RETAINED_TEARDOWN_WITHOUT_INITIALIZED_TREE"];
		return;
	}
	if (![self applicationAllowsGraphics] && ![_state isEqual:@"observing"]) {
		// iOS forbids background OpenGL work. Gates and cover are already closed;
		// stop the native services now and defer scene/GPU teardown until active.
		AudioDriverCoreAudio *audio = PDCoreAudioDriver();
		if (audio) { audio->stop(); }
		if (!audio || !PDAudioStopped(audio->get_partydeck_output_state()) || _observedView.motionManager.deviceMotionActive) {
			[self quarantineRetained:@"RETAINED_BACKGROUND_SERVICE_SUSPENSION_FAILED"];
		}
		return;
	}
	if (_emptyTree && ![_state isEqual:@"observing"] && ![_maintenance isEqual:@"neutralizing"]) {
		// A new handle can close while its empty-tree warm-up is still pending.
		// No replacement scene has entered, but service and queue observations
		// must still complete before this handle permits another entry.
		[_observedView stopRendering];
		++_engineDepth;
		OS_AppleEmbedded::get_singleton()->on_enter_background();
		AudioDriverCoreAudio *audio = PDCoreAudioDriver();
		if (audio) { audio->stop(); }
		Input::get_singleton()->release_pressed_events();
		Input::get_singleton()->flush_buffered_events();
		Error flushed = MessageQueue::get_singleton()->flush();
		_audioRetirementError = audio ? audio->partydeck_retire_closed_playbacks(_audioRetirement) : ERR_UNAVAILABLE;
		--_engineDepth;
		if (flushed != OK || _audioRetirementError != OK || _observedView.motionManager.deviceMotionActive) {
			[self quarantineRetained:@"RETAINED_PENDING_ENTRY_CANCELLATION_FAILED"]; return;
		}
		_oldSceneObjectsAbsent = YES;
		_emptyFrames = 0;
		[self beginMaintenance:@"neutralizing"];
		return;
	}
	if (!_emptyTree) {
		SceneTree *oldTree = SceneTree::get_singleton();
		_previousTreeID = oldTree->get_instance_id();
		_previousSceneID = _presentationSceneID;
		_retiringObjects.clear();
		_retiringObjects.push_back(_previousTreeID);
		std::vector<Node *> pending = { oldTree->get_root().ptr() };
		while (!pending.empty()) {
			Node *node = pending.back();
			pending.pop_back();
			if (_retiringObjects.size() + pending.size() >= PDSceneNodeLimit) {
				[self quarantineRetained:@"RETAINED_SCENE_NODE_BOUND"];
				return;
			}
			_retiringObjects.push_back(node->get_instance_id());
			for (int index = 0; index < node->get_child_count(true); ++index) { pending.push_back(node->get_child(index, true)); }
		}
		_retiredNodeCount = _retiringObjects.size();
		_retirementDepth = _drawDepth + _engineDepth + _deliveryDepth;
		[self emitCommand:@{ @"protocolVersion": @1, @"type": @"close", @"presentationId": _presentationID }];
		++_engineDepth;
		OS_AppleEmbedded::get_singleton()->on_enter_background();
		AudioDriverCoreAudio *audio = PDCoreAudioDriver();
		if (audio) { audio->stop(); }
		BOOL stopped = audio && PDAudioStopped(audio->get_partydeck_output_state()) && !_observedView.motionManager.deviceMotionActive;
		if (!stopped) {
			--_engineDepth;
			[self quarantineRetained:@"RETAINED_SERVICE_SUSPENSION_FAILED"];
			return;
		}
		OS_AppleEmbedded::get_singleton()->partydeck_delete_main_loop();
		SceneTree *freshTree = memnew(SceneTree);
		OS_AppleEmbedded::get_singleton()->partydeck_set_main_loop(freshTree);
		PDConfigureFreshTree(freshTree);
		freshTree->initialize();
		_emptyTree = YES;
		_oldSceneObjectsAbsent = YES;
		for (ObjectID object : _retiringObjects) {
			if (ObjectDB::get_instance(object)) { _oldSceneObjectsAbsent = NO; break; }
		}
		// Only normal dispatch against the fresh empty tree. This is audited
		// fixed content, not a hard work/time bound for arbitrary queued scripts.
		Input::get_singleton()->release_pressed_events();
		Input::get_singleton()->flush_buffered_events();
		Error flushed = MessageQueue::get_singleton()->flush();
		_audioRetirementError = audio->partydeck_retire_closed_playbacks(_audioRetirement);
		BOOL clean = _oldSceneObjectsAbsent && flushed == OK && _audioRetirementError == OK &&
				freshTree->get_node_count() == 1 && !freshTree->get_current_scene() && PDBridgeConnectionCount(bridge) == 0 &&
				!Input::get_singleton()->is_anything_pressed();
		RenderingServer::get_singleton()->set_default_clear_color(Color(0.07, 0.11, 0.10, 1));
		--_engineDepth;
		if (!clean) { [self quarantineRetained:@"RETAINED_EMPTY_TREE_RETIREMENT_FAILED"]; return; }
		_emptyFrames = 0;
		[self beginMaintenance:@"neutralizing"];
		return;
	}
	if ([_maintenance isEqual:@"neutralizing"] && !_maintenanceCompleted) {
		if (_applicationActive) { [_observedView startRendering]; }
		return;
	}
	if ([_maintenance isEqual:@"neutralizing"] && _maintenanceCompleted) {
		++_engineDepth;
		Input::get_singleton()->release_pressed_events();
		Input::get_singleton()->flush_buffered_events();
		Error flushed = MessageQueue::get_singleton()->flush();
		--_engineDepth;
		if (flushed != OK || SceneTree::get_singleton()->get_node_count() != 1 || PDBridgeConnectionCount(bridge) != 0 ||
				Input::get_singleton()->is_anything_pressed()) {
			[self quarantineRetained:@"RETAINED_NEUTRAL_FRAME_RESIDUALS"];
			return;
		}
		if (MessageQueue::get_singleton()->has_messages()) {
			if (_emptyFrames >= PDEmptyFrameLimit) { [self quarantineRetained:@"RETAINED_DEFERRED_DRAIN_LIMIT"]; return; }
			[self beginMaintenance:@"neutralizing"];
			return;
		}
		_neutralFramePresented = YES;
		_maintenance = nil;
		[_observedView stopRendering];
		[_godotController willMoveToParentViewController:nil];
		[_godotController.view removeFromSuperview];
		[_godotController removeFromParentViewController];
		_container.runtime = nil;
		_container = nil;
		_privacyCover = nil;
		UIApplication.sharedApplication.idleTimerDisabled = _previousIdleTimerDisabled;
		_idleTimerPolicyRestored = UIApplication.sharedApplication.idleTimerDisabled == _previousIdleTimerDisabled;
		_presentationID = _presentationMode = _revision = _lastSequence = _lastDiagnosticsSequence = nil;
		AudioDriverCoreAudio *audio = PDCoreAudioDriver();
		_audioObservationStart = audio ? audio->get_partydeck_output_state() : AudioDriverCoreAudio::PartyDeckOutputState{};
		if (!audio || !PDAudioStopped(_audioObservationStart)) {
			[self quarantineRetained:@"RETAINED_AUDIO_NOT_STOPPED_FOR_OBSERVATION"]; return;
		}
		_dormantObservationStarted = NSProcessInfo.processInfo.systemUptime;
		_state = @"observing";
		uint64_t generation = _presentationGeneration;
		dispatch_after(dispatch_time(DISPATCH_TIME_NOW, static_cast<int64_t>(PDDormantObservationInterval * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
			[self finishDormantObservation:generation];
		});
	}
}

- (void)finishDormantObservation:(uint64_t)generation {
	if (_closed || _closeRequested || _quarantined || !_leaveRequested || generation != _presentationGeneration || ![_state isEqual:@"observing"]) { return; }
	AudioDriverCoreAudio *audio = PDCoreAudioDriver();
	if (!audio) { [self quarantineRetained:@"RETAINED_AUDIO_DRIVER_LOST"]; return; }
	auto after = audio->get_partydeck_output_state();
	_audioQuiescenceObserved = PDAudioStopped(after) && after.output_callback_entries == _audioObservationStart.output_callback_entries &&
			after.start_attempts == _audioObservationStart.start_attempts && after.stop_attempts == _audioObservationStart.stop_attempts &&
			NSProcessInfo.processInfo.systemUptime - _dormantObservationStarted >= PDDormantObservationInterval &&
			!_observedView.isActive && !_observedView.motionManager.deviceMotionActive && _observedView.superview == nil &&
			!MessageQueue::get_singleton()->has_messages() && SceneTree::get_singleton()->get_node_count() == 1 &&
			PDBridgeConnectionCount(bridge) == 0 && _commands.count == 0 && _cancelledDeliveries.count == 0 && _events.count == 0 && !_launchDocument && !self.eventHandler &&
			_drawDepth == 0 && _engineDepth == 0 && _deliveryDepth == 0 && !Main::is_iterating() && !MessageQueue::get_singleton()->is_flushing();
	if (!_audioQuiescenceObserved) { [self quarantineRetained:@"RETAINED_DORMANT_OBSERVATION_FAILED"]; return; }
	_leaveRequested = NO;
	_dormant = YES;
	_foreground = _appliedForeground = NO;
	_lifecycleApplied = NO;
	++_suspensionCount;
	_state = @"dormant";
	_retiringObjects.clear();
	[_retainedOwner presentationFinished:[self snapshot]];
}

- (void)installRetainedScene {
	if (!_presentationActive || _leaveRequested || _closeRequested || !_emptyTree || !_maintenanceCompleted || !_foreground || ![self applicationAllowsGraphics]) { return; }
	SceneTree *tree = SceneTree::get_singleton();
	if (!tree || tree->get_node_count() != 1 || PDBridgeConnectionCount(bridge) != 0) {
		[self quarantineRetained:@"RETAINED_REENTRY_WITHOUT_EMPTY_TREE"]; return;
	}
	++_engineDepth;
	Input::get_singleton()->release_pressed_events();
	Input::get_singleton()->flush_buffered_events();
	Error flushed = MessageQueue::get_singleton()->flush();
	Ref<PackedScene> packed;
	if (flushed == OK && !MessageQueue::get_singleton()->has_messages()) {
		packed = ResourceLoader::load("res://main.tscn", "PackedScene");
	}
	Node *scene = packed.is_valid() ? packed->instantiate() : nullptr;
	if (scene) {
		_presentationSceneID = scene->get_instance_id();
		_emptyTree = NO;
		_maintenance = nil;
		RenderingServer::get_singleton()->set_default_clear_color(GLOBAL_GET("rendering/environment/defaults/default_clear_color"));
		tree->set_pause(false);
		tree->add_current_scene(scene);
		_coverUntilIteration = _iterations + 2;
		_state = @"initializing";
	}
	--_engineDepth;
	if (!scene) { [self quarantineRetained:@"RETAINED_FIXED_SCENE_INSTANTIATION_FAILED"]; return; }
	[self scheduleDrain];
}

- (BOOL)confirmRetainedReady {
	if (![self acceptsGeneration:_presentationGeneration] || !_readySeen || _readyEvents != 1) { return NO; }
	_authorityReadyConfirmed = YES;
	[self scheduleDrain];
	return YES;
}

- (NSDictionary<NSString *, id> *)snapshot {
	NSAssert(NSThread.isMainThread, @"Probe observations belong to the native main thread.");
	const double timingSnapshotUptime = PDNativeTimingUptime();
	NSMutableDictionary *snapshot = [@{
		@"state": _state, @"failure": _failure ?: @"", @"bootstrapCount": @(processBootstrapCount),
		@"setup2Succeeded": @(_setup2Succeeded), @"mainStarted": @(_started),
		@"bootstrapExitCode": @(_bootstrapExitCode), @"setup2ErrorCode": @(_setup2ErrorCode),
		@"mainStartExitCode": @(_mainStartExitCode),
		@"displayScale": @(_displayScale),
		@"surfaceSize": @{ @"width": @(_observedView.bounds.size.width), @"height": @(_observedView.bounds.size.height) },
		@"rendererDiagnostics": _rendererDiagnostics ?: @{},
		@"diagnosticsRequests": @(_diagnosticsRequests), @"acceptedDiagnostics": @(_acceptedDiagnostics),
		@"rejectedDiagnostics": @(_rejectedDiagnostics), @"unansweredDiagnostics": @(_unansweredDiagnostics),
		@"iterations": @(_iterations), @"drawCalls": @(_drawCalls), @"drawDepth": @(_drawDepth),
		@"timings": @{
			@"schemaVersion": @1, @"snapshotUptime": @(timingSnapshotUptime),
			@"drawView": PDNativeStageTimingSnapshot(_nativeTimings.draw_view),
			@"uikitPump": PDNativeStageTimingSnapshot(_nativeTimings.uikit_pump),
			@"setupView": PDNativeStageTimingSnapshot(_nativeTimings.setup_view),
			@"renderOnView": PDNativeStageTimingSnapshot(_nativeTimings.render_on_view),
			@"iterate": PDNativeStageTimingSnapshot(_nativeTimings.iterate),
			@"presentRenderbuffer": PDNativeStageTimingSnapshot(_nativeTimings.present_renderbuffer),
			@"drain": PDNativeStageTimingSnapshot(_nativeTimings.drain)
		},
		@"cleanupCount": @(_cleanupCount), @"cleanupDepth": @(_cleanupDepth),
		@"closeRequestedDuringDraw": @(_closeDuringDraw), @"renderLoopActive": @(_observedView.isActive),
		@"closeRequestedDuringInitialization": @(_closeDuringInitialization),
		@"osSingletonPresent": @(OS::get_singleton() != nullptr), @"bridgeRegistered": @(bridge != nullptr),
		@"viewReleased": @(_bootstrapAttempted && !_observedView && !_quarantined),
		@"controllerReleased": @(_bootstrapAttempted && !_observedController && !_quarantined),
		@"readyEvents": @(_readyEvents), @"exitEvents": @(_exitEvents), @"intentEvents": @(_intentEvents),
		@"rejectedEvents": @(_rejectedEvents), @"backgroundTransitions": @(_backgroundTransitions),
		@"queuedCommands": @(_commands.count), @"queuedEvents": @(_events.count), @"queuedBytes": @(_queuedBytes),
		@"foreground": @(_foreground), @"quarantined": @(_quarantined),
		@"privacyCoverVisible": @(_privacyCover != nil), @"pendingForegroundLoss": @(_pendingForegroundLoss),
		@"privacyCoverCount": @(_privacyCoverCount),
		@"idleTimerPolicyCaptured": @(_idleTimerPolicyCaptured), @"idleTimerPolicyRestored": @(_idleTimerPolicyRestored),
		@"previousIdleTimerDisabled": @(_previousIdleTimerDisabled), @"idleTimerDisabledAfterSetup": @(_idleTimerDisabledAfterSetup),
		@"idleTimerDisabled": @(UIApplication.sharedApplication.idleTimerDisabled),
		@"renderingLayerClass": _renderingLayerClass ?: @"", @"reinitializationQualified": @NO,
		@"kmpFactoryQualified": @NO
	} mutableCopy];
	if (_retainedPolicy) { [snapshot addEntriesFromDictionary:[self retainedSnapshot]]; }
	return snapshot;
}

- (NSDictionary *)retainedSnapshot {
	SceneTree *tree = SceneTree::get_singleton();
	CMMotionManager *motion = _observedView.motionManager;
	return @{
		@"retainedEnginePolicy": @YES, @"packSHA256": _fixedPackSHA256 ?: @"",
		@"processIdentifier": @(NSProcessInfo.processInfo.processIdentifier),
		@"presentationGeneration": @(_presentationGeneration).stringValue,
		@"lifecycleGeneration": @(_lifecycleGeneration).stringValue, @"inputGeneration": @(_foregroundGeneration).stringValue,
		@"nativeForeground": @(_presentationActive && _announcedForeground), @"authorityForegroundGrant": @(_authorityForeground),
		@"applicationActive": @([self applicationAllowsGraphics]), @"applicationBackgrounded": @(_presentationActive ? _announcedBackgrounded : [self applicationIsBackgrounded]),
		@"nativePresentedFrames": @(_presentedFrames), @"nativeFailedPresentations": @(_failedPresentations),
		@"surfaceLayoutRequested": @(_surfaceLayoutRequested), @"audioInterrupted": @(_audioInterrupted),
		@"inputViewEnabled": @(_observedView.userInteractionEnabled), @"surfaceAccessibilityHidden": @(_observedView.accessibilityElementsHidden),
		@"engineFramesDrawn": @(OS::get_singleton() && Engine::get_singleton() ? Engine::get_singleton()->get_frames_drawn() : 0).stringValue,
		@"concealedSampleAttempts": @(_concealedSampleAttempts), @"concealedSampleLimit": @(PDConcealedSampleLimit),
		@"presentationCount": @(_presentationCount), @"suspensionCount": @(_suspensionCount),
		@"presentationActive": @(_presentationActive), @"authorityReadyConfirmed": @(_authorityReadyConfirmed),
		@"dormant": @(_dormant), @"emptyTree": @(_emptyTree), @"surfaceAttached": @(_observedView.superview != nil),
		@"emptyTreeNodeCount": @(tree ? tree->get_node_count() : 0), @"bridgeConnections": @(PDBridgeConnectionCount(bridge)),
		@"engineIdentity": [NSString stringWithFormat:@"%p", static_cast<void *>(OS::get_singleton())],
		@"controllerIdentity": [NSString stringWithFormat:@"%p", (__bridge void *)_observedController],
		@"viewIdentity": [NSString stringWithFormat:@"%p", (__bridge void *)_observedView],
		@"layerIdentity": [NSString stringWithFormat:@"%p", (__bridge void *)_observedView.renderingLayer],
		@"treeIdentity": @(tree ? uint64_t(tree->get_instance_id()) : 0).stringValue,
		@"sceneIdentity": @(uint64_t(_presentationSceneID)).stringValue,
		@"previousTreeIdentity": @(uint64_t(_previousTreeID)).stringValue,
		@"previousSceneIdentity": @(uint64_t(_previousSceneID)).stringValue,
		@"oldSceneObjectsAbsent": @(_oldSceneObjectsAbsent), @"retiredNodeCount": @(_retiredNodeCount),
		@"retirementDepth": @(_retirementDepth), @"neutralFramePresented": @(_neutralFramePresented),
		@"neutralFrames": @(_neutralFrames), @"warmupFrames": @(_warmupFrames),
		@"audio": PDAudioSnapshot(), @"audioQuiescenceObserved": @(_audioQuiescenceObserved),
		@"audioObservationMinimumSeconds": @(PDDormantObservationInterval),
		@"audioObservationStartCallbacks": @(_audioObservationStart.output_callback_entries).stringValue,
		@"audioRetirement": @{
			@"error": @(_audioRetirementError), @"preflightPassed": @(_audioRetirement.preflight_passed),
			@"livePlaybacksBefore": @(_audioRetirement.live_playbacks_before), @"unlinkedPlaybacks": @(_audioRetirement.unlinked_playbacks),
			@"retiredPlaybacks": @(_audioRetirement.retired_playbacks), @"playbackCleanupSucceeded": @(_audioRetirement.playback_cleanup_succeeded),
			@"callbackCleanupSucceeded": @(_audioRetirement.callback_cleanup_succeeded), @"busDetailsCleanupSucceeded": @(_audioRetirement.bus_details_cleanup_succeeded),
			@"oldBusDetailsCleanupSucceeded": @(_audioRetirement.old_bus_details_cleanup_succeeded), @"residualsObserved": @(_audioRetirement.residuals_observed),
			@"playbacksRemaining": @(_audioRetirement.playbacks_remaining), @"callbacksRemaining": @(_audioRetirement.callbacks_remaining),
			@"busDetailsRemaining": @(_audioRetirement.bus_details_remaining), @"samplePlaybacksRemaining": @(_audioRetirement.sample_playbacks_remaining),
			@"serverBuffersNeutral": @(_audioRetirement.server_buffers_neutral), @"driverBufferNeutral": @(_audioRetirement.driver_buffer_neutral),
			@"driverQuiescent": @(_audioRetirement.driver_quiescent)
		},
		@"motion": @{ @"managerPresent": @(motion != nil), @"available": @(motion.deviceMotionAvailable), @"active": @(motion.deviceMotionActive) },
		@"queuedPrivateDocuments": @(_commands.count + (_launchDocument ? 1 : 0)),
		@"cancelledDeliveryCallbacks": @(_cancelledDeliveries.count),
		@"eventHandlerPresent": @(self.eventHandler != nil), @"audioInterruptionObserverPresent": @(_audioInterruptionObserver != nil),
		@"audioInterruptions": @(_audioInterruptions), @"ignoredInterruptionCallbacks": @(_ignoredInterruptionCallbacks),
		@"sdlEnabled": @(PDSDLEnabled),
		@"sameProcessReentryQualified": @NO
	};
}
@end

@implementation PDGodotEngineOwner {
	PDGodotRuntime *_runtime;
	PDGodotPresentation *_presentation;
	NSMutableSet<NSString *> *_issuedPresentationIDs;
	uint64_t _nextGeneration;
}

- (instancetype)init {
	self = [super init];
	if (self) {
		_runtime = [PDGodotRuntime new];
		[_runtime installAudioInterruptionObserver];
		_issuedPresentationIDs = [NSMutableSet new];
	}
	return self;
}

- (PDGodotRuntime *)ownedRuntime { return _runtime; }

- (BOOL)isCurrentPresentation:(PDGodotPresentation *)presentation {
	return NSThread.isMainThread && presentation == _presentation && !presentation.invalidated &&
			[_runtime acceptsGeneration:presentation.nativeGeneration];
}

- (PDGodotPresentation *)createPresentationWithProjectPath:(NSString *)projectPath packPath:(NSString *)packPath
										 launchDocument:(NSString *)launchDocument error:(NSError **)error {
	if (!NSThread.isMainThread || _presentation || _nextGeneration == INT64_MAX || _issuedPresentationIDs.count >= 1024) {
		PDReject(error, @"A new handle requires the main thread and a completed previous lifetime.");
		return nil;
	}
	NSString *identifier = PDObject(launchDocument, PDCommandLimit)[@"presentationId"];
	if (!PDIdentifier(identifier, 128) || [_issuedPresentationIDs containsObject:identifier]) {
		PDReject(error, @"Every retained entry requires a new presentation identifier.");
		return nil;
	}
	uint64_t generation = _nextGeneration + 1;
	if (![_runtime prepareRetainedWithProjectPath:projectPath packPath:packPath launchDocument:launchDocument
			generation:generation owner:self error:error]) { return nil; }
	_nextGeneration = generation;
	[_issuedPresentationIDs addObject:identifier];
	PDGodotPresentation *presentation = [PDGodotPresentation new];
	presentation.owner = self;
	presentation.nativeGeneration = generation;
	presentation.presentationID = identifier;
	presentation.viewController = _runtime.viewController;
	_presentation = presentation;
	__weak PDGodotEngineOwner *weakSelf = self;
	__weak PDGodotPresentation *weakPresentation = presentation;
	_runtime.eventHandler = ^(NSString *document) {
		PDGodotEngineOwner *owner = weakSelf;
		PDGodotPresentation *handle = weakPresentation;
		if (owner && handle && handle.nativeGeneration == generation && [owner isCurrentPresentation:handle]) {
			if (handle.eventHandler) { handle.eventHandler(document); }
		}
	};
	return presentation;
}

- (void)invalidatePresentationForFailure:(BOOL)failure {
	_presentation.invalidated = YES;
	_presentation.eventHandler = nil;
	_presentation.lifecycleHandler = nil;
	// Leave failures are reported through close completion. Only an unsolicited
	// terminal loss keeps its unsequenced failure callback until the safe drain.
	if (!failure) { _presentation.failureHandler = nil; }
}

- (void)reportLifecycleGeneration:(uint64_t)generation foreground:(BOOL)foreground backgrounded:(BOOL)backgrounded {
	PDGodotPresentation *presentation = _presentation;
	if ([self isCurrentPresentation:presentation] && presentation.lifecycleHandler) {
		presentation.lifecycleHandler(generation, foreground, backgrounded);
	}
}

- (void)presentationFinished:(NSDictionary *)snapshot {
	PDGodotPresentation *finished = _presentation;
	if (!finished) { return; }
	[finished setInvalidated:YES];
	finished.eventHandler = nil;
	finished.lifecycleHandler = nil;
	finished.closedSnapshot = snapshot;
	finished.viewController = nil;
	finished.owner = nil;
	void (^completion)(BOOL) = finished.closeCompletion;
	void (^failure)(void) = finished.failureHandler;
	finished.closeCompletion = nil;
	finished.failureHandler = nil;
	_presentation = nil;
	if (failure && [snapshot[@"failure"] length] > 0) { failure(); }
	if (completion) { completion([snapshot[@"state"] isEqual:@"dormant"]); }
}

- (void)setApplicationActive:(BOOL)active { [_runtime setApplicationActive:active]; }
- (void)setApplicationActive:(BOOL)active backgrounded:(BOOL)backgrounded { [_runtime setApplicationActive:active backgrounded:backgrounded]; }
- (void)shutdown { [_runtime close]; }
- (NSDictionary<NSString *, id> *)snapshot { return [_runtime snapshot]; }

- (void)dealloc {
	PDGodotRuntime *runtime = _runtime;
	if (NSThread.isMainThread) { [runtime close]; }
	else { dispatch_async(dispatch_get_main_queue(), ^{ [runtime close]; }); }
}
@end

@implementation PDGodotPresentation
@synthesize eventHandler = _eventHandler;
@synthesize lifecycleHandler = _lifecycleHandler;
@synthesize failureHandler = _failureHandler;

- (void)setEventHandler:(void (^)(NSString *))handler {
	_eventHandler = !self.invalidated && [self.owner isCurrentPresentation:self] ? [handler copy] : nil;
}

- (void)setLifecycleHandler:(void (^)(uint64_t, BOOL, BOOL))handler {
	_lifecycleHandler = !self.invalidated && [self.owner isCurrentPresentation:self] ? [handler copy] : nil;
}

- (void)setFailureHandler:(void (^)(void))handler {
	_failureHandler = !self.invalidated && [self.owner isCurrentPresentation:self] ? [handler copy] : nil;
}

- (uint64_t)lifecycleGeneration {
	if ([self.owner isCurrentPresentation:self]) { return [self.owner.ownedRuntime lifecycleGeneration]; }
	return [self.closedSnapshot[@"lifecycleGeneration"] longLongValue];
}

- (BOOL)sendDocument:(NSString *)document error:(NSError **)error {
	return [self sendDocument:document lifecycleGeneration:self.lifecycleGeneration error:error];
}

- (BOOL)sendDocument:(NSString *)document lifecycleGeneration:(uint64_t)generation error:(NSError **)error {
	if (![self.owner isCurrentPresentation:self] || generation != self.lifecycleGeneration) {
		return PDReject(error, @"The presentation handle or lifecycle generation is obsolete.");
	}
	return [self.owner.ownedRuntime enqueueDocument:document lifecycleGeneration:generation confirmReady:NO completion:nil error:error];
}

- (void)deliverDocument:(NSString *)document lifecycleGeneration:(uint64_t)generation
			confirmReady:(BOOL)confirmReady completion:(void (^)(BOOL))completion {
	NSAssert(NSThread.isMainThread, @"Native delivery belongs to the main thread.");
	if (![self.owner isCurrentPresentation:self] || generation != self.lifecycleGeneration ||
			![self.owner.ownedRuntime enqueueDocument:document lifecycleGeneration:generation confirmReady:confirmReady completion:completion error:nil]) {
		completion(NO);
	}
}

- (BOOL)confirmReady {
	return [self confirmReadyAtLifecycleGeneration:self.lifecycleGeneration];
}

- (BOOL)confirmReadyAtLifecycleGeneration:(uint64_t)generation {
	return [self.owner isCurrentPresentation:self] && generation == self.lifecycleGeneration && [self.owner.ownedRuntime confirmRetainedReady];
}

- (void)setForeground:(BOOL)foreground {
	if ([self.owner isCurrentPresentation:self]) { [self.owner.ownedRuntime setForeground:foreground]; }
}

- (void)close {
	if ([self.owner isCurrentPresentation:self]) { [self.owner.ownedRuntime leavePresentation]; }
}

- (void)closeWithCompletion:(void (^)(BOOL))completion {
	if (!NSThread.isMainThread) { return; }
	if (self.closedSnapshot) { completion([self.closedSnapshot[@"state"] isEqual:@"dormant"]); return; }
	if (self.closeCompletion) { completion(NO); return; }
	self.closeCompletion = completion;
	if ([self.owner isCurrentPresentation:self]) { [self close]; }
	else if (!self.owner) {
		self.closeCompletion = nil;
		completion(NO);
	}
}

- (BOOL)requestRendererDiagnostics {
	return [self.owner isCurrentPresentation:self] && [self.owner.ownedRuntime requestRendererDiagnostics];
}

- (NSDictionary<NSString *, id> *)snapshot {
	return self.closedSnapshot ?: (self.owner ? [self.owner snapshot] : @{});
}
@end
