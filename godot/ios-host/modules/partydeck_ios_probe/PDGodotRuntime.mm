// Source-coupled iOS experiment against the exact engine recorded in README.md.
// Real bootstrap, SceneTree, input, rendering and cleanup; one attempt/process.
#include "register_types.h"
#include "strict_json.h"
#import "PDGodotRuntime.h"

#include "core/config/engine.h"
#include "core/object/class_db.h"
#include "core/os/main_loop.h"
#include "core/os/os.h"
#include "main/main.h"

#import "drivers/apple_embedded/app_delegate_service.h"
#import "drivers/apple_embedded/display_server_apple_embedded.h"
#import "drivers/apple_embedded/godot_view_controller.h"
#import "drivers/apple_embedded/godot_view_renderer.h"
#import "drivers/apple_embedded/os_apple_embedded.h"
#import "platform/ios/godot_view_ios.h"

#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

extern int apple_embedded_main(int argc, char **argv);
extern void apple_embedded_finish();

static const NSUInteger PDCommandLimit = 65536;
static const NSUInteger PDEventLimit = 4096;
static const NSUInteger PDDiagnosticsLimit = 16384;
static const NSUInteger PDQueueCountLimit = 16;
static const NSUInteger PDQueueByteLimit = 262144;
static BOOL processConsumed = NO;
static NSUInteger processBootstrapCount = 0;
static PDGodotRuntime *activeRuntime = nil;

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
			@"coordinateSpace", @"foreground", @"viewport", @"handConcealed", @"selectedCount", @"privateFaceCount", @"privateLabelCount", @"controls" ]) ||
			!PDVersion(value[@"schemaVersion"]) || ![value[@"presentationId"] isEqual:presentationID] || ![value[@"presentationMode"] isEqual:mode] ||
			![value[@"coordinateSpace"] isEqual:@"root_viewport"] || !PDCounter(value[@"requestId"]) || !PDCounter(value[@"sequence"]) || !PDCounter(value[@"revision"]) ||
			!PDBoolean(value[@"foreground"]) || !PDBoolean(value[@"handConcealed"]) ||
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
		@"coordinateSpace": @"root_viewport", @"foreground": value[@"foreground"], @"handConcealed": value[@"handConcealed"],
		@"viewport": @{ @"width": @([viewport[@"width"] doubleValue]), @"height": @([viewport[@"height"] doubleValue]) },
		@"selectedCount": @([value[@"selectedCount"] intValue]), @"privateFaceCount": @([value[@"privateFaceCount"] intValue]),
		@"privateLabelCount": @([value[@"privateLabelCount"] intValue]), @"controls": safeControls };
}

@class PDGodotHostViewController;
@class PDGodotContainerViewController;
@class PDGuardedGodotView;

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
	NSMutableArray<NSString *> *_commands;
	NSMutableArray<NSDictionary<NSString *, id> *> *_events;
	NSUInteger _queuedBytes, _drawDepth, _engineDepth, _deliveryDepth, _drawCalls, _iterations;
	NSUInteger _cleanupCount, _cleanupDepth, _readyEvents, _exitEvents, _intentEvents, _rejectedEvents;
	NSUInteger _backgroundTransitions, _closeDuringDraw, _closeDuringInitialization, _coverUntilIteration, _privacyCoverCount;
	NSUInteger _foregroundGeneration;
	int64_t _diagnosticsRequests;
	NSUInteger _acceptedDiagnostics, _rejectedDiagnostics, _unansweredDiagnostics;
	double _displayScale;
	int _bootstrapExitCode, _setup2ErrorCode, _mainStartExitCode;
	BOOL _prepared, _bootstrapAttempted, _bootstrapSucceeded, _setup2Succeeded, _started;
	BOOL _foreground, _appliedForeground, _lifecycleApplied, _closeRequested, _closed, _quarantined;
	BOOL _drainScheduled, _eventTerminal, _readySeen, _closeOnNextDraw, _pendingForegroundLoss, _closeAfterSetup;
	BOOL _idleTimerPolicyCaptured, _idleTimerPolicyRestored, _previousIdleTimerDisabled, _idleTimerDisabledAfterSetup;
}
- (void)startInContainer;
- (BOOL)canDraw;
- (BOOL)canReceiveInput;
- (void)beginDraw;
- (void)endDraw;
- (void)iterate;
- (NSString *)launchDocument;
- (BOOL)receiveRendererDocument:(NSString *)document;
- (BOOL)receiveRendererDiagnostics:(NSString *)document;
- (void)scheduleDrain;
- (void)drain;
- (void)coverPrivateSurface;
@end

