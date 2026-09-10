#pragma once

#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

// Internal, one-process qualification interface. Call every method on the main
// thread. It is not a shipping EmbeddedGameFactory or an iOS LibGodot API.
@interface PDGodotRuntime : NSObject

@property(nonatomic, readonly, nullable) UIViewController *viewController;
@property(nonatomic, copy, nullable) void (^eventHandler)(NSString *document);

// Accepts only trusted, recipient-projected launch documents. The scene/common
// bridge still validates GameView semantics; the host never owns game authority.
- (BOOL)prepareWithProjectPath:(NSString *)projectPath
					 packPath:(nullable NSString *)packPath
				 launchDocument:(NSString *)launchDocument
						 error:(NSError **)error;
- (BOOL)sendDocument:(NSString *)document error:(NSError **)error;
- (void)setForeground:(BOOL)foreground;
- (void)close;
- (NSDictionary<NSString *, id> *)snapshot;

// Read-only qualification channel for the shared renderer's actual control
// geometry/private-binding counts. One outstanding request, 16 KiB maximum;
// accepted sanitized observations appear in snapshot, never as authority input.
- (BOOL)requestRendererDiagnostics;

// Deliberately schedules a close into the real drawView nested run loop so the
// executable probe can verify deferred cleanup. Never used by a game renderer.
- (void)requestCloseDuringNextDrawForProbe;
- (void)requestCloseAfterSetupForProbe;

@end

NS_ASSUME_NONNULL_END
