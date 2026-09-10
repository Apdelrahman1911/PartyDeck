#import <Foundation/NSArray.h>
#import <Foundation/NSDictionary.h>
#import <Foundation/NSError.h>
#import <Foundation/NSObject.h>
#import <Foundation/NSSet.h>
#import <Foundation/NSString.h>
#import <Foundation/NSValue.h>

@class PDGBBridgeDecisionAccepted, PDGBBridgeDecisionRejected, PDGBBridgeInputAction, PDGBBridgeInputAdvanceRound, PDGBBridgeInputExitRequested, PDGBBridgeInputFailed, PDGBBridgeInputReady, PDGBBridgeInputReturnToLobby, PDGBBridgeRejection, PDGBCoreAvailableActions, PDGBCoreAvailableActionsCompanion, PDGBCoreCard, PDGBCoreCardCompanion, PDGBCoreCardRank, PDGBCoreCardRankCompanion, PDGBCoreGamePhase, PDGBCoreGamePhaseCompanion, PDGBCoreGameRejection, PDGBCoreGameRejectionCompanion, PDGBCoreGameView, PDGBCoreGameViewCompanion, PDGBCorePlayerIdentity, PDGBCorePlayerIdentityCompanion, PDGBCorePlayerView, PDGBCorePlayerViewCompanion, PDGBCorePublicClaim, PDGBCorePublicClaimCompanion, PDGBCoreRoundOutcome, PDGBCoreRoundOutcomeCompanion, PDGBGamesEngineCommandSetForeground, PDGBGamesEngineCommandShowView, PDGBGamesEngineEvent, PDGBGamesEngineFailure, PDGBGamesEngineLaunch, PDGBGamesEnginePayload, PDGBIosQualificationAuthority, PDGBIosQualificationFactory, PDGBIosQualificationLifecycle, PDGBIosQualificationOutcome, PDGBIosQualificationPhase, PDGBIosQualificationRandomness, PDGBIosQualificationResult, PDGBIosQualificationStatus, PDGBKotlinArray<T>, PDGBKotlinByteArray, PDGBKotlinByteIterator, PDGBKotlinEnum<E>, PDGBKotlinEnumCompanion, PDGBKotlinException, PDGBKotlinIllegalArgumentException, PDGBKotlinNothing, PDGBKotlinRandom, PDGBKotlinRandomDefault, PDGBKotlinRuntimeException, PDGBKotlinThrowable, PDGBKotlinx_serialization_coreSerialKind, PDGBKotlinx_serialization_coreSerializersModule, PDGBLastLightWireCodec, PDGBPresentationControls, PDGBPresentationControlsCompanion, PDGBPresentationMode, PDGBPresentationPreferences, PDGBPresentationSnapshot, PDGBPresentationSnapshotCompanion, PDGBQualificationStep, PDGBRendererIntentAdvanceRound, PDGBRendererIntentChallenge, PDGBRendererIntentPlay, PDGBRendererIntentReturnToLobby;

@protocol PDGBBridgeDecision, PDGBBridgeInput, PDGBCoreGameAction, PDGBGamesEngineCommand, PDGBGamesEngineEventBody, PDGBKotlinAnnotation, PDGBKotlinComparable, PDGBKotlinIterator, PDGBKotlinKAnnotatedElement, PDGBKotlinKClass, PDGBKotlinKClassifier, PDGBKotlinKDeclarationContainer, PDGBKotlinx_serialization_coreCompositeDecoder, PDGBKotlinx_serialization_coreCompositeEncoder, PDGBKotlinx_serialization_coreDecoder, PDGBKotlinx_serialization_coreDeserializationStrategy, PDGBKotlinx_serialization_coreEncoder, PDGBKotlinx_serialization_coreKSerializer, PDGBKotlinx_serialization_coreSerialDescriptor, PDGBKotlinx_serialization_coreSerializationStrategy, PDGBKotlinx_serialization_coreSerializersModuleCollector, PDGBRendererIntent;

NS_ASSUME_NONNULL_BEGIN
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunknown-warning-option"
#pragma clang diagnostic ignored "-Wincompatible-property-type"
#pragma clang diagnostic ignored "-Wnullability"

#pragma push_macro("_Nullable_result")
#if !__has_feature(nullability_nullable_result)
#undef _Nullable_result
#define _Nullable_result _Nullable
#endif

__attribute__((swift_name("KotlinBase")))
@interface PDGBBase : NSObject
- (instancetype)init __attribute__((unavailable));
+ (instancetype)new __attribute__((unavailable));
+ (void)initialize __attribute__((objc_requires_super));
@end

@interface PDGBBase (PDGBBaseCopying) <NSCopying>
@end

__attribute__((swift_name("KotlinMutableSet")))
@interface PDGBMutableSet<ObjectType> : NSMutableSet<ObjectType>
@end

__attribute__((swift_name("KotlinMutableDictionary")))
@interface PDGBMutableDictionary<KeyType, ObjectType> : NSMutableDictionary<KeyType, ObjectType>
@end

@interface NSError (NSErrorPDGBKotlinException)
@property (readonly) id _Nullable kotlinException;
@end

__attribute__((swift_name("KotlinNumber")))
@interface PDGBNumber : NSNumber
- (instancetype)initWithChar:(char)value __attribute__((unavailable));
- (instancetype)initWithUnsignedChar:(unsigned char)value __attribute__((unavailable));
- (instancetype)initWithShort:(short)value __attribute__((unavailable));
- (instancetype)initWithUnsignedShort:(unsigned short)value __attribute__((unavailable));
- (instancetype)initWithInt:(int)value __attribute__((unavailable));
- (instancetype)initWithUnsignedInt:(unsigned int)value __attribute__((unavailable));
- (instancetype)initWithLong:(long)value __attribute__((unavailable));
- (instancetype)initWithUnsignedLong:(unsigned long)value __attribute__((unavailable));
- (instancetype)initWithLongLong:(long long)value __attribute__((unavailable));
- (instancetype)initWithUnsignedLongLong:(unsigned long long)value __attribute__((unavailable));
- (instancetype)initWithFloat:(float)value __attribute__((unavailable));
- (instancetype)initWithDouble:(double)value __attribute__((unavailable));
- (instancetype)initWithBool:(BOOL)value __attribute__((unavailable));
- (instancetype)initWithInteger:(NSInteger)value __attribute__((unavailable));
- (instancetype)initWithUnsignedInteger:(NSUInteger)value __attribute__((unavailable));
+ (instancetype)numberWithChar:(char)value __attribute__((unavailable));
+ (instancetype)numberWithUnsignedChar:(unsigned char)value __attribute__((unavailable));
+ (instancetype)numberWithShort:(short)value __attribute__((unavailable));
+ (instancetype)numberWithUnsignedShort:(unsigned short)value __attribute__((unavailable));
+ (instancetype)numberWithInt:(int)value __attribute__((unavailable));
+ (instancetype)numberWithUnsignedInt:(unsigned int)value __attribute__((unavailable));
+ (instancetype)numberWithLong:(long)value __attribute__((unavailable));
+ (instancetype)numberWithUnsignedLong:(unsigned long)value __attribute__((unavailable));
+ (instancetype)numberWithLongLong:(long long)value __attribute__((unavailable));
+ (instancetype)numberWithUnsignedLongLong:(unsigned long long)value __attribute__((unavailable));
+ (instancetype)numberWithFloat:(float)value __attribute__((unavailable));
+ (instancetype)numberWithDouble:(double)value __attribute__((unavailable));
+ (instancetype)numberWithBool:(BOOL)value __attribute__((unavailable));
+ (instancetype)numberWithInteger:(NSInteger)value __attribute__((unavailable));
+ (instancetype)numberWithUnsignedInteger:(NSUInteger)value __attribute__((unavailable));
@end

__attribute__((swift_name("KotlinByte")))
@interface PDGBByte : PDGBNumber
- (instancetype)initWithChar:(char)value;
+ (instancetype)numberWithChar:(char)value;
@end

__attribute__((swift_name("KotlinUByte")))
@interface PDGBUByte : PDGBNumber
- (instancetype)initWithUnsignedChar:(unsigned char)value;
+ (instancetype)numberWithUnsignedChar:(unsigned char)value;
@end

__attribute__((swift_name("KotlinShort")))
@interface PDGBShort : PDGBNumber
- (instancetype)initWithShort:(short)value;
+ (instancetype)numberWithShort:(short)value;
@end

__attribute__((swift_name("KotlinUShort")))
@interface PDGBUShort : PDGBNumber
- (instancetype)initWithUnsignedShort:(unsigned short)value;
+ (instancetype)numberWithUnsignedShort:(unsigned short)value;
@end

__attribute__((swift_name("KotlinInt")))
@interface PDGBInt : PDGBNumber
- (instancetype)initWithInt:(int)value;
+ (instancetype)numberWithInt:(int)value;
@end

__attribute__((swift_name("KotlinUInt")))
@interface PDGBUInt : PDGBNumber
- (instancetype)initWithUnsignedInt:(unsigned int)value;
+ (instancetype)numberWithUnsignedInt:(unsigned int)value;
@end

__attribute__((swift_name("KotlinLong")))
@interface PDGBLong : PDGBNumber
- (instancetype)initWithLongLong:(long long)value;
+ (instancetype)numberWithLongLong:(long long)value;
@end

__attribute__((swift_name("KotlinULong")))
@interface PDGBULong : PDGBNumber
- (instancetype)initWithUnsignedLongLong:(unsigned long long)value;
+ (instancetype)numberWithUnsignedLongLong:(unsigned long long)value;
@end

__attribute__((swift_name("KotlinFloat")))
@interface PDGBFloat : PDGBNumber
- (instancetype)initWithFloat:(float)value;
+ (instancetype)numberWithFloat:(float)value;
@end

__attribute__((swift_name("KotlinDouble")))
@interface PDGBDouble : PDGBNumber
- (instancetype)initWithDouble:(double)value;
+ (instancetype)numberWithDouble:(double)value;
@end

__attribute__((swift_name("KotlinBoolean")))
@interface PDGBBoolean : PDGBNumber
- (instancetype)initWithBool:(BOOL)value;
+ (instancetype)numberWithBool:(BOOL)value;
@end

