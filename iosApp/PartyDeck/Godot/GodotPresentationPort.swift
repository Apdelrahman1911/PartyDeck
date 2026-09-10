import Foundation
import PartyDeckKit
import UIKit

/// A disposable native presentation of the existing Kotlin session. This type owns no game rules.
final class GodotPresentationPort: NSObject, IosGodotNativePort {
    private weak var presenter: UIViewController?
    private weak var registration: IosGodotRegistration?
    private let configuration: GodotPresentationConfiguration
    private var engineOwner: PDGodotEngineOwner?
    private var active: Lifetime?
    private var lastClosed: (id: String, success: Bool)?
    private var unacquiredPresentationID: String?
    private var sceneForeground = false
    private var sceneBackgrounded = false
    private var quarantined = false
    private var disposed = false
    #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
    private var qualificationIdentityBaseline: [String: String] = [:]
    #endif

    init(presenter: UIViewController, configuration: GodotPresentationConfiguration = .bundled()) {
        self.presenter = presenter
        self.configuration = configuration
        super.init()
    }

    func attachRegistration(_ value: IosGodotRegistration?) {
        requireMainThread()
        guard !disposed else { value?.close(); return }
        registration = value
        publishAvailability()
    }

    /// Scene facts also reach a retiring/dormant engine, after Kotlin has stopped updating its handle.
    func setSceneLifecycle(foreground: Bool, backgrounded: Bool) {
        requireMainThread()
        guard !disposed else { return }
        let changed = sceneForeground != foreground || sceneBackgrounded != backgrounded
        sceneForeground = foreground
        sceneBackgrounded = backgrounded
        if let lifetime = active, !lifetime.closing {
            if changed { lifetime.screen?.conceal() }
            applyLifecycle(lifetime)
        } else {
            engineOwner?.setApplicationActive(foreground && !backgrounded, backgrounded: backgrounded)
        }
    }