// drawView is implemented, but not publicly declared, in the exact GDTView
// source inspected by source_audit.py. This declaration records that coupling.
@interface GDTView (PDInspectedPrivateDrawSelector)
- (void)drawView;
@end

@interface PDGuardedGodotView : GDTViewIOS
@property(nonatomic, weak) PDGodotRuntime *runtime;
@end

@implementation PDGuardedGodotView
- (void)drawView {
	PDGodotRuntime *runtime = self.runtime;
	if (![runtime canDraw]) {
		return;
	}
	[runtime beginDraw];
	[super drawView];
	[runtime endDraw];
}
- (void)startRendering {
	if ([self.runtime canDraw]) {
		[super startRendering];
	}
}
- (void)layoutSubviews {
	if (OS::get_singleton()) {
		[super layoutSubviews];
	}
}
- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
	if ([self.runtime canReceiveInput]) {
		[super touchesBegan:touches withEvent:event];
	}
}
- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
	if ([self.runtime canReceiveInput]) {
		[super touchesMoved:touches withEvent:event];
	}
}
- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
	if ([self.runtime canReceiveInput]) {
		[super touchesEnded:touches withEvent:event];
	}
}
- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
	if ([self.runtime canReceiveInput]) {
		[super touchesCancelled:touches withEvent:event];
	}
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
	[self.runtime startInContainer];
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
- (instancetype)init {
	self = [super init];
	if (self) {
		_state = @"idle";
		_foreground = YES;
		_bootstrapExitCode = _setup2ErrorCode = _mainStartExitCode = -1;
		_commands = [NSMutableArray new];
		_events = [NSMutableArray new];
	}
	return self;
}

- (UIViewController *)viewController { return _container; }

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
		if (!_foreground || _pendingForegroundLoss) {
			[self coverPrivateSurface];
		}
		// The actual setupProjectData stage, with its Error result checked.
		// The attached native surface exists before any display-server setup.
		_setup2ErrorCode = Main::setup2(false);
		_setup2Succeeded = _setup2ErrorCode == OK;
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
	}
	[self scheduleDrain];
}