__attribute__((swift_name("BridgeDecision")))
@protocol PDGBBridgeDecision
@required
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeDecisionAccepted")))
@interface PDGBBridgeDecisionAccepted : PDGBBase <PDGBBridgeDecision>
- (instancetype)initWithInput:(id<PDGBBridgeInput>)input __attribute__((swift_name("init(input:)"))) __attribute__((objc_designated_initializer));
- (PDGBBridgeDecisionAccepted *)doCopyInput:(id<PDGBBridgeInput>)input __attribute__((swift_name("doCopy(input:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) id<PDGBBridgeInput> input __attribute__((swift_name("input")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeDecisionRejected")))
@interface PDGBBridgeDecisionRejected : PDGBBase <PDGBBridgeDecision>
- (instancetype)initWithReason:(PDGBBridgeRejection *)reason __attribute__((swift_name("init(reason:)"))) __attribute__((objc_designated_initializer));
- (PDGBBridgeDecisionRejected *)doCopyReason:(PDGBBridgeRejection *)reason __attribute__((swift_name("doCopy(reason:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) PDGBBridgeRejection *reason __attribute__((swift_name("reason")));
@end

__attribute__((swift_name("KotlinThrowable")))
@interface PDGBKotlinThrowable : PDGBBase
- (instancetype)init __attribute__((swift_name("init()"))) __attribute__((objc_designated_initializer));
+ (instancetype)new __attribute__((availability(swift, unavailable, message="use object initializers instead")));
- (instancetype)initWithMessage:(NSString * _Nullable)message __attribute__((swift_name("init(message:)"))) __attribute__((objc_designated_initializer));
- (instancetype)initWithCause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(cause:)"))) __attribute__((objc_designated_initializer));
- (instancetype)initWithMessage:(NSString * _Nullable)message cause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(message:cause:)"))) __attribute__((objc_designated_initializer));

/**
 * @note annotations
 *   kotlin.experimental.ExperimentalNativeApi
*/
- (PDGBKotlinArray<NSString *> *)getStackTrace __attribute__((swift_name("getStackTrace()")));
- (void)printStackTrace __attribute__((swift_name("printStackTrace()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) PDGBKotlinThrowable * _Nullable cause __attribute__((swift_name("cause")));
@property (readonly) NSString * _Nullable message __attribute__((swift_name("message")));
- (NSError *)asError __attribute__((swift_name("asError()")));
@end

__attribute__((swift_name("KotlinException")))
@interface PDGBKotlinException : PDGBKotlinThrowable
- (instancetype)init __attribute__((swift_name("init()"))) __attribute__((objc_designated_initializer));
+ (instancetype)new __attribute__((availability(swift, unavailable, message="use object initializers instead")));
- (instancetype)initWithMessage:(NSString * _Nullable)message __attribute__((swift_name("init(message:)"))) __attribute__((objc_designated_initializer));
- (instancetype)initWithCause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(cause:)"))) __attribute__((objc_designated_initializer));
- (instancetype)initWithMessage:(NSString * _Nullable)message cause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(message:cause:)"))) __attribute__((objc_designated_initializer));
@end

__attribute__((swift_name("KotlinRuntimeException")))
@interface PDGBKotlinRuntimeException : PDGBKotlinException
- (instancetype)init __attribute__((swift_name("init()"))) __attribute__((objc_designated_initializer));
+ (instancetype)new __attribute__((availability(swift, unavailable, message="use object initializers instead")));
- (instancetype)initWithMessage:(NSString * _Nullable)message __attribute__((swift_name("init(message:)"))) __attribute__((objc_designated_initializer));
- (instancetype)initWithCause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(cause:)"))) __attribute__((objc_designated_initializer));
- (instancetype)initWithMessage:(NSString * _Nullable)message cause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(message:cause:)"))) __attribute__((objc_designated_initializer));
@end

__attribute__((swift_name("KotlinIllegalArgumentException")))
@interface PDGBKotlinIllegalArgumentException : PDGBKotlinRuntimeException
- (instancetype)init __attribute__((swift_name("init()"))) __attribute__((objc_designated_initializer));
+ (instancetype)new __attribute__((availability(swift, unavailable, message="use object initializers instead")));
- (instancetype)initWithMessage:(NSString * _Nullable)message __attribute__((swift_name("init(message:)"))) __attribute__((objc_designated_initializer));
- (instancetype)initWithCause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(cause:)"))) __attribute__((objc_designated_initializer));
- (instancetype)initWithMessage:(NSString * _Nullable)message cause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(message:cause:)"))) __attribute__((objc_designated_initializer));
@end


/** A schema error contains a bounded explanation, never the rejected private document. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeFormatException")))
@interface PDGBBridgeFormatException : PDGBKotlinIllegalArgumentException
- (instancetype)initWithMessage:(NSString *)message __attribute__((swift_name("init(message:)"))) __attribute__((objc_designated_initializer));
- (instancetype)init __attribute__((swift_name("init()"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
+ (instancetype)new __attribute__((unavailable));
- (instancetype)initWithCause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(cause:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
- (instancetype)initWithMessage:(NSString * _Nullable)message cause:(PDGBKotlinThrowable * _Nullable)cause __attribute__((swift_name("init(message:cause:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@end

__attribute__((swift_name("BridgeInput")))
@protocol PDGBBridgeInput
@required
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeInputAction")))
@interface PDGBBridgeInputAction : PDGBBase <PDGBBridgeInput>
- (instancetype)initWithAction:(id<PDGBCoreGameAction>)action __attribute__((swift_name("init(action:)"))) __attribute__((objc_designated_initializer));
- (PDGBBridgeInputAction *)doCopyAction:(id<PDGBCoreGameAction>)action __attribute__((swift_name("doCopy(action:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) id<PDGBCoreGameAction> action __attribute__((swift_name("action")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeInputAdvanceRound")))
@interface PDGBBridgeInputAdvanceRound : PDGBBase <PDGBBridgeInput>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)advanceRound __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBBridgeInputAdvanceRound *shared __attribute__((swift_name("shared")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeInputExitRequested")))
@interface PDGBBridgeInputExitRequested : PDGBBase <PDGBBridgeInput>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)exitRequested __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBBridgeInputExitRequested *shared __attribute__((swift_name("shared")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeInputFailed")))
@interface PDGBBridgeInputFailed : PDGBBase <PDGBBridgeInput>
- (instancetype)initWithReason:(PDGBGamesEngineFailure *)reason __attribute__((swift_name("init(reason:)"))) __attribute__((objc_designated_initializer));
- (PDGBBridgeInputFailed *)doCopyReason:(PDGBGamesEngineFailure *)reason __attribute__((swift_name("doCopy(reason:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) PDGBGamesEngineFailure *reason __attribute__((swift_name("reason")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeInputReady")))
@interface PDGBBridgeInputReady : PDGBBase <PDGBBridgeInput>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)ready __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBBridgeInputReady *shared __attribute__((swift_name("shared")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeInputReturnToLobby")))
@interface PDGBBridgeInputReturnToLobby : PDGBBase <PDGBBridgeInput>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)returnToLobby __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBBridgeInputReturnToLobby *shared __attribute__((swift_name("shared")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@end

__attribute__((swift_name("KotlinComparable")))
@protocol PDGBKotlinComparable
@required
- (int32_t)compareToOther:(id _Nullable)other __attribute__((swift_name("compareTo(other:)")));
@end

__attribute__((swift_name("KotlinEnum")))
@interface PDGBKotlinEnum<E> : PDGBBase <PDGBKotlinComparable>
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBKotlinEnumCompanion *companion __attribute__((swift_name("companion")));
- (int32_t)compareToOther:(E)other __attribute__((swift_name("compareTo(other:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) NSString *name __attribute__((swift_name("name")));
@property (readonly) int32_t ordinal __attribute__((swift_name("ordinal")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("BridgeRejection")))
@interface PDGBBridgeRejection : PDGBKotlinEnum<PDGBBridgeRejection *>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly) PDGBBridgeRejection *invalidDocument __attribute__((swift_name("invalidDocument")));
@property (class, readonly) PDGBBridgeRejection *closed __attribute__((swift_name("closed")));
@property (class, readonly) PDGBBridgeRejection *wrongPresentation __attribute__((swift_name("wrongPresentation")));
@property (class, readonly) PDGBBridgeRejection *unsupportedProtocol __attribute__((swift_name("unsupportedProtocol")));
@property (class, readonly) PDGBBridgeRejection *replayedEvent __attribute__((swift_name("replayedEvent")));
@property (class, readonly) PDGBBridgeRejection *notReady __attribute__((swift_name("notReady")));
@property (class, readonly) PDGBBridgeRejection *alreadyReady __attribute__((swift_name("alreadyReady")));
@property (class, readonly) PDGBBridgeRejection *staleRevision __attribute__((swift_name("staleRevision")));
@property (class, readonly) PDGBBridgeRejection *notForeground __attribute__((swift_name("notForeground")));
@property (class, readonly) PDGBBridgeRejection *actionUnavailable __attribute__((swift_name("actionUnavailable")));
@property (class, readonly) PDGBBridgeRejection *invalidSelection __attribute__((swift_name("invalidSelection")));
+ (PDGBKotlinArray<PDGBBridgeRejection *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBBridgeRejection *> *entries __attribute__((swift_name("entries")));
@end


/**
 * Swift-friendly ownership of a real qualification driver, without exposing its domain types.
 * The native host serializes calls, bounds/delivers queues, and discards this facade on close.
 * Re-entry creates a new facade and presentation ID. This is not a network/session authority.
 */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("IosQualificationAuthority")))
@interface PDGBIosQualificationAuthority : PDGBBase

/** Existing bounded safe-view opponent policy; no game strategy or rules live here.
 *
 * @note This method converts instances of Exception to errors.
 * Other uncaught Kotlin exceptions are fatal.
*/
- (PDGBIosQualificationResult * _Nullable)advanceOtherPlayersAndReturnError:(NSError * _Nullable * _Nullable)error __attribute__((swift_name("advanceOtherPlayers()")));

/** Terminal and idempotent; returned close documents may safely be delivered again.
 *
 * @note This method converts instances of Exception to errors.
 * Other uncaught Kotlin exceptions are fatal.
*/
- (PDGBIosQualificationResult * _Nullable)closeAndReturnError:(NSError * _Nullable * _Nullable)error __attribute__((swift_name("close()")));

/** Ordinary malformed/stale/replayed/paused input returns REJECTED, without a refresh.
 *
 * @note This method converts instances of Exception to errors.
 * Other uncaught Kotlin exceptions are fatal.
*/
- (PDGBIosQualificationResult * _Nullable)handleRendererEventDocument:(NSString *)document error:(NSError * _Nullable * _Nullable)error __attribute__((swift_name("handleRendererEvent(document:)")));

/** Reconcile pending UI only when the native owner chooses to do so after a rejection.
 *
 * @note This method converts instances of Exception to errors.
 * Other uncaught Kotlin exceptions are fatal.
*/
- (PDGBIosQualificationResult * _Nullable)refreshViewAndReturnError:(NSError * _Nullable * _Nullable)error __attribute__((swift_name("refreshView()")));

/**
 * @note This method converts instances of Exception to errors.
 * Other uncaught Kotlin exceptions are fatal.
*/
- (PDGBIosQualificationResult * _Nullable)setForegroundIsForeground:(BOOL)isForeground error:(NSError * _Nullable * _Nullable)error __attribute__((swift_name("setForeground(isForeground:)")));
- (PDGBIosQualificationStatus *)status __attribute__((swift_name("status()")));

/** Initial safe launch, supplied once to native preparation. Empty after terminal close. */
@property (readonly) NSString *launchDocument __attribute__((swift_name("launchDocument")));
@property (readonly) PDGBIosQualificationRandomness *randomness __attribute__((swift_name("randomness")));
@end


/** All arguments are explicit so Swift never needs Kotlin default-argument overloads. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("IosQualificationFactory")))
@interface PDGBIosQualificationFactory : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));

/** All arguments are explicit so Swift never needs Kotlin default-argument overloads. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)iosQualificationFactory __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBIosQualificationFactory *shared __attribute__((swift_name("shared")));

/**
 * @note This method converts instances of Exception to errors.
 * Other uncaught Kotlin exceptions are fatal.
*/
- (PDGBIosQualificationAuthority * _Nullable)createPresentationId:(NSString *)presentationId mode:(PDGBPresentationMode *)mode randomness:(PDGBIosQualificationRandomness *)randomness reduceMotion:(BOOL)reduceMotion soundEnabled:(BOOL)soundEnabled textScale:(double)textScale error:(NSError * _Nullable * _Nullable)error __attribute__((swift_name("create(presentationId:mode:randomness:reduceMotion:soundEnabled:textScale:)")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("IosQualificationLifecycle")))
@interface PDGBIosQualificationLifecycle : PDGBKotlinEnum<PDGBIosQualificationLifecycle *>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly) PDGBIosQualificationLifecycle *waitingForReady __attribute__((swift_name("waitingForReady")));
@property (class, readonly) PDGBIosQualificationLifecycle *ready __attribute__((swift_name("ready")));
@property (class, readonly) PDGBIosQualificationLifecycle *closed __attribute__((swift_name("closed")));
+ (PDGBKotlinArray<PDGBIosQualificationLifecycle *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBIosQualificationLifecycle *> *entries __attribute__((swift_name("entries")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("IosQualificationOutcome")))
@interface PDGBIosQualificationOutcome : PDGBKotlinEnum<PDGBIosQualificationOutcome *>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly) PDGBIosQualificationOutcome *accepted __attribute__((swift_name("accepted")));
@property (class, readonly) PDGBIosQualificationOutcome *rejected __attribute__((swift_name("rejected")));
@property (class, readonly) PDGBIosQualificationOutcome *authorityRejected __attribute__((swift_name("authorityRejected")));
@property (class, readonly) PDGBIosQualificationOutcome *noChange __attribute__((swift_name("noChange")));
@property (class, readonly) PDGBIosQualificationOutcome *foregroundChanged __attribute__((swift_name("foregroundChanged")));
@property (class, readonly) PDGBIosQualificationOutcome *viewRefreshed __attribute__((swift_name("viewRefreshed")));
@property (class, readonly) PDGBIosQualificationOutcome *returnToLobby __attribute__((swift_name("returnToLobby")));
@property (class, readonly) PDGBIosQualificationOutcome *exitRequested __attribute__((swift_name("exitRequested")));
@property (class, readonly) PDGBIosQualificationOutcome *rendererFailed __attribute__((swift_name("rendererFailed")));
@property (class, readonly) PDGBIosQualificationOutcome *closed __attribute__((swift_name("closed")));
+ (PDGBKotlinArray<PDGBIosQualificationOutcome *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBIosQualificationOutcome *> *entries __attribute__((swift_name("entries")));
@end


/** A direct label for the existing authority phase, with no Swift dependency on domain types. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("IosQualificationPhase")))
@interface PDGBIosQualificationPhase : PDGBKotlinEnum<PDGBIosQualificationPhase *>
+ (instancetype)alloc __attribute__((unavailable));

/** A direct label for the existing authority phase, with no Swift dependency on domain types. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly) PDGBIosQualificationPhase *playing __attribute__((swift_name("playing")));
@property (class, readonly) PDGBIosQualificationPhase *roundEnded __attribute__((swift_name("roundEnded")));
@property (class, readonly) PDGBIosQualificationPhase *finished __attribute__((swift_name("finished")));
+ (PDGBKotlinArray<PDGBIosQualificationPhase *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBIosQualificationPhase *> *entries __attribute__((swift_name("entries")));
@end


/** A reference is explicit and repeatable; a live iOS session uses Security.framework. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("IosQualificationRandomness")))
@interface PDGBIosQualificationRandomness : PDGBKotlinEnum<PDGBIosQualificationRandomness *>
+ (instancetype)alloc __attribute__((unavailable));

/** A reference is explicit and repeatable; a live iOS session uses Security.framework. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly) PDGBIosQualificationRandomness *referenceSeed2 __attribute__((swift_name("referenceSeed2")));
@property (class, readonly) PDGBIosQualificationRandomness *secure __attribute__((swift_name("secure")));
+ (PDGBKotlinArray<PDGBIosQualificationRandomness *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBIosQualificationRandomness *> *entries __attribute__((swift_name("entries")));
@end


/**
 * [reasonCode] is empty on success, or the exact existing bridge/domain/failure enum name.
 * [outcome] identifies which kind of reason it is. Commands are safe native wire documents.
 */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("IosQualificationResult")))
@interface PDGBIosQualificationResult : PDGBBase
@property (readonly) NSArray<NSString *> *commands __attribute__((swift_name("commands")));
@property (readonly) PDGBIosQualificationOutcome *outcome __attribute__((swift_name("outcome")));
@property (readonly) NSString *reasonCode __attribute__((swift_name("reasonCode")));
@property (readonly) PDGBIosQualificationStatus *status __attribute__((swift_name("status")));
@end


/** Coarse receipt data only. Never used to decide a move or reconstruct a game view. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("IosQualificationStatus")))
@interface PDGBIosQualificationStatus : PDGBBase
@property (readonly) int32_t acceptedOpponentActions __attribute__((swift_name("acceptedOpponentActions")));
@property (readonly) int32_t acceptedRendererEvents __attribute__((swift_name("acceptedRendererEvents")));
@property (readonly) int32_t acceptedViewerChallenges __attribute__((swift_name("acceptedViewerChallenges")));
@property (readonly) int32_t acceptedViewerPlays __attribute__((swift_name("acceptedViewerPlays")));
@property (readonly) BOOL foreground __attribute__((swift_name("foreground")));
@property (readonly) PDGBIosQualificationLifecycle *lifecycle __attribute__((swift_name("lifecycle")));
@property (readonly) PDGBIosQualificationPhase *phase __attribute__((swift_name("phase")));
@property (readonly) NSString *revision __attribute__((swift_name("revision")));
@property (readonly) int32_t roundNumber __attribute__((swift_name("roundNumber")));
@property (readonly) int32_t roundsAdvanced __attribute__((swift_name("roundsAdvanced")));
@property (readonly) NSString *winnerId __attribute__((swift_name("winnerId")));
@end


/**
 * One serialized native owner, one presentation, one fixed recipient. Returned actions still
 * require acceptance by the real core/session authority. This class never owns GameState.
 */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("LastLightBridgeAdapter")))
@interface PDGBLastLightBridgeAdapter : PDGBBase
- (instancetype)initWithPresentationId:(NSString *)presentationId initialRevision:(int64_t)initialRevision initialView:(PDGBCoreGameView *)initialView controls:(PDGBPresentationControls *)controls __attribute__((swift_name("init(presentationId:initialRevision:initialView:controls:)"))) __attribute__((objc_designated_initializer));
- (id<PDGBBridgeDecision>)acceptDocument:(NSString *)document __attribute__((swift_name("accept(document:)")));
- (void)close __attribute__((swift_name("close()")));
- (PDGBGamesEngineCommandSetForeground *)setForegroundIsForeground:(BOOL)isForeground __attribute__((swift_name("setForeground(isForeground:)")));
- (PDGBGamesEngineCommandShowView *)showViewNewRevision:(int64_t)newRevision view:(PDGBCoreGameView *)view controls:(PDGBPresentationControls *)controls __attribute__((swift_name("showView(newRevision:view:controls:)")));
@property (readonly) PDGBGamesEngineLaunch *launch __attribute__((swift_name("launch")));
@property (readonly) NSString *presentationId __attribute__((swift_name("presentationId")));
@property (readonly) int64_t revision __attribute__((swift_name("revision")));
@end


/** No authority-state overload exists. The only view input is the existing safe GameView. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("LastLightWireCodec")))
@interface PDGBLastLightWireCodec : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));

/** No authority-state overload exists. The only view input is the existing safe GameView. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)lastLightWireCodec __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBLastLightWireCodec *shared __attribute__((swift_name("shared")));
- (PDGBGamesEngineEvent *)decodeEventDocument:(NSString *)document __attribute__((swift_name("decodeEvent(document:)")));
- (id<PDGBRendererIntent>)decodeIntentPayloadPayload:(PDGBGamesEnginePayload *)payload __attribute__((swift_name("decodeIntentPayload(payload:)")));
- (PDGBPresentationSnapshot *)decodeViewPayloadPayload:(PDGBGamesEnginePayload *)payload __attribute__((swift_name("decodeViewPayload(payload:)")));
- (NSString *)encodeClosePresentationId:(NSString *)presentationId __attribute__((swift_name("encodeClose(presentationId:)")));
- (NSString *)encodeCommandPresentationId:(NSString *)presentationId command:(id<PDGBGamesEngineCommand>)command __attribute__((swift_name("encodeCommand(presentationId:command:)")));
- (NSString *)encodeEventEvent:(PDGBGamesEngineEvent *)event __attribute__((swift_name("encodeEvent(event:)")));
- (NSString *)encodeLaunchLaunch:(PDGBGamesEngineLaunch *)launch mode:(PDGBPresentationMode *)mode preferences:(PDGBPresentationPreferences *)preferences __attribute__((swift_name("encodeLaunch(launch:mode:preferences:)")));
- (PDGBGamesEnginePayload *)intentPayloadIntent:(id<PDGBRendererIntent>)intent __attribute__((swift_name("intentPayload(intent:)")));
- (PDGBGamesEnginePayload *)viewPayloadView:(PDGBCoreGameView *)view controls:(PDGBPresentationControls *)controls __attribute__((swift_name("viewPayload(view:controls:)")));
@end


/** Supplied by the native/session owner, never by renderer JSON.
 *
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("PresentationControls")))
@interface PDGBPresentationControls : PDGBBase
- (instancetype)initWithIsHost:(BOOL)isHost canSendAction:(BOOL)canSendAction canAdvanceRound:(BOOL)canAdvanceRound canReturnToLobby:(BOOL)canReturnToLobby __attribute__((swift_name("init(isHost:canSendAction:canAdvanceRound:canReturnToLobby:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBPresentationControlsCompanion *companion __attribute__((swift_name("companion")));
- (PDGBPresentationControls *)doCopyIsHost:(BOOL)isHost canSendAction:(BOOL)canSendAction canAdvanceRound:(BOOL)canAdvanceRound canReturnToLobby:(BOOL)canReturnToLobby __attribute__((swift_name("doCopy(isHost:canSendAction:canAdvanceRound:canReturnToLobby:)")));

/** Supplied by the native/session owner, never by renderer JSON. */
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));

/** Supplied by the native/session owner, never by renderer JSON. */
- (NSUInteger)hash __attribute__((swift_name("hash()")));

/** Supplied by the native/session owner, never by renderer JSON. */
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) BOOL canAdvanceRound __attribute__((swift_name("canAdvanceRound")));
@property (readonly) BOOL canReturnToLobby __attribute__((swift_name("canReturnToLobby")));
@property (readonly) BOOL canSendAction __attribute__((swift_name("canSendAction")));
@property (readonly) BOOL isHost __attribute__((swift_name("isHost")));
@end