    func prepare(
        presentationId: String,
        launchDocument: String,
        isForeground: Bool,
        isBackgrounded: Bool,
        callbacks: any IosGodotNativeCallbacks,
        completion: any IosGodotNativeCompletion
    ) {
        requireMainThread()
        guard !disposed, !quarantined, active == nil,
              sceneForeground, !sceneBackgrounded, isForeground, !isBackgrounded,
              let project = configuration.projectURL, let pack = configuration.packURL,
              let mode = launchMode(launchDocument, presentationID: presentationId),
              configuration.enabledModes.contains(mode),
              let presenter, presenter.viewIfLoaded?.window != nil,
              presenter.presentedViewController == nil,
              !presenter.isBeingPresented, !presenter.isBeingDismissed else {
            // No native acquisition occurred; a subsequent close for this attempt is already clean.
            unacquiredPresentationID = presentationId
            completion.complete(success: false)
            return
        }

        let lifetime = Lifetime(
            id: presentationId, callbacks: callbacks, completion: completion,
            foreground: isForeground, backgrounded: isBackgrounded
        )
        active = lifetime
        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        lifetime.qualificationMode = mode.rawValue
        #endif
        unacquiredPresentationID = nil
        let owner = engineOwner ?? PDGodotEngineOwner()
        engineOwner = owner
        do {
            let created: PDGodotPresentation? = try owner.createPresentation(
                withProjectPath: project.path, packPath: pack.path, launchDocument: launchDocument
            )
            guard let native = created, native.presentationID == presentationId,
                  let controller = native.viewController else {
                preparationFailed(lifetime)
                return
            }
            lifetime.native = native
            native.eventHandler = { [weak self, weak lifetime] document in
                guard let self, let lifetime, self.isCurrent(lifetime) else { return }
                self.requireMainThread()
                guard document.utf8.count <= Self.maximumEventBytes else { self.fail(lifetime); return }
                lifetime.callbacks?.event(document: document)
            }
            native.lifecycleHandler = { [weak self, weak lifetime] generation, foreground, backgrounded in
                guard let self, let lifetime, self.isCurrent(lifetime) else { return }
                self.requireMainThread()
                guard let generation = Int64(exactly: generation) else { self.fail(lifetime); return }
                lifetime.observedLifecycle = NativeLifecycle(
                    generation: generation, foreground: foreground, backgrounded: backgrounded
                )
                if !lifetime.applyingLifecycle { self.publishLifecycle(lifetime) }
            }
            native.failureHandler = { [weak self, weak lifetime] in
                guard let self, let lifetime, self.isCurrent(lifetime) else { return }
                self.requireMainThread()
                self.fail(lifetime)
            }

            let screen = GodotPresentationViewController(nativeController: controller)
            lifetime.screen = screen
            screen.onVisibilityChanged = { [weak self, weak lifetime] visible in
                guard let self, let lifetime, self.isCurrent(lifetime) else { return }
                lifetime.visible = visible
                lifetime.screen?.conceal()
                self.applyLifecycle(lifetime)
            }
            screen.onReturn = { [weak self, weak lifetime] action in
                guard let self, let lifetime, self.isCurrent(lifetime) else { return }
                self.requestReturn(lifetime, action: action)
            }
            screen.onUnexpectedDismissal = { [weak self, weak lifetime] in
                guard let self, let lifetime, self.isCurrent(lifetime) else { return }
                self.requestReturn(lifetime, action: .standard)
            }
            screen.loadViewIfNeeded()
            applyLifecycle(lifetime)
            guard isCurrent(lifetime), lifetime.publishedLifecycle != nil else {
                lifetime.preparation?.finish(false)
                return
            }
            lifetime.presentationRequested = true
            presenter.present(screen, animated: false) { [weak self, weak lifetime, weak screen] in
                guard let self, let lifetime, self.active === lifetime, !lifetime.finished else {
                    // A timed-out presentation may finish appearing after its lifetime retired.
                    // Dismiss only that obsolete screen, never a replacement presentation.
                    if let screen, screen.presentingViewController != nil {
                        screen.beginClosing()
                        screen.dismiss(animated: false)
                    }
                    return
                }
                self.requireMainThread()
                lifetime.presentationCompleted = true
                if lifetime.closing {
                    self.dismiss(lifetime)
                    return
                }
                self.publishLifecycle(lifetime)
                guard self.isCurrent(lifetime) else { return }
                let prepared = lifetime.preparation
                lifetime.preparation = nil
                prepared?.finish(lifetime.publishedLifecycle != nil)
            }
        } catch {
            // Native may have acquired process resources before rejecting; quarantine until shutdown.
            preparationFailed(lifetime)
        }
    }

    func updateLifecycle(presentationId: String, isForeground: Bool, isBackgrounded: Bool) -> Bool {
        requireMainThread()
        guard let lifetime = active, lifetime.id == presentationId, isCurrent(lifetime) else { return false }
        if lifetime.hostForeground != isForeground || lifetime.hostBackgrounded != isBackgrounded {
            lifetime.screen?.conceal()
        }
        lifetime.hostForeground = isForeground
        lifetime.hostBackgrounded = isBackgrounded
        applyLifecycle(lifetime)
        return isCurrent(lifetime) && lifetime.publishedLifecycle != nil
    }