- (BOOL)canDraw {
	return _started && _foreground && !_pendingForegroundLoss && !_closeRequested && !_closed && !_quarantined && _engineDepth == 0;
}
- (BOOL)canReceiveInput {
	return _started && _foreground && !_closeRequested && !_closed && !_quarantined && DisplayServer::get_singleton();
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
- (void)endDraw {
	--_drawDepth;
	// drawView has returned after presenting its layer. A resumed surface is
	// uncovered only after concealment commands and a subsequent real frame.
	if (_privacyCover && _foreground && _appliedForeground && !_pendingForegroundLoss && !_closeRequested &&
			_iterations >= _coverUntilIteration) {
		[_privacyCover removeFromSuperview];
		_privacyCover = nil;
		_observedView.accessibilityElementsHidden = NO;
	}
	if (_closeRequested || _events.count || _commands.count || _diagnosticsRequest || _pendingForegroundLoss || !_lifecycleApplied || _appliedForeground != _foreground) {
		[self scheduleDrain];
	}
}
- (void)iterate {
	if (![self canDraw]) {
		return;
	}
	++_engineDepth;
	BOOL requestedQuit = OS_AppleEmbedded::get_singleton()->iterate();
	++_iterations;
	--_engineDepth;
	if (requestedQuit) {
		[self close];
	}
}
- (NSString *)launchDocument { return _closeRequested ? nil : _launchDocument; }

- (BOOL)receiveRendererDocument:(NSString *)document {
	if (_closeRequested || _eventTerminal || _closed) {
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
	if ([type isEqual:@"intent"] && (!_readySeen || !_foreground || _pendingForegroundLoss || ![event[@"expectedRevision"] isEqual:_revision])) {
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
	if (!NSThread.isMainThread || !_prepared || _closeRequested || _closed) {
		return PDReject(error, @"The presentation is closed or not owned by the calling thread.");
	}
	NSDictionary *command = PDObject(document, PDCommandLimit);
	if (!PDVersion(command[@"protocolVersion"]) || ![command[@"presentationId"] isEqual:_presentationID]) {
		return PDReject(error, @"The command envelope is invalid.");
	}
	if ([command[@"type"] isEqual:@"close"] && PDKeys(command, @[ @"protocolVersion", @"type", @"presentationId" ])) {
		[self close];
		return YES;
	}
	if ([command[@"type"] isEqual:@"foreground"] && PDKeys(command, @[ @"protocolVersion", @"type", @"presentationId", @"isForeground" ]) && PDBoolean(command[@"isForeground"])) {
		[self setForeground:[command[@"isForeground"] boolValue]];
		return YES;
	}
	if (![command[@"type"] isEqual:@"view"] || !PDKeys(command, @[ @"protocolVersion", @"type", @"presentationId", @"revision", @"schemaId", @"payload" ]) ||
			!PDCounter(command[@"revision"]) || PDCompareCounter(command[@"revision"], _revision) != NSOrderedDescending ||
			![command[@"schemaId"] isEqual:@"last-light-view-v1"] || !PDPayload(command[@"payload"])) {
		return PDReject(error, @"The command is malformed, stale, or unsupported.");
	}
	NSUInteger bytes = [document lengthOfBytesUsingEncoding:NSUTF8StringEncoding];
	if (_commands.count >= PDQueueCountLimit || _queuedBytes + bytes > PDQueueByteLimit) {
		return PDReject(error, @"The bounded command queue is full.");
	}
	_revision = command[@"revision"];
	_rendererDiagnostics = nil;
	_queuedBytes += bytes;
	[_commands addObject:[document copy]];
	[self scheduleDrain];
	return YES;
}

- (void)setForeground:(BOOL)foreground {
	if (!NSThread.isMainThread || _closeRequested || _closed) {
		return;
	}
	_foreground = foreground;
	_rendererDiagnostics = nil;
	if (!foreground) {
		++_foregroundGeneration;
		_pendingForegroundLoss = YES;
		_coverUntilIteration = _iterations + 1;
		[self coverPrivateSurface];
		[_observedView stopRendering];
	}
	if (!_bootstrapAttempted && foreground && _container.viewIfLoaded.window) {
		[self startInContainer];
	}
	[self scheduleDrain];
}

- (void)coverPrivateSurface {
	if (!_container.isViewLoaded) {
		return;
	}
	if (!_privacyCover) {
		++_privacyCoverCount;
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
	_state = @"closing";
	_closeDuringDraw += _drawDepth > 0 ? 1 : 0;
	_closeDuringInitialization += _engineDepth > 0 && !_started ? 1 : 0;
	[self coverPrivateSurface];
	[_observedView stopRendering];
	_observedView.userInteractionEnabled = NO;
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
	if (!NSThread.isMainThread || !_started || !_readySeen || _closeRequested || _closed || _diagnosticsRequest || _diagnosticsRequests == INT64_MAX) {
		return NO;
	}
	_diagnosticsRequest = @(++_diagnosticsRequests).stringValue;
	[self scheduleDrain];
	return YES;
}

- (BOOL)receiveRendererDiagnostics:(NSString *)document {
	if (!_diagnosticsRequest || _closeRequested || _closed) {
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

- (void)emitCommand:(NSDictionary *)command {
	if (!bridge || !_started) {
		return;
	}
	NSData *bytes = [NSJSONSerialization dataWithJSONObject:command options:0 error:nil];
	NSString *document = [[NSString alloc] initWithData:bytes encoding:NSUTF8StringEncoding];
	++_engineDepth;
	bridge->emit_signal("command_received", String::utf8(document.UTF8String));
	--_engineDepth;
}

- (void)drain {
	// Dispatch blocks can run inside GDTView's nested run loop. Do not requeue
	// in a busy loop there; endDraw/startInContainer arrange a later safe drain.
	if (_drawDepth || _engineDepth || _deliveryDepth || _closed) {
		return;
	}
	if (_closeRequested) {
		[_commands removeAllObjects];
		[_events removeAllObjects];
		_diagnosticsRequest = nil;
		_rendererDiagnostics = nil;
		_queuedBytes = 0;
		if (_started) {
			[self emitCommand:@{ @"protocolVersion": @1, @"type": @"close", @"presentationId": _presentationID }];
		}
		[_observedView stopRendering];
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
		}
		_launchDocument = nil;
		// Restore even for cancellation before bootstrap or quarantined setup
		// failure. This UIKit property does not depend on a surviving engine.
		if (_idleTimerPolicyCaptured) {
			UIApplication.sharedApplication.idleTimerDisabled = _previousIdleTimerDisabled;
			_idleTimerPolicyRestored = UIApplication.sharedApplication.idleTimerDisabled == _previousIdleTimerDisabled;
		}
		[_privacyCover removeFromSuperview];
		_privacyCover = nil;
		self.eventHandler = nil;
		_closed = YES;
		_state = _failure ? @"failed" : @"closed";
		return;
	}
	if (!_started) {
		return;
	}
	// A false->true pair may arrive before this drain. Always deliver the loss
	// first so private presentation state is concealed, then apply the latest
	// foreground state. Clearing before callbacks preserves a reentrant loss.
	if (_pendingForegroundLoss) {
		_pendingForegroundLoss = NO;
		[self emitCommand:@{ @"protocolVersion": @1, @"type": @"foreground", @"presentationId": _presentationID, @"isForeground": @NO }];
		++_engineDepth;
		OS_AppleEmbedded::get_singleton()->on_enter_background();
		--_engineDepth;
		++_backgroundTransitions;
		_appliedForeground = NO;
		_lifecycleApplied = YES;
	}
	if (!_lifecycleApplied || _appliedForeground != _foreground) {
		[self emitCommand:@{ @"protocolVersion": @1, @"type": @"foreground", @"presentationId": _presentationID, @"isForeground": @(_foreground) }];
		++_engineDepth;
		if (_foreground) {
			OS_AppleEmbedded::get_singleton()->on_exit_background();
		} else {
			++_backgroundTransitions;
			OS_AppleEmbedded::get_singleton()->on_enter_background();
		}
		--_engineDepth;
		_appliedForeground = _foreground;
		_lifecycleApplied = YES;
		if (_foreground) {
			[_observedView startRendering];
		}
	}
	_state = _foreground ? @"running" : @"paused";
	while (_commands.count && !_closeRequested) {
		NSString *document = _commands.firstObject;
		[_commands removeObjectAtIndex:0];
		_queuedBytes -= [document lengthOfBytesUsingEncoding:NSUTF8StringEncoding];
		++_engineDepth;
		bridge->emit_signal("command_received", String::utf8(document.UTF8String));
		--_engineDepth;
	}
	while (_events.count && !_closeRequested) {
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
			[self close];
		}
	}
	if (_diagnosticsRequest && !_commands.count && !_events.count && !_closeRequested && !_pendingForegroundLoss && _appliedForeground == _foreground) {
		// The shared renderer answers this read-only request synchronously. Do
		// not query between an accepted event and its queued replacement view.
		NSString *request = _diagnosticsRequest;
		++_engineDepth;
		bridge->emit_signal("diagnostics_requested", String::utf8(request.UTF8String));
		--_engineDepth;
		if (_diagnosticsRequest) {
			++_unansweredDiagnostics;
			_diagnosticsRequest = nil;
		}
	}
	if (_closeRequested || _events.count || _commands.count || _diagnosticsRequest || _pendingForegroundLoss || !_lifecycleApplied || _appliedForeground != _foreground) {
		[self scheduleDrain];
	}
}

- (NSDictionary<NSString *, id> *)snapshot {
	NSAssert(NSThread.isMainThread, @"Probe observations belong to the native main thread.");
	return @{
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
	};
}
@end