/** Supplied by the native/session owner, never by renderer JSON. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("PresentationControls.Companion")))
@interface PDGBPresentationControlsCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));

/** Supplied by the native/session owner, never by renderer JSON. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBPresentationControlsCompanion *shared __attribute__((swift_name("shared")));

/** Supplied by the native/session owner, never by renderer JSON. */
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("PresentationMode")))
@interface PDGBPresentationMode : PDGBKotlinEnum<PDGBPresentationMode *>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly) PDGBPresentationMode *twoD __attribute__((swift_name("twoD")));
@property (class, readonly) PDGBPresentationMode *threeD __attribute__((swift_name("threeD")));
+ (PDGBKotlinArray<PDGBPresentationMode *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBPresentationMode *> *entries __attribute__((swift_name("entries")));
@property (readonly) NSString *wireName __attribute__((swift_name("wireName")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("PresentationPreferences")))
@interface PDGBPresentationPreferences : PDGBBase
- (instancetype)initWithReduceMotion:(BOOL)reduceMotion soundEnabled:(BOOL)soundEnabled textScale:(double)textScale __attribute__((swift_name("init(reduceMotion:soundEnabled:textScale:)"))) __attribute__((objc_designated_initializer));
- (PDGBPresentationPreferences *)doCopyReduceMotion:(BOOL)reduceMotion soundEnabled:(BOOL)soundEnabled textScale:(double)textScale __attribute__((swift_name("doCopy(reduceMotion:soundEnabled:textScale:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) BOOL reduceMotion __attribute__((swift_name("reduceMotion")));
@property (readonly) BOOL soundEnabled __attribute__((swift_name("soundEnabled")));
@property (readonly) double textScale __attribute__((swift_name("textScale")));
@end


/**
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("PresentationSnapshot")))
@interface PDGBPresentationSnapshot : PDGBBase
- (instancetype)initWithGame:(PDGBCoreGameView *)game controls:(PDGBPresentationControls *)controls __attribute__((swift_name("init(game:controls:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBPresentationSnapshotCompanion *companion __attribute__((swift_name("companion")));
- (PDGBPresentationSnapshot *)doCopyGame:(PDGBCoreGameView *)game controls:(PDGBPresentationControls *)controls __attribute__((swift_name("doCopy(game:controls:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) PDGBPresentationControls *controls __attribute__((swift_name("controls")));
@property (readonly) PDGBCoreGameView *game __attribute__((swift_name("game")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("PresentationSnapshot.Companion")))
@interface PDGBPresentationSnapshotCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBPresentationSnapshotCompanion *shared __attribute__((swift_name("shared")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end


/**
 * A real core-authority round trip for isolated renderer qualification, not multiplayer.
 * Native code serializes calls and owns delivery/lifecycle. Live callers inject CSPRNG-backed
 * Random; reproducible fixture/test callers may deliberately inject a documented seed.
 */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("QualificationAuthorityDriver")))
@interface PDGBQualificationAuthorityDriver : PDGBBase
- (instancetype)initWithRandom:(PDGBKotlinRandom *)random presentationId:(NSString *)presentationId roster:(NSArray<PDGBCorePlayerIdentity *> *)roster viewerId:(NSString * _Nullable)viewerId __attribute__((swift_name("init(random:presentationId:roster:viewerId:)"))) __attribute__((objc_designated_initializer));

/** Test-opponent policy reads only its own projection; it contains no rule implementation. */
- (NSArray<PDGBQualificationStep *> *)advanceOtherPlayersMaxActions:(int32_t)maxActions __attribute__((swift_name("advanceOtherPlayers(maxActions:)")));
- (NSString *)close __attribute__((swift_name("close()")));
- (PDGBQualificationStep *)handleEventDocument:(NSString *)document __attribute__((swift_name("handleEvent(document:)")));
- (NSString *)launchDocumentMode:(PDGBPresentationMode *)mode preferences:(PDGBPresentationPreferences *)preferences __attribute__((swift_name("launchDocument(mode:preferences:)")));

/** Reconciles a rejected submission without changing domain state or reusing a revision. */
- (NSString *)refreshView __attribute__((swift_name("refreshView()")));
- (NSString *)setForegroundIsForeground:(BOOL)isForeground __attribute__((swift_name("setForeground(isForeground:)")));
@property (readonly) NSString *presentationId __attribute__((swift_name("presentationId")));
@property (readonly) int64_t revision __attribute__((swift_name("revision")));
@property (readonly) PDGBCoreGameView *view __attribute__((swift_name("view")));
@property (readonly) NSString *viewerId __attribute__((swift_name("viewerId")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("QualificationStep")))
@interface PDGBQualificationStep : PDGBBase
- (instancetype)initWithDecision:(id<PDGBBridgeDecision>)decision documents:(NSArray<NSString *> *)documents authorityRejection:(PDGBCoreGameRejection * _Nullable)authorityRejection __attribute__((swift_name("init(decision:documents:authorityRejection:)"))) __attribute__((objc_designated_initializer));
- (PDGBQualificationStep *)doCopyDecision:(id<PDGBBridgeDecision>)decision documents:(NSArray<NSString *> *)documents authorityRejection:(PDGBCoreGameRejection * _Nullable)authorityRejection __attribute__((swift_name("doCopy(decision:documents:authorityRejection:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) PDGBCoreGameRejection * _Nullable authorityRejection __attribute__((swift_name("authorityRejection")));
@property (readonly) id<PDGBBridgeDecision> decision __attribute__((swift_name("decision")));
@property (readonly) NSArray<NSString *> *documents __attribute__((swift_name("documents")));
@end

__attribute__((swift_name("RendererIntent")))
@protocol PDGBRendererIntent
@required
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("RendererIntentAdvanceRound")))
@interface PDGBRendererIntentAdvanceRound : PDGBBase <PDGBRendererIntent>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)advanceRound __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBRendererIntentAdvanceRound *shared __attribute__((swift_name("shared")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("RendererIntentChallenge")))
@interface PDGBRendererIntentChallenge : PDGBBase <PDGBRendererIntent>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)challenge __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBRendererIntentChallenge *shared __attribute__((swift_name("shared")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("RendererIntentPlay")))
@interface PDGBRendererIntentPlay : PDGBBase <PDGBRendererIntent>
- (instancetype)initWithCardIds:(NSArray<NSString *> *)cardIds __attribute__((swift_name("init(cardIds:)"))) __attribute__((objc_designated_initializer));
- (PDGBRendererIntentPlay *)doCopyCardIds:(NSArray<NSString *> *)cardIds __attribute__((swift_name("doCopy(cardIds:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) NSArray<NSString *> *cardIds __attribute__((swift_name("cardIds")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("RendererIntentReturnToLobby")))
@interface PDGBRendererIntentReturnToLobby : PDGBBase <PDGBRendererIntent>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)returnToLobby __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBRendererIntentReturnToLobby *shared __attribute__((swift_name("shared")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("LastLightWireCodecKt")))
@interface PDGBLastLightWireCodecKt : PDGBBase
@property (class, readonly) NSString *LAST_LIGHT_INTENT_SCHEMA __attribute__((swift_name("LAST_LIGHT_INTENT_SCHEMA")));
@property (class, readonly) NSString *LAST_LIGHT_VIEW_SCHEMA __attribute__((swift_name("LAST_LIGHT_VIEW_SCHEMA")));
@property (class, readonly) int32_t MAX_RENDERER_EVENT_BYTES __attribute__((swift_name("MAX_RENDERER_EVENT_BYTES")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("StrictJsonKt")))
@interface PDGBStrictJsonKt : PDGBBase

/**
 * Strict JSON preflight for platform messages before a platform JSON parser runs.
 * This checks syntax and resource bounds; callers must still validate their message schema.
 */
+ (void)validateBoundedJsonDocument:(NSString *)document maxBytes:(int32_t)maxBytes __attribute__((swift_name("validateBoundedJson(document:maxBytes:)")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("KotlinArray")))
@interface PDGBKotlinArray<T> : PDGBBase
+ (instancetype)arrayWithSize:(int32_t)size init:(T _Nullable (^)(PDGBInt *))init __attribute__((swift_name("init(size:init:)")));
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (T _Nullable)getIndex:(int32_t)index __attribute__((swift_name("get(index:)")));
- (id<PDGBKotlinIterator>)iterator __attribute__((swift_name("iterator()")));
- (void)setIndex:(int32_t)index value:(T _Nullable)value __attribute__((swift_name("set(index:value:)")));
@property (readonly) int32_t size __attribute__((swift_name("size")));
@end


/** The session binds [playerId] to an authenticated peer; it is not trusted client input. */
__attribute__((swift_name("CoreGameAction")))
@protocol PDGBCoreGameAction
@required
@property (readonly) NSString *playerId __attribute__((swift_name("playerId")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("GamesEngineFailure")))
@interface PDGBGamesEngineFailure : PDGBKotlinEnum<PDGBGamesEngineFailure *>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly) PDGBGamesEngineFailure *initializationFailed __attribute__((swift_name("initializationFailed")));
@property (class, readonly) PDGBGamesEngineFailure *invalidPayload __attribute__((swift_name("invalidPayload")));
@property (class, readonly) PDGBGamesEngineFailure *rendererLost __attribute__((swift_name("rendererLost")));
@property (class, readonly) PDGBGamesEngineFailure *internalError __attribute__((swift_name("internalError")));
+ (PDGBKotlinArray<PDGBGamesEngineFailure *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBGamesEngineFailure *> *entries __attribute__((swift_name("entries")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("KotlinEnumCompanion")))
@interface PDGBKotlinEnumCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBKotlinEnumCompanion *shared __attribute__((swift_name("shared")));
@end


/**
 * The only game model intended for screens, bots, and recipient-specific wire snapshots.
 * [yourHand] belongs only to [viewerId]. An unknown or eliminated viewer has no cards.
 * [roundOutcome] can belong to the previous round; its own round number is authoritative.
 *
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreGameView")))
@interface PDGBCoreGameView : PDGBBase
- (instancetype)initWithViewerId:(NSString * _Nullable)viewerId phase:(PDGBCoreGamePhase *)phase roundNumber:(int32_t)roundNumber tableRank:(PDGBCoreCardRank *)tableRank players:(NSArray<PDGBCorePlayerView *> *)players yourHand:(NSArray<PDGBCoreCard *> *)yourHand turnPlayerId:(NSString * _Nullable)turnPlayerId latestClaim:(PDGBCorePublicClaim * _Nullable)latestClaim forcedChallenge:(BOOL)forcedChallenge availableActions:(PDGBCoreAvailableActions *)availableActions roundOutcome:(PDGBCoreRoundOutcome * _Nullable)roundOutcome winnerId:(NSString * _Nullable)winnerId __attribute__((swift_name("init(viewerId:phase:roundNumber:tableRank:players:yourHand:turnPlayerId:latestClaim:forcedChallenge:availableActions:roundOutcome:winnerId:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBCoreGameViewCompanion *companion __attribute__((swift_name("companion")));
- (PDGBCoreGameView *)doCopyViewerId:(NSString * _Nullable)viewerId phase:(PDGBCoreGamePhase *)phase roundNumber:(int32_t)roundNumber tableRank:(PDGBCoreCardRank *)tableRank players:(NSArray<PDGBCorePlayerView *> *)players yourHand:(NSArray<PDGBCoreCard *> *)yourHand turnPlayerId:(NSString * _Nullable)turnPlayerId latestClaim:(PDGBCorePublicClaim * _Nullable)latestClaim forcedChallenge:(BOOL)forcedChallenge availableActions:(PDGBCoreAvailableActions *)availableActions roundOutcome:(PDGBCoreRoundOutcome * _Nullable)roundOutcome winnerId:(NSString * _Nullable)winnerId __attribute__((swift_name("doCopy(viewerId:phase:roundNumber:tableRank:players:yourHand:turnPlayerId:latestClaim:forcedChallenge:availableActions:roundOutcome:winnerId:)")));

/**
 * The only game model intended for screens, bots, and recipient-specific wire snapshots.
 * [yourHand] belongs only to [viewerId]. An unknown or eliminated viewer has no cards.
 * [roundOutcome] can belong to the previous round; its own round number is authoritative.
 */
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));

/**
 * The only game model intended for screens, bots, and recipient-specific wire snapshots.
 * [yourHand] belongs only to [viewerId]. An unknown or eliminated viewer has no cards.
 * [roundOutcome] can belong to the previous round; its own round number is authoritative.
 */
- (NSUInteger)hash __attribute__((swift_name("hash()")));

/**
 * The only game model intended for screens, bots, and recipient-specific wire snapshots.
 * [yourHand] belongs only to [viewerId]. An unknown or eliminated viewer has no cards.
 * [roundOutcome] can belong to the previous round; its own round number is authoritative.
 */
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) PDGBCoreAvailableActions *availableActions __attribute__((swift_name("availableActions")));
@property (readonly) BOOL forcedChallenge __attribute__((swift_name("forcedChallenge")));
@property (readonly) PDGBCorePublicClaim * _Nullable latestClaim __attribute__((swift_name("latestClaim")));
@property (readonly) PDGBCoreGamePhase *phase __attribute__((swift_name("phase")));
@property (readonly) NSArray<PDGBCorePlayerView *> *players __attribute__((swift_name("players")));
@property (readonly) int32_t roundNumber __attribute__((swift_name("roundNumber")));
@property (readonly) PDGBCoreRoundOutcome * _Nullable roundOutcome __attribute__((swift_name("roundOutcome")));
@property (readonly) PDGBCoreCardRank *tableRank __attribute__((swift_name("tableRank")));
@property (readonly) NSString * _Nullable turnPlayerId __attribute__((swift_name("turnPlayerId")));
@property (readonly) NSString * _Nullable viewerId __attribute__((swift_name("viewerId")));
@property (readonly) NSString * _Nullable winnerId __attribute__((swift_name("winnerId")));
@property (readonly) NSArray<PDGBCoreCard *> *yourHand __attribute__((swift_name("yourHand")));
@end