    func deliver(
        presentationId: String,
        commandDocument: String,
        lifecycleGeneration: Int64,
        confirmReady: Bool,
        completion: any IosGodotNativeCompletion
    ) {
        requireMainThread()
        guard let lifetime = active, lifetime.id == presentationId, isCurrent(lifetime),
              let native = lifetime.native, lifetime.delivery == nil,
              commandDocument.utf8.count <= Self.maximumCommandBytes,
              lifecycleGeneration >= 0 else {
            completion.complete(success: false)
            return
        }
        guard lifetime.publishedLifecycle?.generation == lifecycleGeneration,
              native.lifecycleGeneration == UInt64(lifecycleGeneration) else {
            publishLifecycle(lifetime)
            completion.complete(success: false)
            return
        }

        let delivery = Delivery(completion: completion, foreground: foregroundGrant(commandDocument))
        lifetime.delivery = delivery
        if delivery.foreground == false { lifetime.screen?.conceal() }
        native.deliverDocument(
            commandDocument, lifecycleGeneration: UInt64(lifecycleGeneration), confirmReady: confirmReady
        ) { [weak self, weak lifetime, weak delivery] delivered in
            guard let self, let lifetime, let delivery,
                  self.isCurrent(lifetime), lifetime.delivery === delivery else { return }
            self.requireMainThread()
            lifetime.delivery = nil
            // An intervening lifecycle is visible to common before a superseded completion.
            self.publishLifecycle(lifetime)
            guard self.isCurrent(lifetime) else { delivery.completion.finish(false); return }
            if delivered && confirmReady { lifetime.readyConfirmed = true }
            if delivered, delivery.foreground == true, lifetime.readyConfirmed,
               let lifecycle = lifetime.publishedLifecycle,
               lifecycle.generation == lifecycleGeneration, lifecycle.foreground, !lifecycle.backgrounded {
                lifetime.screen?.allowNativePresentation()
            }
            delivery.completion.finish(delivered)
        }
    }

    func close(presentationId: String, completion: any IosGodotNativeCompletion) {
        requireMainThread()
        if let lifetime = active, lifetime.id == presentationId, !lifetime.finished {
            if lifetime.closing {
                if lifetime.closure == nil { lifetime.closure = Completion(completion) }
                else { completion.complete(success: false) }
            } else {
                beginClose(lifetime, completion: Completion(completion))
            }
            return
        }
        if let lastClosed, lastClosed.id == presentationId {
            completion.complete(success: lastClosed.success)
        } else {
            completion.complete(success: unacquiredPresentationID == presentationId)
        }
    }

    /// Permanent owner disposal. It cannot restore the retained engine or create a new session.
    func shutdown() {
        requireMainThread()
        guard !disposed else { return }
        disposed = true
        publishAvailability()
        registration = nil
        if let lifetime = active {
            if !lifetime.closing { beginClose(lifetime, completion: nil) }
            lifetime.screen?.beginClosing()
        }
        engineOwner?.shutdown()
        presenter = nil
    }

    private func applyLifecycle(_ lifetime: Lifetime) {
        guard isCurrent(lifetime), let native = lifetime.native, let owner = engineOwner else { return }
        let backgrounded = sceneBackgrounded || lifetime.hostBackgrounded
        let foreground = sceneForeground && lifetime.hostForeground && !backgrounded
        lifetime.applyingLifecycle = true
        // Revoke native permission before changing application facts; gains stay under both covers.
        if !foreground || !lifetime.visible { native.setForeground(false) }
        owner.setApplicationActive(foreground, backgrounded: backgrounded)
        native.setForeground(lifetime.visible)
        lifetime.applyingLifecycle = false
        publishLifecycle(lifetime)
    }

    private func publishLifecycle(_ lifetime: Lifetime) {
        guard isCurrent(lifetime), let native = lifetime.native else { return }
        guard let generation = Int64(exactly: native.lifecycleGeneration) else { fail(lifetime); return }
        var observed = lifetime.observedLifecycle
        if observed?.generation != generation {
            let snapshot = native.snapshot()
            guard let foreground = snapshot["nativeForeground"] as? Bool,
                  let backgrounded = snapshot["applicationBackgrounded"] as? Bool else { fail(lifetime); return }
            observed = NativeLifecycle(generation: generation, foreground: foreground, backgrounded: backgrounded)
        }
        guard let observed else { fail(lifetime); return }
        let previous = lifetime.publishedLifecycle
        if let previous, observed.generation < previous.generation { fail(lifetime); return }
        if observed != previous { lifetime.screen?.conceal() }
        lifetime.observedLifecycle = observed
        lifetime.publishedLifecycle = observed
        lifetime.callbacks?.lifecycleChanged(
            generation: observed.generation, isForeground: observed.foreground, isBackgrounded: observed.backgrounded
        )
    }

