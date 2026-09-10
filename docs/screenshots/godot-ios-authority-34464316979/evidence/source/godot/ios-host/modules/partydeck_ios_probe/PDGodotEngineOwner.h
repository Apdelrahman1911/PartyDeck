#pragma once

#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@class PDGodotPresentation;

// Source-coupled retained-engine qualification. All calls and event delivery
// belong to the native main thread. A dormant owner can issue a fresh handle;
// shutdown and any quarantine are terminal for this process.
@interface PDGodotEngineOwner : NSObject

- (nullable PDGodotPresentation *)createPresentationWithProjectPath:(NSString *)projectPath
														 packPath:(NSString *)packPath
													 launchDocument:(NSString *)launchDocument
															error:(NSError **)error;
- (void)setApplicationActive:(BOOL)active;
// Inactive foreground UI (for example a system alert) is not backgrounded.
- (void)setApplicationActive:(BOOL)active backgrounded:(BOOL)backgrounded;
- (void)shutdown;
- (NSDictionary<NSString *, id> *)snapshot;

@end

// A closed handle cannot mutate or receive events from a later presentation.
// Closing releases its renderer/authority lifetime, not the retained engine.
@interface PDGodotPresentation : NSObject

@property(nonatomic, readonly, copy) NSString *presentationID;
@property(nonatomic, readonly) uint64_t nativeGeneration;
@property(nonatomic, readonly) uint64_t lifecycleGeneration;
@property(nonatomic, readonly, nullable) UIViewController *viewController;
@property(nonatomic, copy, nullable) void (^eventHandler)(NSString *document);
@property(nonatomic, copy, nullable) void (^lifecycleHandler)(uint64_t generation, BOOL foreground, BOOL backgrounded);
@property(nonatomic, copy, nullable) void (^failureHandler)(void);

// BOOL reports bounded queue admission, not completed scene delivery.
- (BOOL)sendDocument:(NSString *)document error:(NSError **)error;
// Capture this epoch when queuing work; do not re-label old work at delivery.
- (BOOL)sendDocument:(NSString *)document lifecycleGeneration:(uint64_t)generation error:(NSError **)error;
// Completion reports actual native bridge delivery in the captured epoch.
// Ready is confirmed only after that delivery, never by queue admission.
- (void)deliverDocument:(NSString *)document lifecycleGeneration:(uint64_t)generation
			confirmReady:(BOOL)confirmReady completion:(void (^)(BOOL delivered))completion;
- (BOOL)confirmReady;
- (BOOL)confirmReadyAtLifecycleGeneration:(uint64_t)generation;
- (void)setForeground:(BOOL)foreground;
- (void)close;
- (void)closeWithCompletion:(void (^)(BOOL dormant))completion NS_SWIFT_NAME(close(completion:));
- (BOOL)requestRendererDiagnostics;
// Includes lifecycleGeneration (decimal string), nativeForeground (BOOL), and
// applicationBackgrounded (BOOL); these are native facts, separate from the
// common authority's foreground grant carried by a wire document.
- (NSDictionary<NSString *, id> *)snapshot;

@end

NS_ASSUME_NONNULL_END