/** Coarse updates only. Local animations and the render loop stay inside the renderer. */
__attribute__((swift_name("GamesEngineCommand")))
@protocol PDGBGamesEngineCommand
@required
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("GamesEngineCommandSetForeground")))
@interface PDGBGamesEngineCommandSetForeground : PDGBBase <PDGBGamesEngineCommand>
- (instancetype)initWithIsForeground:(BOOL)isForeground __attribute__((swift_name("init(isForeground:)"))) __attribute__((objc_designated_initializer));
- (PDGBGamesEngineCommandSetForeground *)doCopyIsForeground:(BOOL)isForeground __attribute__((swift_name("doCopy(isForeground:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) BOOL isForeground __attribute__((swift_name("isForeground")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("GamesEngineCommandShowView")))
@interface PDGBGamesEngineCommandShowView : PDGBBase <PDGBGamesEngineCommand>
- (instancetype)initWithRevision:(int64_t)revision payload:(PDGBGamesEnginePayload *)payload __attribute__((swift_name("init(revision:payload:)"))) __attribute__((objc_designated_initializer));
- (PDGBGamesEngineCommandShowView *)doCopyRevision:(int64_t)revision payload:(PDGBGamesEnginePayload *)payload __attribute__((swift_name("doCopy(revision:payload:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) PDGBGamesEnginePayload *payload __attribute__((swift_name("payload")));
@property (readonly) int64_t revision __attribute__((swift_name("revision")));
@end


/** Unique for each presentation lifetime; this is not a network admission credential. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("GamesEngineLaunch")))
@interface PDGBGamesEngineLaunch : PDGBBase
- (instancetype)initWithGameId:(id)gameId presentationId:(NSString *)presentationId initialView:(PDGBGamesEnginePayload *)initialView initialRevision:(int64_t)initialRevision protocolVersion:(int32_t)protocolVersion __attribute__((swift_name("init(gameId:presentationId:initialView:initialRevision:protocolVersion:)"))) __attribute__((objc_designated_initializer));
- (PDGBGamesEngineLaunch *)doCopyGameId:(id)gameId presentationId:(NSString *)presentationId initialView:(PDGBGamesEnginePayload *)initialView initialRevision:(int64_t)initialRevision protocolVersion:(int32_t)protocolVersion __attribute__((swift_name("doCopy(gameId:presentationId:initialView:initialRevision:protocolVersion:)")));

/** Unique for each presentation lifetime; this is not a network admission credential. */
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));

/** Unique for each presentation lifetime; this is not a network admission credential. */
- (NSUInteger)hash __attribute__((swift_name("hash()")));

/** Unique for each presentation lifetime; this is not a network admission credential. */
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) id gameId __attribute__((swift_name("gameId")));
@property (readonly) int64_t initialRevision __attribute__((swift_name("initialRevision")));
@property (readonly) PDGBGamesEnginePayload *initialView __attribute__((swift_name("initialView")));
@property (readonly) NSString *presentationId __attribute__((swift_name("presentationId")));
@property (readonly) int32_t protocolVersion __attribute__((swift_name("protocolVersion")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("GamesEngineEvent")))
@interface PDGBGamesEngineEvent : PDGBBase
- (instancetype)initWithPresentationId:(NSString *)presentationId protocolVersion:(int32_t)protocolVersion sequence:(int64_t)sequence body:(id<PDGBGamesEngineEventBody>)body __attribute__((swift_name("init(presentationId:protocolVersion:sequence:body:)"))) __attribute__((objc_designated_initializer));
- (PDGBGamesEngineEvent *)doCopyPresentationId:(NSString *)presentationId protocolVersion:(int32_t)protocolVersion sequence:(int64_t)sequence body:(id<PDGBGamesEngineEventBody>)body __attribute__((swift_name("doCopy(presentationId:protocolVersion:sequence:body:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) id<PDGBGamesEngineEventBody> body __attribute__((swift_name("body")));
@property (readonly) NSString *presentationId __attribute__((swift_name("presentationId")));
@property (readonly) int32_t protocolVersion __attribute__((swift_name("protocolVersion")));
@property (readonly) int64_t sequence __attribute__((swift_name("sequence")));
@end


/**
 * An immutable, bounded document in a game adapter's versioned schema.
 * The adapter must encode a recipient-safe view or player intent, never authoritative
 * state or credentials. This boundary bounds storage; the adapter validates its schema.
 */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("GamesEnginePayload")))
@interface PDGBGamesEnginePayload : PDGBBase
- (instancetype)initWithSchemaId:(NSString *)schemaId document:(NSString *)document __attribute__((swift_name("init(schemaId:document:)"))) __attribute__((objc_designated_initializer));
- (PDGBGamesEnginePayload *)doCopySchemaId:(NSString *)schemaId document:(NSString *)document __attribute__((swift_name("doCopy(schemaId:document:)")));

/**
 * An immutable, bounded document in a game adapter's versioned schema.
 * The adapter must encode a recipient-safe view or player intent, never authoritative
 * state or credentials. This boundary bounds storage; the adapter validates its schema.
 */
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));

/**
 * An immutable, bounded document in a game adapter's versioned schema.
 * The adapter must encode a recipient-safe view or player intent, never authoritative
 * state or credentials. This boundary bounds storage; the adapter validates its schema.
 */
- (NSUInteger)hash __attribute__((swift_name("hash()")));

/**
 * An immutable, bounded document in a game adapter's versioned schema.
 * The adapter must encode a recipient-safe view or player intent, never authoritative
 * state or credentials. This boundary bounds storage; the adapter validates its schema.
 */
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) NSString *document __attribute__((swift_name("document")));
@property (readonly) NSString *schemaId __attribute__((swift_name("schemaId")));
@end


/**
 * Serialization strategy defines the serial form of a type [T], including its structural description,
 * declared by the [descriptor] and the actual serialization process, defined by the implementation
 * of the [serialize] method.
 *
 * [serialize] method takes an instance of [T] and transforms it into its serial form (a sequence of primitives),
 * calling the corresponding [Encoder] methods.
 *
 * A serial form of the type is a transformation of the concrete instance into a sequence of primitive values
 * and vice versa. The serial form is not required to completely mimic the structure of the class, for example,
 * a specific implementation may represent multiple integer values as a single string, omit or add some
 * values that are present in the type, but not in the instance.
 *
 * For a more detailed explanation of the serialization process, please refer to [KSerializer] documentation.
 */
__attribute__((swift_name("Kotlinx_serialization_coreSerializationStrategy")))
@protocol PDGBKotlinx_serialization_coreSerializationStrategy
@required

/**
 * Serializes the [value] of type [T] using the format that is represented by the given [encoder].
 * [serialize] method is format-agnostic and operates with a high-level structured [Encoder] API.
 * Throws [SerializationException] if value cannot be serialized.
 *
 * Example of serialize method:
 * ```
 * class MyData(int: Int, stringList: List<String>, alwaysZero: Long)
 *
 * fun serialize(encoder: Encoder, value: MyData): Unit = encoder.encodeStructure(descriptor) {
 *     // encodeStructure encodes beginning and end of the structure
 *     // encode 'int' property as Int
 *     encodeIntElement(descriptor, index = 0, value.int)
 *     // encode 'stringList' property as List<String>
 *     encodeSerializableElement(descriptor, index = 1, serializer<List<String>>, value.stringList)
 *     // don't encode 'alwaysZero' property because we decided to do so
 * } // end of the structure
 * ```
 *
 * @throws SerializationException in case of any serialization-specific error
 * @throws IllegalArgumentException if the supplied input does not comply encoder's specification
 * @see KSerializer for additional information about general contracts and exception specifics
 */
- (void)serializeEncoder:(id<PDGBKotlinx_serialization_coreEncoder>)encoder value:(id _Nullable)value __attribute__((swift_name("serialize(encoder:value:)")));

/**
 * Describes the structure of the serializable representation of [T], produced
 * by this serializer.
 */
@property (readonly) id<PDGBKotlinx_serialization_coreSerialDescriptor> descriptor __attribute__((swift_name("descriptor")));
@end


/**
 * Deserialization strategy defines the serial form of a type [T], including its structural description,
 * declared by the [descriptor] and the actual deserialization process, defined by the implementation
 * of the [deserialize] method.
 *
 * [deserialize] method takes an instance of [Decoder], and, knowing the serial form of the [T],
 * invokes primitive retrieval methods on the decoder and then transforms the received primitives
 * to an instance of [T].
 *
 * A serial form of the type is a transformation of the concrete instance into a sequence of primitive values
 * and vice versa. The serial form is not required to completely mimic the structure of the class, for example,
 * a specific implementation may represent multiple integer values as a single string, omit or add some
 * values that are present in the type, but not in the instance.
 *
 * For a more detailed explanation of the serialization process, please refer to [KSerializer] documentation.
 */
__attribute__((swift_name("Kotlinx_serialization_coreDeserializationStrategy")))
@protocol PDGBKotlinx_serialization_coreDeserializationStrategy
@required

/**
 * Deserializes the value of type [T] using the format that is represented by the given [decoder].
 * [deserialize] method is format-agnostic and operates with a high-level structured [Decoder] API.
 * As long as most of the formats imply an arbitrary order of properties, deserializer should be able
 * to decode these properties in an arbitrary order and in a format-agnostic way.
 * For that purposes, [CompositeDecoder.decodeElementIndex]-based loop is used: decoder firstly
 * signals property at which index it is ready to decode and then expects caller to decode
 * property with the given index.
 *
 * Throws [SerializationException] if value cannot be deserialized.
 *
 * Example of deserialize method:
 * ```
 * class MyData(int: Int, stringList: List<String>, alwaysZero: Long)
 *
 * fun deserialize(decoder: Decoder): MyData = decoder.decodeStructure(descriptor) {
 *     // decodeStructure decodes beginning and end of the structure
 *     var int: Int? = null
 *     var list: List<String>? = null
 *     loop@ while (true) {
 *         when (val index = decodeElementIndex(descriptor)) {
 *             DECODE_DONE -> break@loop
 *             0 -> {
 *                 // Decode 'int' property as Int
 *                 int = decodeIntElement(descriptor, index = 0)
 *             }
 *             1 -> {
 *                 // Decode 'stringList' property as List<String>
 *                 list = decodeSerializableElement(descriptor, index = 1, serializer<List<String>>())
 *             }
 *             else -> throw SerializationException("Unexpected index $index")
 *         }
 *      }
 *     if (int == null || list == null) throwMissingFieldException()
 *     // Always use 0 as a value for alwaysZero property because we decided to do so.
 *     return MyData(int, list, alwaysZero = 0L)
 * }
 * ```
 *
 * @throws MissingFieldException if non-optional fields were not found during deserialization
 * @throws SerializationException in case of any deserialization-specific error
 * @throws IllegalArgumentException if the decoded input is not a valid instance of [T]
 * @see KSerializer for additional information about general contracts and exception specifics
 */
- (id _Nullable)deserializeDecoder:(id<PDGBKotlinx_serialization_coreDecoder>)decoder __attribute__((swift_name("deserialize(decoder:)")));

/**
 * Describes the structure of the serializable representation of [T], that current
 * deserializer is able to deserialize.
 */
@property (readonly) id<PDGBKotlinx_serialization_coreSerialDescriptor> descriptor __attribute__((swift_name("descriptor")));
@end


/**
 * KSerializer is responsible for the representation of a serial form of a type [T]
 * in terms of [encoders][Encoder] and [decoders][Decoder] and for constructing and deconstructing [T]
 * from/to a sequence of encoding primitives. For classes marked with [@Serializable][Serializable], can be
 * obtained from generated companion extension `.serializer()` or from [serializer<T>()][serializer] function.
 *
 * Serialization is decoupled from the encoding process to make it completely format-agnostic.
 * Serialization represents a type as its serial form and is abstracted from the actual
 * format (whether its JSON, ProtoBuf or a hashing) and unaware of the underlying storage
 * (whether it is a string builder, byte array or a network socket), while
 * encoding/decoding is abstracted from a particular type and its serial form and is responsible
 * for transforming primitives ("here in an int property 'foo'" call from a serializer) into a particular
 * format-specific representation ("for a given int, append a property name in quotation marks,
 * then append a colon, then append an actual value" for JSON) and how to retrieve a primitive
 * ("give me an int that is 'foo' property") from the underlying representation ("expect the next string to be 'foo',
 * parse it, then parse colon, then parse a string until the next comma as an int and return it).
 *
 * Serial form consists of a structural description, declared by the [descriptor] and
 * actual serialization and deserialization processes, defined by the corresponding
 * [serialize] and [deserialize] methods implementation.
 *
 * Structural description specifies how the [T] is represented in the serial form:
 * its [kind][SerialKind] (e.g. whether it is represented as a primitive, a list or a class),
 * its [elements][SerialDescriptor.elementNames] and their [positional names][SerialDescriptor.getElementName].
 *
 * Serialization process is defined as a sequence of calls to an [Encoder], and transforms a type [T]
 * into a stream of format-agnostic primitives that represent [T], such as "here is an int, here is a double
 * and here is another nested object". It can be demonstrated by the example:
 * ```
 * class MyData(int: Int, stringList: List<String>, alwaysZero: Long)
 *
 * // .. serialize method of a corresponding serializer
 * fun serialize(encoder: Encoder, value: MyData): Unit = encoder.encodeStructure(descriptor) {
 *     // encodeStructure encodes beginning and end of the structure
 *     // encode 'int' property as Int
 *     encodeIntElement(descriptor, index = 0, value.int)
 *     // encode 'stringList' property as List<String>
 *     encodeSerializableElement(descriptor, index = 1, serializer<List<String>>, value.stringList)
 *     // don't encode 'alwaysZero' property because we decided to do so
 * } // end of the structure
 * ```
 *
 * Deserialization process is symmetric and uses [Decoder].
 *
 * ### Exception types for `KSerializer` implementation
 *
 * Implementations of [serialize] and [deserialize] methods are allowed to throw
 * any subtype of [IllegalArgumentException] in order to indicate serialization
 * and deserialization errors.
 *
 * For serializer implementations, it is recommended to throw subclasses of [SerializationException] for
 * any serialization-specific errors related to invalid or unsupported format of the data
 * and [IllegalStateException] for errors during validation of the data.
 */
__attribute__((swift_name("Kotlinx_serialization_coreKSerializer")))
@protocol PDGBKotlinx_serialization_coreKSerializer <PDGBKotlinx_serialization_coreSerializationStrategy, PDGBKotlinx_serialization_coreDeserializationStrategy>
@required
@end


/**
 * @note annotations
 *   kotlin.SinceKotlin(version="1.3")
*/
__attribute__((swift_name("KotlinRandom")))
@interface PDGBKotlinRandom : PDGBBase
- (instancetype)init __attribute__((swift_name("init()"))) __attribute__((objc_designated_initializer));
+ (instancetype)new __attribute__((availability(swift, unavailable, message="use object initializers instead")));
@property (class, readonly, getter=companion) PDGBKotlinRandomDefault *companion __attribute__((swift_name("companion")));
- (int32_t)nextBitsBitCount:(int32_t)bitCount __attribute__((swift_name("nextBits(bitCount:)")));
- (BOOL)nextBoolean __attribute__((swift_name("nextBoolean()")));

/**
 * @note annotations
 *   kotlin.IgnorableReturnValue
*/
- (PDGBKotlinByteArray *)nextBytesArray:(PDGBKotlinByteArray *)array __attribute__((swift_name("nextBytes(array:)")));
- (PDGBKotlinByteArray *)nextBytesSize:(int32_t)size __attribute__((swift_name("nextBytes(size:)")));

/**
 * @note annotations
 *   kotlin.IgnorableReturnValue
*/
- (PDGBKotlinByteArray *)nextBytesArray:(PDGBKotlinByteArray *)array fromIndex:(int32_t)fromIndex toIndex:(int32_t)toIndex __attribute__((swift_name("nextBytes(array:fromIndex:toIndex:)")));
- (double)nextDouble __attribute__((swift_name("nextDouble()")));
- (double)nextDoubleUntil:(double)until __attribute__((swift_name("nextDouble(until:)")));
- (double)nextDoubleFrom:(double)from until:(double)until __attribute__((swift_name("nextDouble(from:until:)")));
- (float)nextFloat __attribute__((swift_name("nextFloat()")));
- (int32_t)nextInt __attribute__((swift_name("nextInt()")));
- (int32_t)nextIntUntil:(int32_t)until __attribute__((swift_name("nextInt(until:)")));
- (int32_t)nextIntFrom:(int32_t)from until:(int32_t)until __attribute__((swift_name("nextInt(from:until:)")));
- (int64_t)nextLong __attribute__((swift_name("nextLong()")));
- (int64_t)nextLongUntil:(int64_t)until __attribute__((swift_name("nextLong(until:)")));
- (int64_t)nextLongFrom:(int64_t)from until:(int64_t)until __attribute__((swift_name("nextLong(from:until:)")));
@end


/**
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CorePlayerIdentity")))
@interface PDGBCorePlayerIdentity : PDGBBase
- (instancetype)initWithId:(NSString *)id displayName:(NSString *)displayName __attribute__((swift_name("init(id:displayName:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBCorePlayerIdentityCompanion *companion __attribute__((swift_name("companion")));
- (PDGBCorePlayerIdentity *)doCopyId:(NSString *)id displayName:(NSString *)displayName __attribute__((swift_name("doCopy(id:displayName:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) NSString *displayName __attribute__((swift_name("displayName")));
@property (readonly) NSString *id __attribute__((swift_name("id")));
@end


/**
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreGameRejection")))
@interface PDGBCoreGameRejection : PDGBKotlinEnum<PDGBCoreGameRejection *>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly, getter=companion) PDGBCoreGameRejectionCompanion *companion __attribute__((swift_name("companion")));
@property (class, readonly) PDGBCoreGameRejection *gameFinished __attribute__((swift_name("gameFinished")));
@property (class, readonly) PDGBCoreGameRejection *roundNotPlaying __attribute__((swift_name("roundNotPlaying")));
@property (class, readonly) PDGBCoreGameRejection *roundNotEnded __attribute__((swift_name("roundNotEnded")));
@property (class, readonly) PDGBCoreGameRejection *unknownPlayer __attribute__((swift_name("unknownPlayer")));
@property (class, readonly) PDGBCoreGameRejection *playerEliminated __attribute__((swift_name("playerEliminated")));
@property (class, readonly) PDGBCoreGameRejection *notYourTurn __attribute__((swift_name("notYourTurn")));
@property (class, readonly) PDGBCoreGameRejection *mustChallenge __attribute__((swift_name("mustChallenge")));
@property (class, readonly) PDGBCoreGameRejection *invalidCardCount __attribute__((swift_name("invalidCardCount")));
@property (class, readonly) PDGBCoreGameRejection *duplicateCard __attribute__((swift_name("duplicateCard")));
@property (class, readonly) PDGBCoreGameRejection *cardNotInHand __attribute__((swift_name("cardNotInHand")));
@property (class, readonly) PDGBCoreGameRejection *noClaim __attribute__((swift_name("noClaim")));
@property (class, readonly) PDGBCoreGameRejection *cannotChallengeSelf __attribute__((swift_name("cannotChallengeSelf")));
+ (PDGBKotlinArray<PDGBCoreGameRejection *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBCoreGameRejection *> *entries __attribute__((swift_name("entries")));
@end

__attribute__((swift_name("KotlinIterator")))
@protocol PDGBKotlinIterator
@required
- (BOOL)hasNext __attribute__((swift_name("hasNext()")));
- (id _Nullable)next __attribute__((swift_name("next()")));
@end


/**
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreGamePhase")))
@interface PDGBCoreGamePhase : PDGBKotlinEnum<PDGBCoreGamePhase *>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly, getter=companion) PDGBCoreGamePhaseCompanion *companion __attribute__((swift_name("companion")));
@property (class, readonly) PDGBCoreGamePhase *playing __attribute__((swift_name("playing")));
@property (class, readonly) PDGBCoreGamePhase *roundEnded __attribute__((swift_name("roundEnded")));
@property (class, readonly) PDGBCoreGamePhase *finished __attribute__((swift_name("finished")));
+ (PDGBKotlinArray<PDGBCoreGamePhase *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBCoreGamePhase *> *entries __attribute__((swift_name("entries")));
@end


/**
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreCardRank")))
@interface PDGBCoreCardRank : PDGBKotlinEnum<PDGBCoreCardRank *>
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)initWithName:(NSString *)name ordinal:(int32_t)ordinal __attribute__((swift_name("init(name:ordinal:)"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
@property (class, readonly, getter=companion) PDGBCoreCardRankCompanion *companion __attribute__((swift_name("companion")));
@property (class, readonly) PDGBCoreCardRank *crown __attribute__((swift_name("crown")));
@property (class, readonly) PDGBCoreCardRank *moon __attribute__((swift_name("moon")));
@property (class, readonly) PDGBCoreCardRank *star __attribute__((swift_name("star")));
@property (class, readonly) PDGBCoreCardRank *wild __attribute__((swift_name("wild")));
+ (PDGBKotlinArray<PDGBCoreCardRank *> *)values __attribute__((swift_name("values()")));
@property (class, readonly) NSArray<PDGBCoreCardRank *> *entries __attribute__((swift_name("entries")));
@end


/** Public seat information. Fuse burnout steps and other hands never appear here.
 *
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CorePlayerView")))
@interface PDGBCorePlayerView : PDGBBase
- (instancetype)initWithId:(NSString *)id displayName:(NSString *)displayName handCount:(int32_t)handCount penaltyAttempts:(int32_t)penaltyAttempts eliminated:(BOOL)eliminated __attribute__((swift_name("init(id:displayName:handCount:penaltyAttempts:eliminated:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBCorePlayerViewCompanion *companion __attribute__((swift_name("companion")));
- (PDGBCorePlayerView *)doCopyId:(NSString *)id displayName:(NSString *)displayName handCount:(int32_t)handCount penaltyAttempts:(int32_t)penaltyAttempts eliminated:(BOOL)eliminated __attribute__((swift_name("doCopy(id:displayName:handCount:penaltyAttempts:eliminated:)")));

/** Public seat information. Fuse burnout steps and other hands never appear here. */
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));

/** Public seat information. Fuse burnout steps and other hands never appear here. */
- (NSUInteger)hash __attribute__((swift_name("hash()")));

/** Public seat information. Fuse burnout steps and other hands never appear here. */
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) NSString *displayName __attribute__((swift_name("displayName")));
@property (readonly) BOOL eliminated __attribute__((swift_name("eliminated")));
@property (readonly) int32_t handCount __attribute__((swift_name("handCount")));
@property (readonly) NSString *id __attribute__((swift_name("id")));
@property (readonly) int32_t penaltyAttempts __attribute__((swift_name("penaltyAttempts")));
@end


/**
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreCard")))
@interface PDGBCoreCard : PDGBBase
- (instancetype)initWithId:(NSString *)id rank:(PDGBCoreCardRank *)rank __attribute__((swift_name("init(id:rank:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBCoreCardCompanion *companion __attribute__((swift_name("companion")));
- (PDGBCoreCard *)doCopyId:(NSString *)id rank:(PDGBCoreCardRank *)rank __attribute__((swift_name("doCopy(id:rank:)")));
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) NSString *id __attribute__((swift_name("id")));
@property (readonly) PDGBCoreCardRank *rank __attribute__((swift_name("rank")));
@end


/** A face-down claim deliberately has neither card identifiers nor card ranks.
 *
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CorePublicClaim")))
@interface PDGBCorePublicClaim : PDGBBase
- (instancetype)initWithPlayerId:(NSString *)playerId cardCount:(int32_t)cardCount __attribute__((swift_name("init(playerId:cardCount:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBCorePublicClaimCompanion *companion __attribute__((swift_name("companion")));
- (PDGBCorePublicClaim *)doCopyPlayerId:(NSString *)playerId cardCount:(int32_t)cardCount __attribute__((swift_name("doCopy(playerId:cardCount:)")));

/** A face-down claim deliberately has neither card identifiers nor card ranks. */
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));

/** A face-down claim deliberately has neither card identifiers nor card ranks. */
- (NSUInteger)hash __attribute__((swift_name("hash()")));

/** A face-down claim deliberately has neither card identifiers nor card ranks. */
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) int32_t cardCount __attribute__((swift_name("cardCount")));
@property (readonly) NSString *playerId __attribute__((swift_name("playerId")));
@end


/** Actions available to this view's recipient, rather than to any other player.
 *
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreAvailableActions")))
@interface PDGBCoreAvailableActions : PDGBBase
- (instancetype)initWithCanPlay:(BOOL)canPlay canChallenge:(BOOL)canChallenge maxPlayableCards:(int32_t)maxPlayableCards __attribute__((swift_name("init(canPlay:canChallenge:maxPlayableCards:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBCoreAvailableActionsCompanion *companion __attribute__((swift_name("companion")));
- (PDGBCoreAvailableActions *)doCopyCanPlay:(BOOL)canPlay canChallenge:(BOOL)canChallenge maxPlayableCards:(int32_t)maxPlayableCards __attribute__((swift_name("doCopy(canPlay:canChallenge:maxPlayableCards:)")));

/** Actions available to this view's recipient, rather than to any other player. */
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));

/** Actions available to this view's recipient, rather than to any other player. */
- (NSUInteger)hash __attribute__((swift_name("hash()")));

/** Actions available to this view's recipient, rather than to any other player. */
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) BOOL canChallenge __attribute__((swift_name("canChallenge")));
@property (readonly) BOOL canPlay __attribute__((swift_name("canPlay")));
@property (readonly) int32_t maxPlayableCards __attribute__((swift_name("maxPlayableCards")));
@end


/** Public proof and outcome of one resolved challenge.
 *
 * @note annotations
 *   kotlinx.serialization.Serializable
*/
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreRoundOutcome")))
@interface PDGBCoreRoundOutcome : PDGBBase
- (instancetype)initWithRoundNumber:(int32_t)roundNumber tableRank:(PDGBCoreCardRank *)tableRank claimantId:(NSString *)claimantId challengerId:(NSString *)challengerId revealedCards:(NSArray<PDGBCoreCard *> *)revealedCards truthful:(BOOL)truthful penalizedPlayerId:(NSString *)penalizedPlayerId penaltyAttempt:(int32_t)penaltyAttempt burnedOut:(BOOL)burnedOut __attribute__((swift_name("init(roundNumber:tableRank:claimantId:challengerId:revealedCards:truthful:penalizedPlayerId:penaltyAttempt:burnedOut:)"))) __attribute__((objc_designated_initializer));
@property (class, readonly, getter=companion) PDGBCoreRoundOutcomeCompanion *companion __attribute__((swift_name("companion")));
- (PDGBCoreRoundOutcome *)doCopyRoundNumber:(int32_t)roundNumber tableRank:(PDGBCoreCardRank *)tableRank claimantId:(NSString *)claimantId challengerId:(NSString *)challengerId revealedCards:(NSArray<PDGBCoreCard *> *)revealedCards truthful:(BOOL)truthful penalizedPlayerId:(NSString *)penalizedPlayerId penaltyAttempt:(int32_t)penaltyAttempt burnedOut:(BOOL)burnedOut __attribute__((swift_name("doCopy(roundNumber:tableRank:claimantId:challengerId:revealedCards:truthful:penalizedPlayerId:penaltyAttempt:burnedOut:)")));

/** Public proof and outcome of one resolved challenge. */
- (BOOL)isEqual:(id _Nullable)other __attribute__((swift_name("isEqual(_:)")));

/** Public proof and outcome of one resolved challenge. */
- (NSUInteger)hash __attribute__((swift_name("hash()")));