    private func requestReturn(_ lifetime: Lifetime, action: GodotTableReturn) {
        guard isCurrent(lifetime), !lifetime.returnRequested else { return }
        lifetime.returnRequested = true
        lifetime.screen?.conceal()
        let callbacks = lifetime.callbacks
        switch action {
        case .leave: callbacks?.exitRequested()
        case .standard: callbacks?.useCompose()
        }
        if isCurrent(lifetime) { beginClose(lifetime, completion: nil) }
    }

    private func fail(_ lifetime: Lifetime) {
        guard isCurrent(lifetime), !lifetime.failureReported else { return }
        lifetime.failureReported = true
        lifetime.screen?.conceal()
        lifetime.callbacks?.failed()
        if isCurrent(lifetime) { beginClose(lifetime, completion: nil) }
    }

    private func preparationFailed(_ lifetime: Lifetime) {
        quarantined = true
        lifetime.nativeCleaned = false
        let prepared = lifetime.preparation
        lifetime.preparation = nil
        beginClose(lifetime, completion: nil)
        engineOwner?.shutdown()
        prepared?.finish(false)
    }

    private func beginClose(_ lifetime: Lifetime, completion: Completion?) {
        guard active === lifetime, !lifetime.closing, !lifetime.finished else { return }
        lifetime.closing = true
        lifetime.closure = completion
        lifetime.callbacks = nil
        lifetime.screen?.beginClosing()
        lifetime.native?.eventHandler = nil
        lifetime.native?.lifecycleHandler = nil
        lifetime.native?.failureHandler = nil
        publishAvailability()
        let prepared = lifetime.preparation
        lifetime.preparation = nil
        let delivery = lifetime.delivery
        lifetime.delivery = nil
        prepared?.finish(false)
        delivery?.completion.finish(false)

        let deadline = DispatchWorkItem { [weak self, weak lifetime] in
            guard let self, let lifetime, self.active === lifetime, !lifetime.finished else { return }
            self.finishClose(lifetime, success: false)
            self.engineOwner?.shutdown()
        }
        lifetime.closeDeadline = deadline
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.closeTimeout, execute: deadline)
        if let native = lifetime.native {
            native.close(completion: { [weak self, weak lifetime] dormant in
                guard let self, let lifetime, self.active === lifetime, !lifetime.finished else { return }
                self.requireMainThread()
                lifetime.nativeCleaned = dormant
                if dormant { lifetime.screen?.detachNativeController() }
                self.dismiss(lifetime)
                self.completeCloseIfPossible(lifetime)
            })
        } else {
            // No handle after an attempted native acquisition is not proof of a dormant engine.
            lifetime.nativeCleaned = false
        }
        dismiss(lifetime)
        completeCloseIfPossible(lifetime)
    }

    private func dismiss(_ lifetime: Lifetime) {
        guard active === lifetime, lifetime.closing, !lifetime.finished, !lifetime.dismissalRequested else { return }
        if lifetime.presentationRequested && !lifetime.presentationCompleted { return }
        guard let screen = lifetime.screen, screen.presentingViewController != nil else {
            lifetime.dismissed = true
            completeCloseIfPossible(lifetime)
            return
        }
        lifetime.dismissalRequested = true
        screen.dismiss(animated: false) { [weak self, weak lifetime] in
            guard let self, let lifetime, self.active === lifetime, !lifetime.finished else { return }
            self.requireMainThread()
            lifetime.dismissed = true
            self.completeCloseIfPossible(lifetime)
        }
    }

    private func completeCloseIfPossible(_ lifetime: Lifetime) {
        if lifetime.dismissed, let cleaned = lifetime.nativeCleaned { finishClose(lifetime, success: cleaned) }
    }

    private func finishClose(_ lifetime: Lifetime, success: Bool) {
        guard active === lifetime, !lifetime.finished else { return }
        lifetime.finished = true
        lifetime.closeDeadline?.cancel()
        lifetime.closeDeadline = nil
        if !success {
            quarantined = true
            // The surface remains opaque even if UIKit/native teardown missed its deadline.
            lifetime.screen?.beginClosing()
            if lifetime.presentationCompleted { lifetime.screen?.dismiss(animated: false) }
        }
        let completion = lifetime.closure
        lifetime.closure = nil
        lifetime.callbacks = nil
        lifetime.native = nil
        lifetime.screen = nil
        active = nil
        lastClosed = (lifetime.id, success)
        publishAvailability()
        // Completing into Main.immediate may synchronously open the next presentation.
        completion?.finish(success)
    }

    private func publishAvailability() {
        let modes = !disposed && !quarantined && active?.closing != true ? configuration.enabledModes : []
        registration?.setAvailability(twoD: modes.contains(.twoD), threeD: modes.contains(.threeD))
    }

    private func isCurrent(_ lifetime: Lifetime) -> Bool {
        !disposed && active === lifetime && !lifetime.closing && !lifetime.finished
    }

    private func launchMode(_ document: String, presentationID: String) -> GodotPresentationMode? {
        guard document.utf8.count <= Self.maximumCommandBytes,
              let data = document.data(using: .utf8),
              let launch = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              launch["type"] as? String == "launch", launch["presentationId"] as? String == presentationID,
              let name = launch["presentationMode"] as? String else { return nil }
        // The native strict codec validates the full trusted launch before any engine acquisition.
        return GodotPresentationMode(rawValue: name)
    }

    private func foregroundGrant(_ document: String) -> Bool? {
        guard let data = document.data(using: .utf8),
              let command = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              command["type"] as? String == "foreground" else { return nil }
        return command["isForeground"] as? Bool
    }

    #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
    /// Reads fixed observations and requests existing diagnostics; never acquires an owner or sends an intent.
    func sessionQualificationObservation() -> [String: Any] {
        requireMainThread()
        let activationValid = configuration.activationProfile == .qualification && !configuration.enabledModes.isEmpty
        var output: [String: Any] = [
            "activationValid": activationValid, "profile": configuration.activationProfile?.rawValue ?? "invalid",
            "enabledModes": configuration.enabledModes.map(\.rawValue).sorted(),
            "ownerCreated": engineOwner != nil, "active": active != nil,
            "closing": active?.closing == true, "quarantined": quarantined, "disposed": disposed,
            "portReadyConfirmed": active?.readyConfirmed == true,
            "native": NSNull(), "geometry": NSNull(), "renderer": NSNull(),
        ]
        if let lastClosed { output["lastCloseSucceeded"] = lastClosed.success }
        else { output["lastCloseSucceeded"] = NSNull() }
        guard activationValid, let engineOwner else { return output }
        let raw = engineOwner.snapshot()
        // Explicit allowlist. Addresses, state documents, paths and raw failure text never leave here.
        let nativeKeys = ["bootstrapCount", "processIdentifier", "presentationGeneration", "lifecycleGeneration",
            "inputGeneration", "readyEvents", "intentEvents", "exitEvents", "rejectedEvents", "nativePresentedFrames",
            "nativeFailedPresentations", "iterations", "drawCalls", "authorityReadyConfirmed", "nativeForeground",
            "authorityForegroundGrant", "applicationBackgrounded", "inputViewEnabled", "privacyCoverVisible",
            "renderLoopActive", "dormant", "emptyTree", "surfaceAttached", "surfaceAccessibilityHidden",
            "queuedCommands", "queuedEvents", "queuedBytes", "surfaceSize", "retainedEnginePolicy", "quarantined"]
        var native: [String: Any] = [:]
        for key in nativeKeys { native[key] = raw[key] ?? NSNull() }
        if let failure = raw["failure"] as? String { native["failurePresent"] = !failure.isEmpty }
        else { native["failurePresent"] = NSNull() }
        let identityKeys = ["engineIdentity", "controllerIdentity", "viewIdentity", "layerIdentity"]
        var currentIdentities: [String: String] = [:]
        for key in identityKeys {
            if let value = raw[key] as? String, !value.isEmpty, value != "0x0", value != "(nil)" {
                currentIdentities[key] = value
            }
        }
        if qualificationIdentityBaseline.isEmpty, currentIdentities.count == identityKeys.count,
           raw["mainStarted"] as? Bool == true, raw["surfaceAttached"] as? Bool == true {
            qualificationIdentityBaseline = currentIdentities
        }
        native["retainedIdentitiesMatchFirstEntry"] = currentIdentities.count == identityKeys.count &&
            !qualificationIdentityBaseline.isEmpty && currentIdentities == qualificationIdentityBaseline
        output["native"] = native
        if let geometry = active?.screen?.sessionQualificationGeometry(), !geometry.isEmpty {
            output["geometry"] = geometry
        }
        if let lifetime = active, isCurrent(lifetime), let nativePresentation = lifetime.native,
           let diagnostics = raw["rendererDiagnostics"] as? [String: Any],
           let mode = lifetime.qualificationMode, let lifecycle = lifetime.publishedLifecycle,
           diagnostics["presentationId"] as? String == lifetime.id,
           diagnostics["presentationMode"] as? String == mode,
           raw["lifecycleGeneration"] as? String == String(lifecycle.generation) {
            // Native validates current identity/revision/foreground, complete schema and sequence.
            // The raw presentation ID is used for correlation above and is never exported.
            var renderer: [String: Any] = [:]
            let keys = ["schemaVersion", "requestId", "sequence", "revision", "presentationMode", "coordinateSpace",
                        "foreground", "viewport", "sceneStateApplied", "handConcealed", "selectedCount", "privateFaceCount", "privateLabelCount", "controls"]
            for key in keys { renderer[key] = diagnostics[key] ?? NSNull() }
            output["renderer"] = renderer
            if sceneForeground && !sceneBackgrounded && lifetime.visible && lifetime.readyConfirmed {
                _ = nativePresentation.requestRendererDiagnostics()
            }
        } else if let lifetime = active, isCurrent(lifetime), lifetime.visible, lifetime.readyConfirmed,
                  sceneForeground && !sceneBackgrounded {
            _ = lifetime.native?.requestRendererDiagnostics()
        }
        return output
    }

    func setSessionQualificationValue(_ document: String) {
        requireMainThread()
        active?.screen?.setSessionQualificationValue(document)
    }
    #endif

    private func requireMainThread() { precondition(Thread.isMainThread) }

    private struct NativeLifecycle: Equatable {
        let generation: Int64
        let foreground: Bool
        let backgrounded: Bool
    }

    private final class Completion {
        private var callback: (any IosGodotNativeCompletion)?
        init(_ callback: any IosGodotNativeCompletion) { self.callback = callback }
        func finish(_ success: Bool) {
            let callback = callback
            self.callback = nil
            callback?.complete(success: success)
        }
    }

    private final class Delivery {
        let completion: Completion
        let foreground: Bool?
        init(completion: any IosGodotNativeCompletion, foreground: Bool?) {
            self.completion = Completion(completion)
            self.foreground = foreground
        }
    }

    private final class Lifetime {
        let id: String
        var callbacks: (any IosGodotNativeCallbacks)?
        var preparation: Completion?
        var delivery: Delivery?
        var closure: Completion?
        var native: PDGodotPresentation?
        var screen: GodotPresentationViewController?
        var observedLifecycle: NativeLifecycle?
        var publishedLifecycle: NativeLifecycle?
        var closeDeadline: DispatchWorkItem?
        var hostForeground: Bool
        var hostBackgrounded: Bool
        var visible = false
        var applyingLifecycle = false
        var readyConfirmed = false
        var returnRequested = false
        var failureReported = false
        var presentationRequested = false
        var presentationCompleted = false
        var dismissalRequested = false
        var dismissed = false
        var nativeCleaned: Bool?
        var closing = false
        var finished = false
        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        var qualificationMode: String?
        #endif

        init(id: String, callbacks: any IosGodotNativeCallbacks, completion: any IosGodotNativeCompletion,
             foreground: Bool, backgrounded: Bool) {
            self.id = id
            self.callbacks = callbacks
            preparation = Completion(completion)
            hostForeground = foreground
            hostBackgrounded = backgrounded
        }
    }

    private static let maximumCommandBytes = 65_536
    private static let maximumEventBytes = 4_096
    private static let closeTimeout: TimeInterval = 2.5
}