/** Public proof and outcome of one resolved challenge. */
- (NSString *)description __attribute__((swift_name("description()")));
@property (readonly) BOOL burnedOut __attribute__((swift_name("burnedOut")));
@property (readonly) NSString *challengerId __attribute__((swift_name("challengerId")));
@property (readonly) NSString *claimantId __attribute__((swift_name("claimantId")));
@property (readonly) NSString *penalizedPlayerId __attribute__((swift_name("penalizedPlayerId")));
@property (readonly) int32_t penaltyAttempt __attribute__((swift_name("penaltyAttempt")));
@property (readonly) NSArray<PDGBCoreCard *> *revealedCards __attribute__((swift_name("revealedCards")));
@property (readonly) int32_t roundNumber __attribute__((swift_name("roundNumber")));
@property (readonly) PDGBCoreCardRank *tableRank __attribute__((swift_name("tableRank")));
@property (readonly) BOOL truthful __attribute__((swift_name("truthful")));
@end


/**
 * The only game model intended for screens, bots, and recipient-specific wire snapshots.
 * [yourHand] belongs only to [viewerId]. An unknown or eliminated viewer has no cards.
 * [roundOutcome] can belong to the previous round; its own round number is authoritative.
 */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreGameView.Companion")))
@interface PDGBCoreGameViewCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));

/**
 * The only game model intended for screens, bots, and recipient-specific wire snapshots.
 * [yourHand] belongs only to [viewerId]. An unknown or eliminated viewer has no cards.
 * [roundOutcome] can belong to the previous round; its own round number is authoritative.
 */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCoreGameViewCompanion *shared __attribute__((swift_name("shared")));

/**
 * The only game model intended for screens, bots, and recipient-specific wire snapshots.
 * [yourHand] belongs only to [viewerId]. An unknown or eliminated viewer has no cards.
 * [roundOutcome] can belong to the previous round; its own round number is authoritative.
 */
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end

__attribute__((swift_name("GamesEngineEventBody")))
@protocol PDGBGamesEngineEventBody
@required
@end


/**
 * Encoder is a core serialization primitive that encapsulates the knowledge of the underlying
 * format and its storage, exposing only structural methods to the serializer, making it completely
 * format-agnostic. Serialization process transforms a single value into the sequence of its
 * primitive elements, also called its serial form, while encoding transforms these primitive elements into an actual
 * format representation: JSON string, ProtoBuf ByteArray, in-memory map representation etc.
 *
 * Encoder provides high-level API that operates with basic primitive types, collections
 * and nested structures. Internally, encoder represents output storage and operates with its state
 * and lower level format-specific details.
 *
 * To be more specific, serialization transforms a value into a sequence of "here is an int, here is
 * a double, here a list of strings and here is another object that is a nested int", while encoding
 * transforms this sequence into a format-specific commands such as "insert opening curly bracket
 * for a nested object start, insert a name of the value, and the value separated with colon for an int etc."
 *
 * The symmetric interface for the deserialization process is [Decoder].
 *
 * ### Serialization. Primitives
 *
 * If a class is represented as a single [primitive][PrimitiveKind] value in its serialized form,
 * then one of the `encode*` methods (e.g. [encodeInt]) can be used directly.
 *
 * ### Serialization. Structured types.
 *
 * If a class is represented as a structure or has multiple values in its serialized form,
 * `encode*` methods are not that helpful, because they do not allow working with collection types or establish structure boundaries.
 * All these capabilities are delegated to the [CompositeEncoder] interface with a more specific API surface.
 * To denote a structure start, [beginStructure] should be used.
 * ```
 * // Denote the structure start,
 * val composite = encoder.beginStructure(descriptor)
 * // Encoding all elements within the structure using 'composite'
 * ...
 * // Denote the structure end
 * composite.endStructure(descriptor)
 * ```
 *
 * E.g. if the encoder belongs to JSON format, then [beginStructure] will write an opening bracket
 * (`{` or `[`, depending on the descriptor kind), returning the [CompositeEncoder] that is aware of colon separator,
 * that should be appended between each key-value pair, whilst [CompositeEncoder.endStructure] will write a closing bracket.
 *
 * ### Exception guarantees
 *
 * For the regular exceptions, such as invalid input, conflicting serial names,
 * [SerializationException] can be thrown by any encoder methods.
 * It is recommended to declare a format-specific subclass of [SerializationException] and throw it.
 *
 * ### Exception safety
 *
 * In general, catching [SerializationException] from any of `encode*` methods is not allowed and produces unspecified behaviour.
 * After thrown exception, the current encoder is left in an arbitrary state, no longer suitable for further encoding.
 *
 * ### Format encapsulation
 *
 * For example, for the following serializer:
 * ```
 * class StringHolder(val stringValue: String)
 *
 * object StringPairDeserializer : SerializationStrategy<StringHolder> {
 *    override val descriptor = ...
 *
 *    override fun serializer(encoder: Encoder, value: StringHolder) {
 *        // Denotes start of the structure, StringHolder is not a "plain" data type
 *        val composite = encoder.beginStructure(descriptor)
 *        // Encode the nested string value
 *        composite.encodeStringElement(descriptor, index = 0)
 *        // Denotes end of the structure
 *        composite.endStructure(descriptor)
 *    }
 * }
 * ```
 *
 * This serializer does not know anything about the underlying storage and will work with any properly-implemented encoder.
 * JSON, for example, writes an opening bracket `{` during the `beginStructure` call, writes `stringValue` key along
 * with its value in `encodeStringElement` and writes the closing bracket `}` during the `endStructure`.
 * XML would do roughly the same, but with different separators and structures, while ProtoBuf
 * machinery could be completely different.
 * In any case, all these parsing details are encapsulated by an encoder.
 *
 * ### Encoder implementation.
 *
 * While being strictly typed, an underlying format can transform actual types in the way it wants.
 * For example, a format can support only string types and encode/decode all primitives in a string form:
 * ```
 * StringFormatEncoder : Encoder {
 *
 *     ...
 *     override fun encodeDouble(value: Double) = encodeString(value.toString())
 *     override fun encodeInt(value: Int) = encodeString(value.toString())
 *     ...
 * }
 * ```
 *
 * ### Not stable for inheritance
 *
 * `Encoder` interface is not stable for inheritance in 3rd party libraries, as new methods
 * might be added to this interface or contracts of the existing methods can be changed.
 */
__attribute__((swift_name("Kotlinx_serialization_coreEncoder")))
@protocol PDGBKotlinx_serialization_coreEncoder
@required

/**
 * Encodes the beginning of the collection with size [collectionSize] and the given serializer of its type parameters.
 * This method has to be implemented only if you need to know collection size in advance, otherwise, [beginStructure] can be used.
 */
- (id<PDGBKotlinx_serialization_coreCompositeEncoder>)beginCollectionDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor collectionSize:(int32_t)collectionSize __attribute__((swift_name("beginCollection(descriptor:collectionSize:)")));

/**
 * Encodes the beginning of the nested structure in a serialized form
 * and returns [CompositeDecoder] responsible for encoding this very structure.
 * E.g the hierarchy:
 * ```
 * class StringHolder(val stringValue: String)
 * class Holder(val stringHolder: StringHolder)
 * ```
 *
 * with the following serialized form in JSON:
 * ```
 * {
 *   "stringHolder" : { "stringValue": "value" }
 * }
 * ```
 *
 * will be roughly represented as the following sequence of calls:
 * ```
 * // Holder serializer
 * fun serialize(encoder: Encoder, value: Holder) {
 *     val composite = encoder.beginStructure(descriptor) // the very first opening bracket '{'
 *     composite.encodeSerializableElement(descriptor, 0, value.stringHolder) // Serialize nested StringHolder
 *     composite.endStructure(descriptor) // The very last closing bracket
 * }
 *
 * // StringHolder serializer
 * fun serialize(encoder: Encoder, value: StringHolder) {
 *     val composite = encoder.beginStructure(descriptor) // One more '{' when the key "stringHolder" is already written
 *     composite.encodeStringElement(descriptor, 0, value.stringValue) // Serialize actual value
 *     composite.endStructure(descriptor) // Closing bracket
 * }
 * ```
 */
- (id<PDGBKotlinx_serialization_coreCompositeEncoder>)beginStructureDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor __attribute__((swift_name("beginStructure(descriptor:)")));

/**
 * Encodes a boolean value.
 * Corresponding kind is [PrimitiveKind.BOOLEAN].
 */
- (void)encodeBooleanValue:(BOOL)value __attribute__((swift_name("encodeBoolean(value:)")));

/**
 * Encodes a single byte value.
 * Corresponding kind is [PrimitiveKind.BYTE].
 */
- (void)encodeByteValue:(int8_t)value __attribute__((swift_name("encodeByte(value:)")));

/**
 * Encodes a 16-bit unicode character value.
 * Corresponding kind is [PrimitiveKind.CHAR].
 */
- (void)encodeCharValue:(unichar)value __attribute__((swift_name("encodeChar(value:)")));

/**
 * Encodes a 64-bit IEEE 754 floating point value.
 * Corresponding kind is [PrimitiveKind.DOUBLE].
 */
- (void)encodeDoubleValue:(double)value __attribute__((swift_name("encodeDouble(value:)")));

/**
 * Encodes a enum value that is stored at the [index] in [enumDescriptor] elements collection.
 * Corresponding kind is [SerialKind.ENUM].
 *
 * E.g. for the enum `enum class Letters { A, B, C, D }` and
 * serializable value "C", [encodeEnum] method should be called with `2` as am index.
 *
 * This method does not imply any restrictions on the output format,
 * the format is free to store the enum by its name, index, ordinal or any other
 */
- (void)encodeEnumEnumDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)enumDescriptor index:(int32_t)index __attribute__((swift_name("encodeEnum(enumDescriptor:index:)")));

/**
 * Encodes a 32-bit IEEE 754 floating point value.
 * Corresponding kind is [PrimitiveKind.FLOAT].
 */
- (void)encodeFloatValue:(float)value __attribute__((swift_name("encodeFloat(value:)")));

/**
 * Returns [Encoder] for encoding an underlying type of a value class in an inline manner.
 * [descriptor] describes a serializable value class.
 *
 * Namely, for the `@Serializable @JvmInline value class MyInt(val my: Int)`,
 * the following sequence is used:
 * ```
 * thisEncoder.encodeInline(MyInt.serializer().descriptor).encodeInt(my)
 * ```
 *
 * Current encoder may return any other instance of [Encoder] class, depending on the provided [descriptor].
 * For example, when this function is called on Json encoder with `UInt.serializer().descriptor`, the returned encoder is able
 * to encode unsigned integers.
 *
 * Note that this function returns [Encoder] instead of the [CompositeEncoder]
 * because value classes always have the single property.
 * Calling [Encoder.beginStructure] on returned instance leads to an unspecified behavior and, in general, is prohibited.
 */
- (id<PDGBKotlinx_serialization_coreEncoder>)encodeInlineDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor __attribute__((swift_name("encodeInline(descriptor:)")));

/**
 * Encodes a 32-bit integer value.
 * Corresponding kind is [PrimitiveKind.INT].
 */
- (void)encodeIntValue:(int32_t)value __attribute__((swift_name("encodeInt(value:)")));

/**
 * Encodes a 64-bit integer value.
 * Corresponding kind is [PrimitiveKind.LONG].
 */
- (void)encodeLongValue:(int64_t)value __attribute__((swift_name("encodeLong(value:)")));

/**
 * Notifies the encoder that value of a nullable type that is
 * being serialized is not null. It should be called before writing a non-null value
 * of nullable type:
 * ```
 * // Could be String? serialize method
 * if (value != null) {
 *     encoder.encodeNotNullMark()
 *     encoder.encodeStringValue(value)
 * } else {
 *     encoder.encodeNull()
 * }
 * ```
 *
 * This method has a use in highly-performant binary formats and can
 * be safely ignore by most of the regular formats.
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (void)encodeNotNullMark __attribute__((swift_name("encodeNotNullMark()")));

/**
 * Encodes `null` value.
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (void)encodeNull __attribute__((swift_name("encodeNull()")));

/**
 * Encodes the nullable [value] of type [T] by delegating the encoding process to the given [serializer].
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (void)encodeNullableSerializableValueSerializer:(id<PDGBKotlinx_serialization_coreSerializationStrategy>)serializer value:(id _Nullable)value __attribute__((swift_name("encodeNullableSerializableValue(serializer:value:)")));

/**
 * Encodes the [value] of type [T] by delegating the encoding process to the given [serializer].
 * For example, `encodeInt` call is equivalent to delegating integer encoding to [Int.serializer][Int.Companion.serializer]:
 * `encodeSerializableValue(Int.serializer())`
 */
- (void)encodeSerializableValueSerializer:(id<PDGBKotlinx_serialization_coreSerializationStrategy>)serializer value:(id _Nullable)value __attribute__((swift_name("encodeSerializableValue(serializer:value:)")));

/**
 * Encodes a 16-bit short value.
 * Corresponding kind is [PrimitiveKind.SHORT].
 */
- (void)encodeShortValue:(int16_t)value __attribute__((swift_name("encodeShort(value:)")));

/**
 * Encodes a string value.
 * Corresponding kind is [PrimitiveKind.STRING].
 */
- (void)encodeStringValue:(NSString *)value __attribute__((swift_name("encodeString(value:)")));

/**
 * Context of the current serialization process, including contextual and polymorphic serialization and,
 * potentially, a format-specific configuration.
 */
@property (readonly) PDGBKotlinx_serialization_coreSerializersModule *serializersModule __attribute__((swift_name("serializersModule")));
@end


/**
 * Serial descriptor is an inherent property of [KSerializer] that describes the structure of the serializable type.
 * The structure of the serializable type is not only the characteristic of the type itself, but also of the serializer as well,
 * meaning that one type can have multiple descriptors that have completely different structures.
 *
 * For example, the class `class Color(val rgb: Int)` can have multiple serializable representations,
 * such as `{"rgb": 255}`, `"#0000FF"`, `[0, 0, 255]` and `{"red": 0, "green": 0, "blue": 255}`.
 * Representations are determined by serializers, and each such serializer has its own descriptor that identifies
 * each structure in a distinguishable and format-agnostic manner.
 *
 * ### Structure
 * Serial descriptor is identified by its [name][serialName] and consists of a kind, potentially empty set of
 * children elements, and additional metadata.
 *
 * * [serialName] uniquely identifies the descriptor (and the corresponding serializer) for non-generic types.
 *   For generic types, the actual type substitution is omitted from the string representation, and the name
 *   identifies the family of the serializers without type substitutions. However, type substitution is accounted for
 *   in [equals] and [hashCode] operations, meaning that descriptors of generic classes with the same name but different type
 *   arguments are not equal to each other.
 *   [serialName] is typically used to specify the type of the target class during serialization of polymorphic and sealed
 *   classes, for observability and diagnostics.
 * * [Kind][SerialKind] defines what this descriptor represents: primitive, enum, object, collection, etc.
 * * Children elements are represented as serial descriptors as well and define the structure of the type's elements.
 * * Metadata carries additional information, such as [nullability][nullable], [optionality][isElementOptional]
 *   and [serial annotations][getElementAnnotations].
 *
 * ### Usages
 * There are two general usages of the descriptors: THE serialization process and serialization introspection.
 *
 * #### Serialization
 * Serial descriptor is used as a bridge between decoders/encoders and serializers.
 * When asking for a next element, the serializer provides an expected descriptor to the decoder, and,
 * based on the descriptor content, the decoder decides how to parse its input.
 * In JSON, for example, when the encoder is asked to encode the next element and this element
 * is a subtype of [List], the encoder receives a descriptor with [StructureKind.LIST] and, based on that,
 * first writes an opening square bracket before writing the content of the list.
 *
 * Serial descriptor _encapsulates_ the structure of the data, so serializers can be free from
 * format-specific details. `ListSerializer` knows nothing about JSON and square brackets, providing
 * only the structure of the data and delegating encoding decision to the format itself.
 *
 * #### Introspection
 * Another usage of a serial descriptor is type introspection without its serialization.
 * Introspection can be used to check whether the given serializable class complies the
 * corresponding scheme and to generate JSON or ProtoBuf schema from the given class.
 *
 * ### Indices
 * Serial descriptor API operates with children indices.
 * For the fixed-size structures, such as regular classes, index is represented by a value in
 * the range from zero to [elementsCount] and represent and index of the property in this class.
 * Consequently, primitives do not have children and their element count is zero.
 *
 * For collections and maps indices do not have a fixed bound. Regular collections descriptors usually
 * have one element (`T`, maps have two, one for keys and one for values), but potentially unlimited
 * number of actual children values. Valid indices range is not known statically,
 * and implementations of such a descriptor should provide consistent and unbounded names and indices.
 *
 * In practice, for regular classes it is allowed to invoke `getElement*(index)` methods
 * with an index from `0` to [elementsCount] range and the element at the particular index corresponds to the
 * serializable property at the given position.
 * For collections and maps, index parameter for `getElement*(index)` methods is effectively bounded
 * by the maximal number of collection/map elements.
 *
 * ### Thread-safety and mutability
 * Serial descriptor implementation should be immutable and, thus, thread-safe.
 *
 * ### Equality and caching
 * Serial descriptor can be used as a unique identifier for format-specific data or schemas and
 * this implies the following restrictions on its `equals` and `hashCode`:
 *
 * An [equals] implementation should use both [serialName] and elements structure.
 * Comparing [elementDescriptors] directly is discouraged,
 * because it may cause a stack overflow error, e.g., if a serializable class `T` contains elements of type `T`.
 * To avoid it, a serial descriptor implementation should compare only descriptors
 * of class' type parameters, in a way that `serializer<Box<Int>>().descriptor != serializer<Box<String>>().descriptor`.
 * If type parameters are equal, descriptor structure should be compared by using children elements
 * descriptors' [serialName]s, which correspond to class names
 * (do not confuse with elements' own names, which correspond to properties' names); and/or other [SerialDescriptor]
 * properties, such as [kind].
 * An example of [equals] implementation:
 * ```
 * if (this === other) return true
 * if (other::class != this::class) return false
 * if (serialName != other.serialName) return false
 * if (!typeParametersAreEqual(other)) return false
 * if (this.elementDescriptors().map { it.serialName } != other.elementDescriptors().map { it.serialName }) return false
 * return true
 * ```
 *
 * [hashCode] implementation should use the same properties for computing the result.
 *
 * ### User-defined serial descriptors
 * The best way to define a custom descriptor is to use [buildClassSerialDescriptor] builder function, where
 * for each serializable property the corresponding element is declared.
 *
 * Example:
 * ```
 * // Class with custom serializer and custom serial descriptor
 * class Data(
 *     val intField: Int, // This field is ignored by custom serializer
 *     val longField: Long, // This field is written as long, but in serialized form is named as "_longField"
 *     val stringList: List<String> // This field is written as regular list of strings
 * )
 *
 * // Descriptor for such class:
 * buildClassSerialDescriptor("my.package.Data") {
 *     // intField is deliberately ignored by serializer -- not present in the descriptor as well
 *     element<Long>("_longField") // longField is named as _longField
 *     element("stringField", listSerialDescriptor<String>())
 * }
 *
 * // Example of 'serialize' function for such descriptor
 * override fun serialize(encoder: Encoder, value: Data) {
 *     encoder.encodeStructure(descriptor) {
 *         encodeLongElement(descriptor, 0, value.longField) // Will be written as "_longField" because descriptor's child at index 0 says so
 *         encodeSerializableElement(descriptor, 1, ListSerializer(String.serializer()), value.stringList)
 *     }
 * }
 * ```
 *
 * For classes that are represented as a single primitive value, [PrimitiveSerialDescriptor] builder function can be used instead.
 *
 * ### Consistency violations
 * An implementation of [SerialDescriptor] should be consistent with the implementation of the corresponding [KSerializer].
 * Yet it is not type-checked statically, thus making it possible to declare a non-consistent implementation of descriptor and serializer.
 * In such cases, the behavior of an underlying format is unspecified and may lead to both runtime errors and encoding of
 * corrupted data that is impossible to decode back.
 *
 * ### Not for implementation
 *
 * `SerialDescriptor` interface should not be implemented in 3rd party libraries, as new methods
 * might be added to this interface when kotlinx.serialization adds support for new Kotlin features.
 * This interface is safe to use and construct via [buildClassSerialDescriptor], [PrimitiveSerialDescriptor], and `SerialDescriptor` factory function.
 *
 * @note annotations
 *   kotlin.SubclassOptInRequired(markerClass=[NormalClass(value=kotlinx/serialization/SealedSerializationApi)])
*/
__attribute__((swift_name("Kotlinx_serialization_coreSerialDescriptor")))
@protocol PDGBKotlinx_serialization_coreSerialDescriptor
@required

/**
 * Returns serial annotations of the child element at the given [index].
 * This method differs from `getElementDescriptor(index).annotations` by reporting only
 * element-specific annotations:
 * ```
 * @Serializable
 * @OnClassSerialAnnotation
 * class Nested(...)
 *
 * @Serializable
 * class Outer(@OnPropertySerialAnnotation val nested: Nested)
 *
 * val outerDescriptor = Outer.serializer().descriptor
 *
 * outerDescriptor.getElementAnnotations(0) // Returns [@OnPropertySerialAnnotation]
 * outerDescriptor.getElementDescriptor(0).annotations // Returns [@OnClassSerialAnnotation]
 * ```
 * Only annotations marked with [SerialInfo] are added to the resulting list.
 *
 * @throws IndexOutOfBoundsException for an illegal [index] values.
 * @throws IllegalStateException if the current descriptor does not support children elements (e.g. is a primitive).
 */
- (NSArray<id<PDGBKotlinAnnotation>> *)getElementAnnotationsIndex:(int32_t)index __attribute__((swift_name("getElementAnnotations(index:)")));

/**
 * Retrieves the descriptor of the child element for the given [index].
 * For the property of type `T` on the position `i`, `getElementDescriptor(i)` yields the same result
 * as for `T.serializer().descriptor`, if the serializer for this property is not explicitly overridden
 * with `@Serializable(with = ...`)`, [Polymorphic] or [Contextual].
 * This method can be used to completely introspect the type that the current descriptor describes.
 *
 * Example:
 * ```
 * @Serializable
 * @OnClassSerialAnnotation
 * class Nested(...)
 *
 * @Serializable
 * class Outer(val nested: Nested)
 *
 * val outerDescriptor = Outer.serializer().descriptor
 *
 * outerDescriptor.getElementDescriptor(0).serialName // Returns "Nested"
 * outerDescriptor.getElementDescriptor(0).annotations // Returns [@OnClassSerialAnnotation]
 * ```
 *
 * @throws IndexOutOfBoundsException for illegal [index] values.
 * @throws IllegalStateException if the current descriptor does not support children elements (e.g. is a primitive).
 */
- (id<PDGBKotlinx_serialization_coreSerialDescriptor>)getElementDescriptorIndex:(int32_t)index __attribute__((swift_name("getElementDescriptor(index:)")));

/**
 * Returns an index in the children list of the given element by its name or [CompositeDecoder.UNKNOWN_NAME]
 * if there is no such element.
 * The resulting index, if it is not [CompositeDecoder.UNKNOWN_NAME], is guaranteed to be usable with [getElementName].
 *
 * Example:
 *
 * ```
 * @Serializable
 * class User(val name: String, val alias: String?)
 *
 * val userDescriptor = User.serializer().descriptor
 *
 * userDescriptor.getElementIndex("name") // Returns 0
 * userDescriptor.getElementIndex("alias") // Returns 1
 * userDescriptor.getElementIndex("lastName") // Returns CompositeDecoder.UNKNOWN_NAME = -3
 * ```
 */
- (int32_t)getElementIndexName:(NSString *)name __attribute__((swift_name("getElementIndex(name:)")));

/**
 * Returns a positional name of the child at the given [index].
 * Positional name represents a corresponding property name in the class, associated with
 * the current descriptor.
 *
 * Do not confuse with [serialName], which returns class name:
 *
 * ```
 * package my.app
 *
 * @Serializable
 * class User(val name: String)
 *
 * val userDescriptor = User.serializer().descriptor
 *
 * userDescriptor.serialName // Returns "my.app.User"
 * userDescriptor.getElementName(0) // Returns "name"
 * ```
 *
 * @throws IndexOutOfBoundsException for an illegal [index] values.
 * @throws IllegalStateException if the current descriptor does not support children elements (e.g. is a primitive)
 */
- (NSString *)getElementNameIndex:(int32_t)index __attribute__((swift_name("getElementName(index:)")));

/**
 * Whether the element at the given [index] is optional (can be absent in serialized form).
 * For generated descriptors, all elements that have a corresponding default parameter value are
 * marked as optional. Custom serializers can treat optional values in a serialization-specific manner
 * without a default parameters constraint.
 *
 * Example of optionality:
 * ```
 * @Serializable
 * class Holder(
 *     val a: Int, // isElementOptional(0) == false
 *     val b: Int?, // isElementOptional(1) == false
 *     val c: Int? = null, // isElementOptional(2) == true
 *     val d: List<Int>, // isElementOptional(3) == false
 *     val e: List<Int> = listOf(1), // isElementOptional(4) == true
 * )
 * ```
 * Returns `false` for valid indices of collections, maps, and enums.
 *
 * @throws IndexOutOfBoundsException for an illegal [index] values.
 * @throws IllegalStateException if the current descriptor does not support children elements (e.g. is a primitive).
 */
- (BOOL)isElementOptionalIndex:(int32_t)index __attribute__((swift_name("isElementOptional(index:)")));

/**
 * Returns serial annotations of the associated class.
 * Serial annotations can be used to specify additional metadata that may be used during serialization.
 * Only annotations marked with [SerialInfo] are added to the resulting list.
 *
 * Do not confuse with [getElementAnnotations]:
 * ```
 * @Serializable
 * @OnClassSerialAnnotation
 * class Nested(...)
 *
 * @Serializable
 * class Outer(@OnPropertySerialAnnotation val nested: Nested)
 *
 * val outerDescriptor = Outer.serializer().descriptor
 *
 * outerDescriptor.getElementAnnotations(0) // Returns [@OnPropertySerialAnnotation]
 * outerDescriptor.getElementDescriptor(0).annotations // Returns [@OnClassSerialAnnotation]
 * ```
 */
@property (readonly) NSArray<id<PDGBKotlinAnnotation>> *annotations __attribute__((swift_name("annotations")));

/**
 * The number of elements this descriptor describes, besides from the class itself.
 * [elementsCount] describes the number of **semantic** elements, not the number
 * of actual fields/properties in the serialized form, even though they frequently match.
 *
 * For example, for the following class
 * `class Complex(val real: Long, val imaginary: Long)` the corresponding descriptor
 * and the serialized form both have two elements, while for `List<Int>`
 * the corresponding descriptor has a single element (`IntDescriptor`, the type of list element),
 * but from zero up to `Int.MAX_VALUE` values in the serialized form:
 *
 * ```
 * @Serializable
 * class Complex(val real: Long, val imaginary: Long)
 *
 * Complex.serializer().descriptor.elementsCount // Returns 2
 *
 * @Serializable
 * class OuterList(val list: List<Int>)
 *
 * OuterList.serializer().descriptor.getElementDescriptor(0).elementsCount // Returns 1
 * ```
 */
@property (readonly) int32_t elementsCount __attribute__((swift_name("elementsCount")));

/**
 * Returns `true` if this descriptor describes a serializable value class which underlying value
 * is serialized directly.
 *
 * This property is true for serializable `@JvmInline value` classes:
 * ```
 * @Serializable
 * class User(val name: Name)
 *
 * @Serializable
 * @JvmInline
 * value class Name(val value: String)
 *
 * User.serializer().descriptor.isInline // false
 * User.serializer().descriptor.getElementDescriptor(0).isInline // true
 * Name.serializer().descriptor.isInline // true
 * ```
 */
@property (readonly) BOOL isInline __attribute__((swift_name("isInline")));

/**
 * Whether the descriptor describes a nullable type.
 * Returns `true` if associated serializer can serialize/deserialize nullable elements of the described type.
 *
 * Example:
 *
 * ```
 * @Serializable
 * class User(val name: String, val alias: String?)
 *
 * val userDescriptor = User.serializer().descriptor
 *
 * userDescriptor.isNullable // Returns false
 * userDescriptor.getElementDescriptor(0).isNullable // Returns false
 * userDescriptor.getElementDescriptor(1).isNullable // Returns true
 * ```
 */
@property (readonly) BOOL isNullable __attribute__((swift_name("isNullable")));

/**
 * The kind of the serialized form that determines **the shape** of the serialized data.
 * Formats use serial kind to add and parse serializer-agnostic metadata to the result.
 *
 * For example, JSON format wraps [classes][StructureKind.CLASS] and [StructureKind.MAP] into
 * brackets, while ProtoBuf just serialize these types in separate ways.
 *
 * Kind should be consistent with the implementation, for example, if it is a [primitive][PrimitiveKind],
 * then its element count should be zero and vice versa.
 *
 * Example of introspecting kinds:
 *
 * ```
 * @Serializable
 * class User(val name: String)
 *
 * val userDescriptor = User.serializer().descriptor
 *
 * userDescriptor.kind // Returns StructureKind.CLASS
 * userDescriptor.getElementDescriptor(0).kind // Returns PrimitiveKind.STRING
 * ```
 */
@property (readonly) PDGBKotlinx_serialization_coreSerialKind *kind __attribute__((swift_name("kind")));

/**
 * Serial name of the descriptor that identifies a pair of the associated serializer and target class.
 *
 * For generated and default serializers, the serial name is equal to the corresponding class's fully qualified name
 * or, if overridden, [SerialName].
 * Custom serializers should provide a unique serial name that identifies both the serializable class and
 * the serializer itself, ignoring type arguments if they are present, for example: `my.package.LongAsTrimmedString`.
 *
 * Do not confuse with [getElementName], which returns property name:
 *
 * ```
 * package my.app
 *
 * @Serializable
 * class User(val name: String)
 *
 * val userDescriptor = User.serializer().descriptor
 *
 * userDescriptor.serialName // Returns "my.app.User"
 * userDescriptor.getElementName(0) // Returns "name"
 * ```
 */
@property (readonly) NSString *serialName __attribute__((swift_name("serialName")));
@end


/**
 * Decoder is a core deserialization primitive that encapsulates the knowledge of the underlying
 * format and an underlying storage, exposing only structural methods to the deserializer, making it completely
 * format-agnostic. Deserialization process takes a decoder and asks him for a sequence of primitive elements,
 * defined by a deserializer serial form, while decoder knows how to retrieve these primitive elements from an actual format
 * representations.
 *
 * Decoder provides high-level API that operates with basic primitive types, collections
 * and nested structures. Internally, the decoder represents input storage, and operates with its state
 * and lower level format-specific details.
 *
 * To be more specific, serialization asks a decoder for a sequence of "give me an int, give me
 * a double, give me a list of strings and give me another object that is a nested int", while decoding
 * transforms this sequence into a format-specific commands such as "parse the part of the string until the next quotation mark
 * as an int to retrieve an int, parse everything within the next curly braces to retrieve elements of a nested object etc."
 *
 * The symmetric interface for the serialization process is [Encoder].
 *
 * ### Deserialization. Primitives
 *
 * If a class is represented as a single [primitive][PrimitiveKind] value in its serialized form,
 * then one of the `decode*` methods (e.g. [decodeInt]) can be used directly.
 *
 * ### Deserialization. Structured types
 *
 * If a class is represented as a structure or has multiple values in its serialized form,
 * `decode*` methods are not that helpful, because format may not require a strict order of data
 * (e.g. JSON or XML), do not allow working with collection types or establish structure boundaries.
 * All these capabilities are delegated to the [CompositeDecoder] interface with a more specific API surface.
 * To denote a structure start, [beginStructure] should be used.
 * ```
 * // Denote the structure start,
 * val composite = decoder.beginStructure(descriptor)
 * // Decode all elements within the structure using 'composite'
 * ...
 * // Denote the structure end
 * composite.endStructure(descriptor)
 * ```
 *
 * E.g. if the decoder belongs to JSON format, then [beginStructure] will parse an opening bracket
 * (`{` or `[`, depending on the descriptor kind), returning the [CompositeDecoder] that is aware of colon separator,
 * that should be read after each key-value pair, whilst [CompositeDecoder.endStructure] will parse a closing bracket.
 *
 * ### Exception guarantees
 *
 * For the regular exceptions, such as invalid input, missing control symbols or attributes, and unknown symbols,
 * [SerializationException] can be thrown by any decoder methods. It is recommended to declare a format-specific
 * subclass of [SerializationException] and throw it.
 *
 * ### Exception safety
 *
 * In general, catching [SerializationException] from any of `decode*` methods is not allowed and produces unspecified behavior.
 * After thrown exception, the current decoder is left in an arbitrary state, no longer suitable for further decoding.
 *
 * ### Format encapsulation
 *
 * For example, for the following deserializer:
 * ```
 * class StringHolder(val stringValue: String)
 *
 * object StringPairDeserializer : DeserializationStrategy<StringHolder> {
 *    override val descriptor = ...
 *
 *    override fun deserializer(decoder: Decoder): StringHolder {
 *        // Denotes start of the structure, StringHolder is not a "plain" data type
 *        val composite = decoder.beginStructure(descriptor)
 *        if (composite.decodeElementIndex(descriptor) != 0)
 *            throw MissingFieldException("Field 'stringValue' is missing")
 *        // Decode the nested string value
 *        val value = composite.decodeStringElement(descriptor, index = 0)
 *        // Denotes end of the structure
 *        composite.endStructure(descriptor)
 *    }
 * }
 * ```
 *
 * This deserializer does not know anything about the underlying data and will work with any properly-implemented decoder.
 * JSON, for example, parses an opening bracket `{` during the `beginStructure` call, checks that the next key
 * after this bracket is `stringValue` (using the descriptor), returns the value after the colon as string value
 * and parses closing bracket `}` during the `endStructure`.
 * XML would do roughly the same, but with different separators and parsing structures, while ProtoBuf
 * machinery could be completely different.
 * In any case, all these parsing details are encapsulated by a decoder.
 *
 * ### Decoder implementation
 *
 * While being strictly typed, an underlying format can transform actual types in the way it wants.
 * For example, a format can support only string types and encode/decode all primitives in a string form:
 * ```
 * StringFormatDecoder : Decoder {
 *
 *     ...
 *     override fun decodeDouble(): Double = decodeString().toDouble()
 *     override fun decodeInt(): Int = decodeString().toInt()
 *     ...
 * }
 * ```
 *
 * ### Not stable for inheritance
 *
 * `Decoder` interface is not stable for inheritance in 3rd-party libraries, as new methods
 * might be added to this interface or contracts of the existing methods can be changed.
 */
__attribute__((swift_name("Kotlinx_serialization_coreDecoder")))
@protocol PDGBKotlinx_serialization_coreDecoder
@required

/**
 * Decodes the beginning of the nested structure in a serialized form
 * and returns [CompositeDecoder] responsible for decoding this very structure.
 *
 * Typically, classes, collections and maps are represented as a nested structure in a serialized form.
 * E.g. the following JSON
 * ```
 * {
 *     "a": 2,
 *     "b": { "nested": "c" }
 *     "c": [1, 2, 3],
 *     "d": null
 * }
 * ```
 * has three nested structures: the very beginning of the data, "b" value and "c" value.
 */
- (id<PDGBKotlinx_serialization_coreCompositeDecoder>)beginStructureDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor __attribute__((swift_name("beginStructure(descriptor:)")));

/**
 * Decodes a boolean value.
 * Corresponding kind is [PrimitiveKind.BOOLEAN].
 */
- (BOOL)decodeBoolean __attribute__((swift_name("decodeBoolean()")));

/**
 * Decodes a single byte value.
 * Corresponding kind is [PrimitiveKind.BYTE].
 */
- (int8_t)decodeByte __attribute__((swift_name("decodeByte()")));

/**
 * Decodes a 16-bit unicode character value.
 * Corresponding kind is [PrimitiveKind.CHAR].
 */
- (unichar)decodeChar __attribute__((swift_name("decodeChar()")));

/**
 * Decodes a 64-bit IEEE 754 floating point value.
 * Corresponding kind is [PrimitiveKind.DOUBLE].
 */
- (double)decodeDouble __attribute__((swift_name("decodeDouble()")));

/**
 * Decodes a enum value and returns its index in [enumDescriptor] elements collection.
 * Corresponding kind is [SerialKind.ENUM].
 *
 * E.g. for the enum `enum class Letters { A, B, C, D }` and
 * underlying input "C", [decodeEnum] method should return `2` as a result.
 *
 * This method does not imply any restrictions on the input format,
 * the format is free to store the enum by its name, index, ordinal or any other enum representation.
 */
- (int32_t)decodeEnumEnumDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)enumDescriptor __attribute__((swift_name("decodeEnum(enumDescriptor:)")));

/**
 * Decodes a 32-bit IEEE 754 floating point value.
 * Corresponding kind is [PrimitiveKind.FLOAT].
 */
- (float)decodeFloat __attribute__((swift_name("decodeFloat()")));

/**
 * Returns [Decoder] for decoding an underlying type of a value class in an inline manner.
 * [descriptor] describes a target value class.
 *
 * Namely, for the `@Serializable @JvmInline value class MyInt(val my: Int)`, the following sequence is used:
 * ```
 * thisDecoder.decodeInline(MyInt.serializer().descriptor).decodeInt()
 * ```
 *
 * Current decoder may return any other instance of [Decoder] class, depending on the provided [descriptor].
 * For example, when this function is called on `Json` decoder with
 * `UInt.serializer().descriptor`, the returned decoder is able to decode unsigned integers.
 *
 * Note that this function returns [Decoder] instead of the [CompositeDecoder]
 * because value classes always have the single property.
 *
 * Calling [Decoder.beginStructure] on returned instance leads to an unspecified behavior and, in general, is prohibited.
 */
- (id<PDGBKotlinx_serialization_coreDecoder>)decodeInlineDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor __attribute__((swift_name("decodeInline(descriptor:)")));

/**
 * Decodes a 32-bit integer value.
 * Corresponding kind is [PrimitiveKind.INT].
 */
- (int32_t)decodeInt __attribute__((swift_name("decodeInt()")));

/**
 * Decodes a 64-bit integer value.
 * Corresponding kind is [PrimitiveKind.LONG].
 */
- (int64_t)decodeLong __attribute__((swift_name("decodeLong()")));

/**
 * Returns `true` if the current value in decoder is not null, false otherwise.
 * This method is usually used to decode potentially nullable data:
 * ```
 * // Could be String? deserialize() method
 * public fun deserialize(decoder: Decoder): String? {
 *     if (decoder.decodeNotNullMark()) {
 *         return decoder.decodeString()
 *     } else {
 *         return decoder.decodeNull()
 *     }
 * }
 * ```
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (BOOL)decodeNotNullMark __attribute__((swift_name("decodeNotNullMark()")));

/**
 * Decodes the `null` value and returns it.
 *
 * It is expected that `decodeNotNullMark` was called
 * prior to `decodeNull` invocation and the case when it returned `true` was handled.
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (PDGBKotlinNothing * _Nullable)decodeNull __attribute__((swift_name("decodeNull()")));

/**
 * Decodes the nullable value of type [T] by delegating the decoding process to the given [deserializer].
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (id _Nullable)decodeNullableSerializableValueDeserializer:(id<PDGBKotlinx_serialization_coreDeserializationStrategy>)deserializer __attribute__((swift_name("decodeNullableSerializableValue(deserializer:)")));

/**
 * Decodes the value of type [T] by delegating the decoding process to the given [deserializer].
 * For example, `decodeInt` call is equivalent to delegating integer decoding to [Int.serializer][Int.Companion.serializer]:
 * `decodeSerializableValue(Int.serializer())`
 */
- (id _Nullable)decodeSerializableValueDeserializer:(id<PDGBKotlinx_serialization_coreDeserializationStrategy>)deserializer __attribute__((swift_name("decodeSerializableValue(deserializer:)")));

/**
 * Decodes a 16-bit short value.
 * Corresponding kind is [PrimitiveKind.SHORT].
 */
- (int16_t)decodeShort __attribute__((swift_name("decodeShort()")));

/**
 * Decodes a string value.
 * Corresponding kind is [PrimitiveKind.STRING].
 */
- (NSString *)decodeString __attribute__((swift_name("decodeString()")));

/**
 * Context of the current serialization process, including contextual and polymorphic serialization and,
 * potentially, a format-specific configuration.
 */
@property (readonly) PDGBKotlinx_serialization_coreSerializersModule *serializersModule __attribute__((swift_name("serializersModule")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("KotlinRandom.Default")))
@interface PDGBKotlinRandomDefault : PDGBKotlinRandom
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (instancetype)init __attribute__((swift_name("init()"))) __attribute__((objc_designated_initializer)) __attribute__((unavailable));
+ (instancetype)new __attribute__((unavailable));
+ (instancetype)default_ __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBKotlinRandomDefault *shared __attribute__((swift_name("shared")));
- (int32_t)nextBitsBitCount:(int32_t)bitCount __attribute__((swift_name("nextBits(bitCount:)")));
- (BOOL)nextBoolean __attribute__((swift_name("nextBoolean()")));

/**
 * @note annotations
 *   kotlin.IgnorableReturnValue
*/
- (PDGBKotlinByteArray *)nextBytesArray:(PDGBKotlinByteArray *)array __attribute__((swift_name("nextBytes(array:)")));
- (PDGBKotlinByteArray *)nextBytesSize:(int32_t)size __attribute__((swift_name("nextBytes(size:)")));
- (PDGBKotlinByteArray *)nextBytesArray:(PDGBKotlinByteArray *)array fromIndex:(int32_t)fromIndex toIndex:(int32_t)toIndex __attribute__((swift_name("nextBytes(array:fromIndex:toIndex:)")));
- (double)nextDouble __attribute__((swift_name("nextDouble()")));
- (double)nextDoubleUntil:(double)until __attribute__((swift_name("nextDouble(until:)")));
- (double)nextDoubleFrom:(double)from until:(double)until __attribute__((swift_name("nextDouble(from:until:)")));
- (float)nextFloat __attribute__((swift_name("nextFloat()")));
- (int32_t)nextInt __attribute__((swift_name("nextInt()")));
- (int32_t)nextIntUntil:(int32_t)until __attribute__((swift_name("nextInt(until:)")));
- (int32_t)nextIntFrom:(int32_t)from until:(int32_t)until __attribute__((swift_name("nextInt(from:until:)")));
- (int64_t)nextLong __attribute__((swift_name("nextLong()")));
- (int64_t)nextLongUntil:(int64_t)until __attribute__((swift_name("nextLong(until:)")));
- (int64_t)nextLongFrom:(int64_t)from until:(int64_t)until __attribute__((swift_name("nextLong(from:until:)")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("KotlinByteArray")))
@interface PDGBKotlinByteArray : PDGBBase
+ (instancetype)arrayWithSize:(int32_t)size __attribute__((swift_name("init(size:)")));
+ (instancetype)arrayWithSize:(int32_t)size init:(PDGBByte *(^)(PDGBInt *))init __attribute__((swift_name("init(size:init:)")));
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
- (int8_t)getIndex:(int32_t)index __attribute__((swift_name("get(index:)")));
- (PDGBKotlinByteIterator *)iterator __attribute__((swift_name("iterator()")));
- (void)setIndex:(int32_t)index value:(int8_t)value __attribute__((swift_name("set(index:value:)")));
@property (readonly) int32_t size __attribute__((swift_name("size")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CorePlayerIdentity.Companion")))
@interface PDGBCorePlayerIdentityCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCorePlayerIdentityCompanion *shared __attribute__((swift_name("shared")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreGameRejection.Companion")))
@interface PDGBCoreGameRejectionCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCoreGameRejectionCompanion *shared __attribute__((swift_name("shared")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializerTypeParamsSerializers:(PDGBKotlinArray<id<PDGBKotlinx_serialization_coreKSerializer>> *)typeParamsSerializers __attribute__((swift_name("serializer(typeParamsSerializers:)")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreGamePhase.Companion")))
@interface PDGBCoreGamePhaseCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCoreGamePhaseCompanion *shared __attribute__((swift_name("shared")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializerTypeParamsSerializers:(PDGBKotlinArray<id<PDGBKotlinx_serialization_coreKSerializer>> *)typeParamsSerializers __attribute__((swift_name("serializer(typeParamsSerializers:)")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreCardRank.Companion")))
@interface PDGBCoreCardRankCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCoreCardRankCompanion *shared __attribute__((swift_name("shared")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializerTypeParamsSerializers:(PDGBKotlinArray<id<PDGBKotlinx_serialization_coreKSerializer>> *)typeParamsSerializers __attribute__((swift_name("serializer(typeParamsSerializers:)")));
@end


/** Public seat information. Fuse burnout steps and other hands never appear here. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CorePlayerView.Companion")))
@interface PDGBCorePlayerViewCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));

/** Public seat information. Fuse burnout steps and other hands never appear here. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCorePlayerViewCompanion *shared __attribute__((swift_name("shared")));

/** Public seat information. Fuse burnout steps and other hands never appear here. */
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreCard.Companion")))
@interface PDGBCoreCardCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCoreCardCompanion *shared __attribute__((swift_name("shared")));
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end


/** A face-down claim deliberately has neither card identifiers nor card ranks. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CorePublicClaim.Companion")))
@interface PDGBCorePublicClaimCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));

/** A face-down claim deliberately has neither card identifiers nor card ranks. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCorePublicClaimCompanion *shared __attribute__((swift_name("shared")));

/** A face-down claim deliberately has neither card identifiers nor card ranks. */
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end


/** Actions available to this view's recipient, rather than to any other player. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreAvailableActions.Companion")))
@interface PDGBCoreAvailableActionsCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));

/** Actions available to this view's recipient, rather than to any other player. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCoreAvailableActionsCompanion *shared __attribute__((swift_name("shared")));

/** Actions available to this view's recipient, rather than to any other player. */
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end


/** Public proof and outcome of one resolved challenge. */
__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("CoreRoundOutcome.Companion")))
@interface PDGBCoreRoundOutcomeCompanion : PDGBBase
+ (instancetype)alloc __attribute__((unavailable));

/** Public proof and outcome of one resolved challenge. */
+ (instancetype)allocWithZone:(struct _NSZone *)zone __attribute__((unavailable));
+ (instancetype)companion __attribute__((swift_name("init()")));
@property (class, readonly, getter=shared) PDGBCoreRoundOutcomeCompanion *shared __attribute__((swift_name("shared")));

/** Public proof and outcome of one resolved challenge. */
- (id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("serializer()")));
@end


/**
 * [CompositeEncoder] is a part of encoding process that is bound to a particular structured part of
 * the serialized form, described by the serial descriptor passed to [Encoder.beginStructure].
 *
 * All `encode*` methods have `index` and `serialDescriptor` parameters with a strict semantics and constraints:
 *   * `descriptor` is always the same as one used in [Encoder.beginStructure]. While this parameter may seem redundant,
 *      it is required for efficient serialization process to avoid excessive field spilling.
 *      If you are writing your own format, you can safely ignore this parameter and use one used in `beginStructure`
 *      for simplicity.
 *   * `index` of the element being encoded. This element at this index in the descriptor should be associated with
 *      the one being written.
 *
 * The symmetric interface for the deserialization process is [CompositeDecoder].
 *
 * ### Not stable for inheritance
 *
 * `CompositeEncoder` interface is not stable for inheritance in 3rd party libraries, as new methods
 * might be added to this interface or contracts of the existing methods can be changed.
 */
__attribute__((swift_name("Kotlinx_serialization_coreCompositeEncoder")))
@protocol PDGBKotlinx_serialization_coreCompositeEncoder
@required

/**
 * Encodes a boolean [value] associated with an element at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.BOOLEAN] kind.
 */
- (void)encodeBooleanElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(BOOL)value __attribute__((swift_name("encodeBooleanElement(descriptor:index:value:)")));

/**
 * Encodes a single byte [value] associated with an element at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.BYTE] kind.
 */
- (void)encodeByteElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(int8_t)value __attribute__((swift_name("encodeByteElement(descriptor:index:value:)")));

/**
 * Encodes a 16-bit unicode character [value] associated with an element at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.CHAR] kind.
 */
- (void)encodeCharElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(unichar)value __attribute__((swift_name("encodeCharElement(descriptor:index:value:)")));

/**
 * Encodes a 64-bit IEEE 754 floating point [value] associated with an element
 * at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.DOUBLE] kind.
 */
- (void)encodeDoubleElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(double)value __attribute__((swift_name("encodeDoubleElement(descriptor:index:value:)")));

/**
 * Encodes a 32-bit IEEE 754 floating point [value] associated with an element
 * at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.FLOAT] kind.
 */
- (void)encodeFloatElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(float)value __attribute__((swift_name("encodeFloatElement(descriptor:index:value:)")));

/**
 * Returns [Encoder] for decoding an underlying type of a value class in an inline manner.
 * Serializable value class is described by the [child descriptor][SerialDescriptor.getElementDescriptor]
 * of given [descriptor] at [index].
 *
 * Namely, for the `@Serializable @JvmInline value class MyInt(val my: Int)`,
 * and `@Serializable class MyData(val myInt: MyInt)` the following sequence is used:
 * ```
 * thisEncoder.encodeInlineElement(MyData.serializer.descriptor, 0).encodeInt(my)
 * ```
 *
 * This method provides an opportunity for the optimization to avoid boxing of a carried value
 * and its invocation should be equivalent to the following:
 * ```
 * thisEncoder.encodeSerializableElement(MyData.serializer.descriptor, 0, MyInt.serializer(), myInt)
 * ```
 *
 * Current encoder may return any other instance of [Encoder] class, depending on provided descriptor.
 * For example, when this function is called on Json encoder with descriptor that has
 * `UInt.serializer().descriptor` at the given [index], the returned encoder is able
 * to encode unsigned integers.
 *
 * Note that this function returns [Encoder] instead of the [CompositeEncoder]
 * because value classes always have the single property.
 * Calling [Encoder.beginStructure] on returned instance leads to an unspecified behavior and, in general, is prohibited.
 *
 * @see Encoder.encodeInline
 * @see SerialDescriptor.getElementDescriptor
 */
- (id<PDGBKotlinx_serialization_coreEncoder>)encodeInlineElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("encodeInlineElement(descriptor:index:)")));

/**
 * Encodes a 32-bit integer [value] associated with an element at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.INT] kind.
 */
- (void)encodeIntElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(int32_t)value __attribute__((swift_name("encodeIntElement(descriptor:index:value:)")));

/**
 * Encodes a 64-bit integer [value] associated with an element at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.LONG] kind.
 */
- (void)encodeLongElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(int64_t)value __attribute__((swift_name("encodeLongElement(descriptor:index:value:)")));

/**
 * Delegates nullable [value] encoding of the type [T] to the given [serializer].
 * [value] is associated with an element at the given [index] in [serial descriptor][descriptor].
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (void)encodeNullableSerializableElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index serializer:(id<PDGBKotlinx_serialization_coreSerializationStrategy>)serializer value:(id _Nullable)value __attribute__((swift_name("encodeNullableSerializableElement(descriptor:index:serializer:value:)")));

/**
 * Delegates [value] encoding of the type [T] to the given [serializer].
 * [value] is associated with an element at the given [index] in [serial descriptor][descriptor].
 */
- (void)encodeSerializableElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index serializer:(id<PDGBKotlinx_serialization_coreSerializationStrategy>)serializer value:(id _Nullable)value __attribute__((swift_name("encodeSerializableElement(descriptor:index:serializer:value:)")));

/**
 * Encodes a 16-bit short [value] associated with an element at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.SHORT] kind.
 */
- (void)encodeShortElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(int16_t)value __attribute__((swift_name("encodeShortElement(descriptor:index:value:)")));

/**
 * Encodes a string [value] associated with an element at the given [index] in [serial descriptor][descriptor].
 * The element at the given [index] should have [PrimitiveKind.STRING] kind.
 */
- (void)encodeStringElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index value:(NSString *)value __attribute__((swift_name("encodeStringElement(descriptor:index:value:)")));

/**
 * Denotes the end of the structure associated with current encoder.
 * For example, composite encoder of JSON format will write
 * a closing bracket in the underlying input and reduce the number of nesting for pretty printing.
 */
- (void)endStructureDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor __attribute__((swift_name("endStructure(descriptor:)")));

/**
 * Whether the format should encode values that are equal to the default values.
 * This method is used by plugin-generated serializers for properties with default values:
 * ```
 * @Serializable
 * class WithDefault(val int: Int = 42)
 * // serialize method
 * if (value.int != 42 || output.shouldEncodeElementDefault(serialDesc, 0)) {
 *    encoder.encodeIntElement(serialDesc, 0, value.int);
 * }
 * ```
 *
 * This method is never invoked for properties annotated with [EncodeDefault].
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (BOOL)shouldEncodeElementDefaultDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("shouldEncodeElementDefault(descriptor:index:)")));

/**
 * Context of the current serialization process, including contextual and polymorphic serialization and,
 * potentially, a format-specific configuration.
 */
@property (readonly) PDGBKotlinx_serialization_coreSerializersModule *serializersModule __attribute__((swift_name("serializersModule")));
@end


/**
 * [SerializersModule] is a collection of serializers used by [ContextualSerializer] and [PolymorphicSerializer]
 * to override or provide serializers at the runtime, whereas at the compile-time they provided by the serialization plugin.
 * It can be considered as a map where serializers can be found using their statically known KClasses.
 *
 * To enable runtime serializers resolution, one of the special annotations must be used on target types
 * ([Polymorphic] or [Contextual]), and a serial module with serializers should be used during construction of [SerialFormat].
 *
 * Serializers module can be built with `SerializersModule {}` builder function.
 * Empty module can be obtained with `EmptySerializersModule()` factory function.
 *
 * @see Contextual
 * @see Polymorphic
 */
__attribute__((swift_name("Kotlinx_serialization_coreSerializersModule")))
@interface PDGBKotlinx_serialization_coreSerializersModule : PDGBBase

/**
 * Copies contents of this module to the given [collector].
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (void)dumpToCollector:(id<PDGBKotlinx_serialization_coreSerializersModuleCollector>)collector __attribute__((swift_name("dumpTo(collector:)")));

/**
 * Returns a contextual serializer associated with a given [kClass].
 * If given class has generic parameters and module has provider for [kClass],
 * [typeArgumentsSerializers] are used to create serializer.
 * This method is used in context-sensitive operations on a property marked with [Contextual] by a [ContextualSerializer].
 *
 * @see SerializersModuleBuilder.contextual
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (id<PDGBKotlinx_serialization_coreKSerializer> _Nullable)getContextualKClass:(id<PDGBKotlinKClass>)kClass typeArgumentsSerializers:(NSArray<id<PDGBKotlinx_serialization_coreKSerializer>> *)typeArgumentsSerializers __attribute__((swift_name("getContextual(kClass:typeArgumentsSerializers:)")));

/**
 * Returns a polymorphic serializer registered for a class of the given [value] in the scope of [baseClass].
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (id<PDGBKotlinx_serialization_coreSerializationStrategy> _Nullable)getPolymorphicBaseClass:(id<PDGBKotlinKClass>)baseClass value:(id)value __attribute__((swift_name("getPolymorphic(baseClass:value:)")));

/**
 * Returns a polymorphic deserializer registered for a [serializedClassName] in the scope of [baseClass]
 * or default value constructed from [serializedClassName] if a default serializer provider was registered.
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (id<PDGBKotlinx_serialization_coreDeserializationStrategy> _Nullable)getPolymorphicBaseClass:(id<PDGBKotlinKClass>)baseClass serializedClassName:(NSString * _Nullable)serializedClassName __attribute__((swift_name("getPolymorphic(baseClass:serializedClassName:)")));
@end

__attribute__((swift_name("KotlinAnnotation")))
@protocol PDGBKotlinAnnotation
@required
@end


/**
 * Serial kind is an intrinsic property of [SerialDescriptor] that indicates how
 * the corresponding type is structurally represented by its serializer.
 *
 * Kind is used by serialization formats to determine how exactly the given type
 * should be serialized. For example, JSON format detects the kind of the value and,
 * depending on that, may write it as a plain value for primitive kinds, open a
 * curly brace '{' for class-like structures and square bracket '[' for list- and array- like structures.
 *
 * Kinds are used both during serialization, to serialize a value properly and statically, and
 * to introspect the type structure or build serialization schema.
 *
 * Kind should match the structure of the serialized form, not the structure of the corresponding Kotlin class.
 * Meaning that if serializable class `class IntPair(val left: Int, val right: Int)` is represented by the serializer
 * as a single `Long` value, its descriptor should have [PrimitiveKind.LONG] without nested elements even though the class itself
 * represents a structure with two primitive fields.
 */
__attribute__((swift_name("Kotlinx_serialization_coreSerialKind")))
@interface PDGBKotlinx_serialization_coreSerialKind : PDGBBase
- (NSUInteger)hash __attribute__((swift_name("hash()")));
- (NSString *)description __attribute__((swift_name("description()")));
@end


/**
 * [CompositeDecoder] is a part of decoding process that is bound to a particular structured part of
 * the serialized form, described by the serial descriptor passed to [Decoder.beginStructure].
 *
 * Typically, for unordered data, [CompositeDecoder] is used by a serializer withing a [decodeElementIndex]-based
 * loop that decodes all the required data one-by-one in any order and then terminates by calling [endStructure].
 * Please refer to [decodeElementIndex] for example of such loop.
 *
 * All `decode*` methods have `index` and `serialDescriptor` parameters with a strict semantics and constraints:
 *   * `descriptor` argument is always the same as one used in [Decoder.beginStructure].
 *   * `index` of the element being decoded. For [sequential][decodeSequentially] decoding, it is always a monotonic
 *      sequence from `0` to `descriptor.elementsCount` and for indexing-loop it is always an index that [decodeElementIndex]
 *      has returned from the last call.
 *
 * The symmetric interface for the serialization process is [CompositeEncoder].
 *
 * ### Not stable for inheritance
 *
 * `CompositeDecoder` interface is not stable for inheritance in 3rd party libraries, as new methods
 * might be added to this interface or contracts of the existing methods can be changed.
 */
__attribute__((swift_name("Kotlinx_serialization_coreCompositeDecoder")))
@protocol PDGBKotlinx_serialization_coreCompositeDecoder
@required

/**
 * Decodes a boolean value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.BOOLEAN] kind.
 */
- (BOOL)decodeBooleanElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeBooleanElement(descriptor:index:)")));

/**
 * Decodes a single byte value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.BYTE] kind.
 */
- (int8_t)decodeByteElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeByteElement(descriptor:index:)")));

/**
 * Decodes a 16-bit unicode character value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.CHAR] kind.
 */
- (unichar)decodeCharElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeCharElement(descriptor:index:)")));

/**
 * Method to decode collection size that may be called before the collection decoding.
 * Collection type includes [Collection], [Map] and [Array] (including primitive arrays).
 * Method can return `-1` if the size is not known in advance, though for [sequential decoding][decodeSequentially]
 * knowing precise size is a mandatory requirement.
 */
- (int32_t)decodeCollectionSizeDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor __attribute__((swift_name("decodeCollectionSize(descriptor:)")));

/**
 * Decodes a 64-bit IEEE 754 floating point value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.DOUBLE] kind.
 */
- (double)decodeDoubleElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeDoubleElement(descriptor:index:)")));

/**
 *  Decodes the index of the next element to be decoded.
 *  Index represents a position of the current element in the serial descriptor element that can be found
 *  with [SerialDescriptor.getElementIndex].
 *
 *  If this method returns non-negative index, the caller should call one of the `decode*Element` methods
 *  with a resulting index.
 *  Apart from positive values, this method can return [DECODE_DONE] to indicate that no more elements
 *  are left or [UNKNOWN_NAME] to indicate that symbol with an unknown name was encountered.
 *
 * Example of usage:
 * ```
 * class MyPair(i: Int, d: Double)
 *
 * object MyPairSerializer : KSerializer<MyPair> {
 *     // ... other methods omitted
 *
 *    fun deserialize(decoder: Decoder): MyPair {
 *        val composite = decoder.beginStructure(descriptor)
 *        var i: Int? = null
 *        var d: Double? = null
 *        while (true) {
 *            when (val index = composite.decodeElementIndex(descriptor)) {
 *                0 -> i = composite.decodeIntElement(descriptor, 0)
 *                1 -> d = composite.decodeDoubleElement(descriptor, 1)
 *                DECODE_DONE -> break // Input is over
 *                else -> error("Unexpected index: $index)
 *            }
 *        }
 *        composite.endStructure(descriptor)
 *        require(i != null && d != null)
 *        return MyPair(i, d)
 *    }
 * }
 * ```
 * This example is a rough equivalent of what serialization plugin generates for serializable pair class.
 *
 * The need in such a loop comes from unstructured nature of most serialization formats.
 * For example, JSON for the following input `{"d": 2.0, "i": 1}`, will first read `d` key with index `1`
 * and only after `i` with the index `0`.
 *
 * A potential implementation of this method for JSON format can be the following:
 * ```
 * fun decodeElementIndex(descriptor: SerialDescriptor): Int {
 *     // Ignore arrays
 *     val nextKey: String? = myStringJsonParser.nextKey()
 *     if (nextKey == null) return DECODE_DONE
 *     return descriptor.getElementIndex(nextKey) // getElementIndex can return UNKNOWN_NAME
 * }
 * ```
 *
 * If [decodeSequentially] returns `true`, the caller might skip calling this method.
 */
- (int32_t)decodeElementIndexDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor __attribute__((swift_name("decodeElementIndex(descriptor:)")));

/**
 * Decodes a 32-bit IEEE 754 floating point value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.FLOAT] kind.
 */
- (float)decodeFloatElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeFloatElement(descriptor:index:)")));

/**
 * Returns [Decoder] for decoding an underlying type of a value class in an inline manner.
 * Serializable value class is described by the [child descriptor][SerialDescriptor.getElementDescriptor]
 * of given [descriptor] at [index].
 *
 * Namely, for the `@Serializable @JvmInline value class MyInt(val my: Int)`,
 * and `@Serializable class MyData(val myInt: MyInt)` the following sequence is used:
 * ```
 * thisDecoder.decodeInlineElement(MyData.serializer().descriptor, 0).decodeInt()
 * ```
 *
 * This method provides an opportunity for the optimization to avoid boxing of a carried value
 * and its invocation should be equivalent to the following:
 * ```
 * thisDecoder.decodeSerializableElement(MyData.serializer.descriptor, 0, MyInt.serializer())
 * ```
 *
 * Current decoder may return any other instance of [Decoder] class, depending on the provided descriptor.
 * For example, when this function is called on `Json` decoder with descriptor that has
 * `UInt.serializer().descriptor` at the given [index], the returned decoder is able
 * to decode unsigned integers.
 *
 * Note that this function returns [Decoder] instead of the [CompositeDecoder]
 * because value classes always have the single property.
 * Calling [Decoder.beginStructure] on returned instance leads to an unspecified behavior and, in general, is prohibited.
 *
 * @see Decoder.decodeInline
 * @see SerialDescriptor.getElementDescriptor
 */
- (id<PDGBKotlinx_serialization_coreDecoder>)decodeInlineElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeInlineElement(descriptor:index:)")));

/**
 * Decodes a 32-bit integer value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.INT] kind.
 */
- (int32_t)decodeIntElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeIntElement(descriptor:index:)")));

/**
 * Decodes a 64-bit integer value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.LONG] kind.
 */
- (int64_t)decodeLongElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeLongElement(descriptor:index:)")));

/**
 * Decodes nullable value of the type [T] with the given [deserializer].
 *
 * If value at given [index] was already decoded with previous [decodeSerializableElement] call with the same index,
 * [previousValue] would contain a previously decoded value.
 * This parameter can be used to aggregate multiple values of the given property to the only one.
 * Implementation can safely ignore it and return a new value, efficiently using 'the last one wins' strategy,
 * or apply format-specific aggregating strategies, e.g. appending scattered Protobuf lists to a single one.
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (id _Nullable)decodeNullableSerializableElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index deserializer:(id<PDGBKotlinx_serialization_coreDeserializationStrategy>)deserializer previousValue:(id _Nullable)previousValue __attribute__((swift_name("decodeNullableSerializableElement(descriptor:index:deserializer:previousValue:)")));

/**
 * Checks whether the current decoder supports strictly ordered decoding of the data
 * without calling to [decodeElementIndex].
 * If the method returns `true`, the caller might skip [decodeElementIndex] calls
 * and start invoking `decode*Element` directly, incrementing the index of the element one by one.
 * This method can be called by serializers (either generated or user-defined) as a performance optimization,
 * but there is no guarantee that the method will be ever called. Practically, it means that implementations
 * that may benefit from sequential decoding should also support a regular [decodeElementIndex]-based decoding as well.
 *
 * Example of usage:
 * ```
 * class MyPair(i: Int, d: Double)
 *
 * object MyPairSerializer : KSerializer<MyPair> {
 *     // ... other methods omitted
 *
 *    fun deserialize(decoder: Decoder): MyPair {
 *        val composite = decoder.beginStructure(descriptor)
 *        if (composite.decodeSequentially()) {
 *            val i = composite.decodeIntElement(descriptor, index = 0) // Mind the sequential indexing
 *            val d = composite.decodeIntElement(descriptor, index = 1)
 *            composite.endStructure(descriptor)
 *            return MyPair(i, d)
 *        } else {
 *            // Fallback to `decodeElementIndex` loop, refer to its documentation for details
 *        }
 *    }
 * }
 * ```
 * This example is a rough equivalent of what serialization plugin generates for serializable pair class.
 *
 * Sequential decoding is a performance optimization for formats with strictly ordered schema,
 * usually binary ones. Regular formats such as JSON or ProtoBuf cannot use this optimization,
 * because e.g. in the latter example, the same data can be represented both as
 * `{"i": 1, "d": 1.0}` and `{"d": 1.0, "i": 1}` (thus, unordered).
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
- (BOOL)decodeSequentially __attribute__((swift_name("decodeSequentially()")));

/**
 * Decodes value of the type [T] with the given [deserializer].
 *
 * Implementations of [CompositeDecoder] may use their format-specific deserializers
 * for particular data types, e.g. handle [ByteArray] specifically if format is binary.
 *
 * If value at given [index] was already decoded with previous [decodeSerializableElement] call with the same index,
 * [previousValue] would contain a previously decoded value.
 * This parameter can be used to aggregate multiple values of the given property to the only one.
 * Implementation can safely ignore it and return a new value, effectively using 'the last one wins' strategy,
 * or apply format-specific aggregating strategies, e.g. appending scattered Protobuf lists to a single one.
 */
- (id _Nullable)decodeSerializableElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index deserializer:(id<PDGBKotlinx_serialization_coreDeserializationStrategy>)deserializer previousValue:(id _Nullable)previousValue __attribute__((swift_name("decodeSerializableElement(descriptor:index:deserializer:previousValue:)")));

/**
 * Decodes a 16-bit short value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.SHORT] kind.
 */
- (int16_t)decodeShortElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeShortElement(descriptor:index:)")));

/**
 * Decodes a string value from the underlying input.
 * The resulting value is associated with the [descriptor] element at the given [index].
 * The element at the given index should have [PrimitiveKind.STRING] kind.
 */
- (NSString *)decodeStringElementDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor index:(int32_t)index __attribute__((swift_name("decodeStringElement(descriptor:index:)")));

/**
 * Denotes the end of the structure associated with current decoder.
 * For example, composite decoder of JSON format will expect (and parse)
 * a closing bracket in the underlying input.
 */
- (void)endStructureDescriptor:(id<PDGBKotlinx_serialization_coreSerialDescriptor>)descriptor __attribute__((swift_name("endStructure(descriptor:)")));

/**
 * Context of the current decoding process, including contextual and polymorphic serialization and,
 * potentially, a format-specific configuration.
 */
@property (readonly) PDGBKotlinx_serialization_coreSerializersModule *serializersModule __attribute__((swift_name("serializersModule")));
@end

__attribute__((objc_subclassing_restricted))
__attribute__((swift_name("KotlinNothing")))
@interface PDGBKotlinNothing : PDGBBase
@end

__attribute__((swift_name("KotlinByteIterator")))
@interface PDGBKotlinByteIterator : PDGBBase <PDGBKotlinIterator>
- (instancetype)init __attribute__((swift_name("init()"))) __attribute__((objc_designated_initializer));
+ (instancetype)new __attribute__((availability(swift, unavailable, message="use object initializers instead")));
- (PDGBByte *)next __attribute__((swift_name("next()")));
- (int8_t)nextByte __attribute__((swift_name("nextByte()")));
@end


/**
 * [SerializersModuleCollector] can introspect and accumulate content of any [SerializersModule] via [SerializersModule.dumpTo],
 * using a visitor-like pattern: [contextual] and [polymorphic] functions are invoked for each registered serializer.
 *
 * ### Not stable for inheritance
 *
 * `SerializersModuleCollector` interface is not stable for inheritance in 3rd party libraries, as new methods
 * might be added to this interface or contracts of the existing methods can be changed.
 *
 * @note annotations
 *   kotlinx.serialization.ExperimentalSerializationApi
*/
__attribute__((swift_name("Kotlinx_serialization_coreSerializersModuleCollector")))
@protocol PDGBKotlinx_serialization_coreSerializersModuleCollector
@required

/**
 * Accept a provider, associated with generic [kClass] for contextual serialization.
 */
- (void)contextualKClass:(id<PDGBKotlinKClass>)kClass provider:(id<PDGBKotlinx_serialization_coreKSerializer> (^)(NSArray<id<PDGBKotlinx_serialization_coreKSerializer>> *))provider __attribute__((swift_name("contextual(kClass:provider:)")));

/**
 * Accept a serializer, associated with [kClass] for contextual serialization.
 */
- (void)contextualKClass:(id<PDGBKotlinKClass>)kClass serializer:(id<PDGBKotlinx_serialization_coreKSerializer>)serializer __attribute__((swift_name("contextual(kClass:serializer:)")));

/**
 * Accept a serializer, associated with [actualClass] for polymorphic serialization.
 */
- (void)polymorphicBaseClass:(id<PDGBKotlinKClass>)baseClass actualClass:(id<PDGBKotlinKClass>)actualClass actualSerializer:(id<PDGBKotlinx_serialization_coreKSerializer>)actualSerializer __attribute__((swift_name("polymorphic(baseClass:actualClass:actualSerializer:)")));

/**
 * Accept a default deserializer provider, associated with the [baseClass] for polymorphic deserialization.
 *
 * This function affect only deserialization process. To avoid confusion, it was deprecated and replaced with [polymorphicDefaultDeserializer].
 * To affect serialization process, use [SerializersModuleCollector.polymorphicDefaultSerializer].
 *
 * [defaultDeserializerProvider] is invoked when no polymorphic serializers associated with the `className`
 * in the scope of [baseClass] were found. `className` could be `null` for formats that support nullable class discriminators
 * (currently only `Json` with `useArrayPolymorphism` set to `false`).
 *
 * [defaultDeserializerProvider] can be stateful and lookup a serializer for the missing type dynamically.
 *
 * @see SerializersModuleCollector.polymorphicDefaultDeserializer
 * @see SerializersModuleCollector.polymorphicDefaultSerializer
 */
- (void)polymorphicDefaultBaseClass:(id<PDGBKotlinKClass>)baseClass defaultDeserializerProvider:(id<PDGBKotlinx_serialization_coreDeserializationStrategy> _Nullable (^)(NSString * _Nullable))defaultDeserializerProvider __attribute__((swift_name("polymorphicDefault(baseClass:defaultDeserializerProvider:)"))) __attribute__((deprecated("Deprecated in favor of function with more precise name: polymorphicDefaultDeserializer")));

/**
 * Accept a default deserializer provider, associated with the [baseClass] for polymorphic deserialization.
 * [defaultDeserializerProvider] is invoked when no polymorphic serializers associated with the `className`
 * in the scope of [baseClass] were found. `className` could be `null` for formats that support nullable class discriminators
 * (currently only `Json` with `useArrayPolymorphism` set to `false`).
 *
 * Default deserializers provider affects only deserialization process. Serializers are accepted in the
 * [SerializersModuleCollector.polymorphicDefaultSerializer] method.
 *
 * [defaultDeserializerProvider] can be stateful and lookup a serializer for the missing type dynamically.
 */
- (void)polymorphicDefaultDeserializerBaseClass:(id<PDGBKotlinKClass>)baseClass defaultDeserializerProvider:(id<PDGBKotlinx_serialization_coreDeserializationStrategy> _Nullable (^)(NSString * _Nullable))defaultDeserializerProvider __attribute__((swift_name("polymorphicDefaultDeserializer(baseClass:defaultDeserializerProvider:)")));

/**
 * Accept a default serializer provider, associated with the [baseClass] for polymorphic serialization.
 * [defaultSerializerProvider] is invoked when no polymorphic serializers for `value` in the scope of [baseClass] were found.
 *
 * Default serializers provider affects only serialization process. Deserializers are accepted in the
 * [SerializersModuleCollector.polymorphicDefaultDeserializer] method.
 *
 * [defaultSerializerProvider] can be stateful and lookup a serializer for the missing type dynamically.
 */
- (void)polymorphicDefaultSerializerBaseClass:(id<PDGBKotlinKClass>)baseClass defaultSerializerProvider:(id<PDGBKotlinx_serialization_coreSerializationStrategy> _Nullable (^)(id))defaultSerializerProvider __attribute__((swift_name("polymorphicDefaultSerializer(baseClass:defaultSerializerProvider:)")));
@end

__attribute__((swift_name("KotlinKDeclarationContainer")))
@protocol PDGBKotlinKDeclarationContainer
@required
@end

__attribute__((swift_name("KotlinKAnnotatedElement")))
@protocol PDGBKotlinKAnnotatedElement
@required
@end


/**
 * @note annotations
 *   kotlin.SinceKotlin(version="1.1")
*/
__attribute__((swift_name("KotlinKClassifier")))
@protocol PDGBKotlinKClassifier
@required
@end

__attribute__((swift_name("KotlinKClass")))
@protocol PDGBKotlinKClass <PDGBKotlinKDeclarationContainer, PDGBKotlinKAnnotatedElement, PDGBKotlinKClassifier>
@required

/**
 * @note annotations
 *   kotlin.SinceKotlin(version="1.1")
*/
- (BOOL)isInstanceValue:(id _Nullable)value __attribute__((swift_name("isInstance(value:)")));
@property (readonly) NSString * _Nullable qualifiedName __attribute__((swift_name("qualifiedName")));
@property (readonly) NSString * _Nullable simpleName __attribute__((swift_name("simpleName")));
@end

#pragma pop_macro("_Nullable_result")
#pragma clang diagnostic pop
NS_ASSUME_NONNULL_END
