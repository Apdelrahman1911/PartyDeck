import Combine
import Foundation
import PartyDeckGodotBridge
import UIKit

// The real qualification facade owns all rules and recipient projections. This
// host owns only native lifetimes, bounded command delivery, and observations.
// Native completions run on the main thread but import as nonisolated. Their
// checked actor scopes run inline so cancellation and close ordering stay real.
@MainActor
final class RetainedModel: ObservableObject {
    let owner = PDGodotEngineOwner()
    @Published private(set) var state = "idle"
    @Published private(set) var observations = "{}"
    @Published private(set) var errorMessage = ""
    @Published private(set) var pausedByUser = false
    @Published private(set) var mode = ""
    @Published private(set) var presentationID = ""
    @Published private(set) var showEngine = false
    @Published private(set) var hostCounter = 0

    private var active: Entry?
    private var retired: [Entry] = []
    private var pendingMode: String?
    private var entryCount = 0
    private var pollCount = 0
    private var pumpHoldDepth = 0
    private var applicationActive = true
    private var applicationBackgrounded = false
    private var applicationBackgroundCount = 0
    private var applicationForegroundCount = 0
    private var focusCycleCount = 0
    private var lastDiagnosticRequestAt: TimeInterval = 0
    private var lastClosure: [String: Any] = [:]
    private var staleProbe: [String: Any] = [:]
    private var journal: [[String: Any]] = []
    private let runID = UUID().uuidString
    private let startedAt = Date().timeIntervalSince1970

    var canEnter: Bool { active == nil && errorMessage.isEmpty && (state == "idle" || state == "dormant") }
    var canProbeOldHandle: Bool { active != nil && !retired.isEmpty }
    var viewController: UIViewController? { active?.native.viewController }

    init() {
        switch ProcessInfo.processInfo.arguments.first(where: { $0.hasPrefix("--host-idle-timer=") }) ?? "" {
        case "--host-idle-timer=on": UIApplication.shared.isIdleTimerDisabled = true
        case "--host-idle-timer=off": UIApplication.shared.isIdleTimerDisabled = false
        default: break
        }
    }

    func start(mode selectedMode: String) {
        guard canEnter, selectedMode == "2d" || selectedMode == "3d" else { return }
        do {
            let resources = try inputs()
            let id = UUID().uuidString
            let facade = try newFacade(id: id, mode: selectedMode)
            let created: PDGodotPresentation? = try owner.createPresentation(
                withProjectPath: resources.project, packPath: resources.pack, launchDocument: facade.launchDocument
            )
            guard let native = created, native.presentationID == id, native.viewController != nil else {
                _ = try facade.close()
                throw HostFailure.preparation
            }
            entryCount += 1
            let entry = Entry(id: id, ordinal: entryCount, mode: selectedMode, native: native, authority: facade)
            active = entry
            mode = selectedMode
            presentationID = id
            pausedByUser = false
            staleProbe = [:]
            entry.preparedNative = native.snapshot()
            copyStatus(facade.status(), into: entry)
            native.eventHandler = { [weak self, weak entry] document in
                guard let self, let entry else { return }
                entry.eventCallbacks += 1
                guard self.active === entry, !entry.closing else {
                    entry.callbacksAfterClose += 1
                    return
                }
                self.receive(document, entry: entry)
            }
            native.lifecycleHandler = { [weak self, weak entry] generation, foreground, backgrounded in
                guard let self, let entry else { return }
                entry.lifecycleCallbacks += 1
                guard self.active === entry, !entry.closing else {
                    entry.callbacksAfterClose += 1
                    return
                }
                self.lifecycle(entry, generation: generation, foreground: foreground, backgrounded: backgrounded)
            }
            native.failureHandler = { [weak self, weak entry] in
                guard let self, let entry else { return }
                guard self.active === entry, !entry.closing else {
                    entry.callbacksAfterClose += 1
                    return
                }
                self.fail("NATIVE_FAILURE", entry: entry)
            }
            owner.setApplicationActive(applicationActive, backgrounded: applicationBackgrounded)
            native.setForeground(true)
            // prepare records the initial native facts before callbacks can be
            // installed. An unchanged setForeground need not report them again.
            let initial = native.snapshot()
            lifecycle(entry, generation: native.lifecycleGeneration, foreground: flag("nativeForeground", initial),
                      backgrounded: flag("applicationBackgrounded", initial))
            showEngine = !entry.closing
            poll()
        } catch {
            errorMessage = "Native preparation failed: \(error.localizedDescription)"
            if let entry = active { finish(entry, reason: "PREPARATION_FAILED") }
            poll()
            persist("preparation-failed")
        }
    }

    func setApplicationActive(_ active: Bool, backgrounded: Bool) {
        if backgrounded && !applicationBackgrounded { applicationBackgroundCount += 1 }
        if active && !applicationActive { applicationForegroundCount += 1 }
        applicationActive = active && !backgrounded
        applicationBackgrounded = backgrounded
        owner.setApplicationActive(applicationActive, backgrounded: backgrounded)
        if let entry = self.active, !entry.closing { entry.native.setForeground(!pausedByUser) }
        poll()
    }

    func togglePause() {
        guard let entry = active, !entry.closing else { return }
        pausedByUser.toggle()
        entry.native.setForeground(!pausedByUser)
        poll()
    }

    func cycleFocus() {
        guard let entry = active, !entry.closing, !pausedByUser else { return }
        focusCycleCount += 1
        entry.native.setForeground(false)
        entry.native.setForeground(true)
        poll()
    }

    func close() {
        if let entry = active { finish(entry, reason: "HOST_CLOSE") }
    }

    func surfaceDetached(presentationID id: String) {
        // SwiftUI can dismantle the previous container after close completion
        // has already opened its replacement. Never close by global current.
        if let entry = active, entry.id == id, !entry.closing { finish(entry, reason: "SURFACE_DETACHED") }
    }

    func countHostInteraction() {
        hostCounter += 1
        poll()
    }

    func closeAndSwitch() {
        guard let entry = active, !entry.closing, entry.readyConfirmed, entry.inFlight == nil,
              entry.commands.isEmpty, let facade = entry.authority else { return }
        do {
            let update = try facade.refreshView()
            copyStatus(update.status, into: entry)
            guard let document = update.commands.first, update.commands.count == 1 else { throw HostFailure.commandBound }
            // Preserve native admission evidence before close can clear the
            // queue. A synchronous rejection must not pass as cancellation.
            entry.closeProbeLifecycleGeneration = entry.native.lifecycleGeneration
            entry.closeProbeDocumentBytes = document.utf8.count
            entry.closeProbeBeforeNative = entry.native.snapshot()
            entry.native.deliverDocument(document, lifecycleGeneration: entry.closeProbeLifecycleGeneration, confirmReady: false) {
                [weak self, weak entry] delivered in
                MainActor.assumeIsolated {
                    guard let self, let entry else { return }
                    entry.closeProbeDelivered = delivered
                    entry.closeProbeCallbackObserved = true
                    entry.closeProbeCallbackBeforeClose = !entry.closing
                    entry.closeProbeCallbackBeforeCompletion = !entry.closeCompletionObserved
                    self.poll()
                }
            }
            entry.closeProbeAfterNative = entry.native.snapshot()
            entry.closeProbeCallbackObservedBeforeClose = entry.closeProbeCallbackObserved
            pendingMode = entry.mode == "2d" ? "3d" : "2d"
            finish(entry, reason: "SWITCH_FROM_CLOSE_COMPLETION")
        } catch { fail("SWITCH_PREPARATION_FAILED", entry: entry) }
    }

    func probeOldHandle() {
        guard let current = active, !current.closing, let old = retired.last,
              let document = old.obsoleteForegroundDocument else { return }
        staleProbe = ["attempted": true, "oldPresentationID": old.id, "currentPresentationID": current.id,
                      "before": owner.snapshot(), "deliveryCompleted": false, "closeCompleted": false]
        old.native.eventHandler = { [weak old] _ in old?.callbacksAfterClose += 1 }
        old.native.lifecycleHandler = { [weak old] _, _, _ in old?.callbacksAfterClose += 1 }
        old.native.failureHandler = { [weak old] in old?.callbacksAfterClose += 1 }
        staleProbe["callbackRebindingRefused"] = old.native.eventHandler == nil &&
            old.native.lifecycleHandler == nil && old.native.failureHandler == nil
        old.native.setForeground(false)
        old.native.setForeground(true)
        staleProbe["readyConfirmationAccepted"] = old.native.confirmReady()
        staleProbe["diagnosticsAccepted"] = old.native.requestRendererDiagnostics()
        do {
            try old.native.sendDocument(document, lifecycleGeneration: current.native.lifecycleGeneration)
            staleProbe["sendAccepted"] = true
        } catch {
            staleProbe["sendAccepted"] = false
            staleProbe["sendError"] = error.localizedDescription
        }
        old.native.deliverDocument(document, lifecycleGeneration: current.native.lifecycleGeneration, confirmReady: true) {
            [weak self] delivered in
            MainActor.assumeIsolated {
                self?.staleProbe["deliveryCompleted"] = true
                self?.staleProbe["deliveryAccepted"] = delivered
                self?.poll()
            }
        }
        old.native.close { [weak self] dormant in
            MainActor.assumeIsolated {
                self?.staleProbe["closeCompleted"] = true
                self?.staleProbe["oldCloseDormant"] = dormant
                self?.poll()
            }
        }
        staleProbe["after"] = owner.snapshot()
        poll()
        persist("old-handle-probed")
    }

    func poll() {
        pollCount += 1
        let now = ProcessInfo.processInfo.systemUptime
        if let entry = active, !entry.closing, entry.readyAccepted, now - lastDiagnosticRequestAt >= 0.5,
           entry.native.requestRendererDiagnostics() { lastDiagnosticRequestAt = now }
        let native = owner.snapshot()
        state = native["state"] as? String ?? "unknown"
        if let entry = active, !entry.closing,
           state == "failed" || state == "closed" || flag("quarantined", native) {
            fail("NATIVE_OWNER_ENDED", entry: entry)
            return
        }
        var measured = active?.status ?? [:]
        measured["native"] = native
        measured["state"] = state
        measured["mode"] = mode
        measured["presentationID"] = presentationID
        measured["runID"] = runID
        measured["entryCount"] = entryCount
        measured["authorityReleased"] = active?.authority == nil
        measured["modelQueuedDocuments"] = active?.commands.count ?? 0
        measured["modelDeliveryPending"] = active?.inFlight != nil
        measured["readyConfirmed"] = active?.readyConfirmed ?? false
        measured["firstReadyProbe"] = active?.firstReadyProbe ?? [:]
        measured["entryPreparedNative"] = active?.preparedNative ?? [:]
        measured["hostCounter"] = hostCounter
        measured["pollCount"] = pollCount
        measured["observedUptime"] = now
        measured["applicationBackgroundCount"] = applicationBackgroundCount
        measured["applicationForegroundCount"] = applicationForegroundCount
        measured["focusCycleCount"] = focusCycleCount
        measured["lastClosure"] = lastClosure
        measured["staleProbe"] = staleProbe
        measured["retiredCallbacksAfterClose"] = retired.reduce(0) { $0 + $1.callbacksAfterClose }
        measured["failure"] = errorMessage
        measured["kmpFactoryQualified"] = false
        if let bytes = try? JSONSerialization.data(withJSONObject: measured, options: [.sortedKeys]),
           let document = String(data: bytes, encoding: .utf8) { observations = document }
    }

    private func receive(_ document: String, entry: Entry) {
        guard document.utf8.count <= 4_096, let facade = entry.authority else {
            fail("EVENT_BOUND_OR_MISSING_AUTHORITY", entry: entry)
            return
        }
        pumpHoldDepth += 1
        defer { pumpHoldDepth -= 1; pump(entry); poll() }
        do {
            let result = try facade.handleRendererEvent(document: document)
            copyStatus(result.status, into: entry)
            if [.returnToLobby, .exitRequested, .rendererFailed, .closed].contains(result.outcome) {
                finish(entry, reason: result.outcome.name, authorityAlreadyClosed: true)
                return
            }
            let newlyReady = !entry.readyAccepted && result.status.lifecycle == .ready && result.outcome == .accepted
            entry.readyAccepted = result.status.lifecycle == .ready
            try enqueue(result.commands, entry: entry)
            if newlyReady {
                try projectLifecycle(entry)
                if ProcessInfo.processInfo.arguments.contains("--supersede-first-ready"), entry.ordinal == 1 {
                    try supersedeFirstReady(entry)
                }
            } else if result.outcome == .rejected || result.outcome == .authorityRejected {
                let refresh = try facade.refreshView()
                copyStatus(refresh.status, into: entry)
                try enqueue(refresh.commands, entry: entry)
            }
            if result.outcome == .accepted && entry.nativeForeground {
                let opponents = try facade.advanceOtherPlayers()
                guard opponents.outcome == .accepted || opponents.outcome == .noChange else { throw HostFailure.opponentPolicy }
                copyStatus(opponents.status, into: entry)
                try enqueue(opponents.commands, entry: entry)
            }
        } catch { fail("AUTHORITY_OR_DELIVERY_FAILED", entry: entry) }
    }

    private func lifecycle(_ entry: Entry, generation: UInt64, foreground: Bool, backgrounded: Bool) {
        guard generation >= entry.lifecycleGeneration else { fail("LIFECYCLE_REGRESSION", entry: entry); return }
        entry.lifecycleGeneration = generation
        entry.nativeForeground = foreground && !backgrounded
        entry.commands.removeAll { $0.generation != generation }
        do { try projectLifecycle(entry) } catch { fail("LIFECYCLE_PROJECTION_FAILED", entry: entry) }
        pump(entry)
    }

    private func projectLifecycle(_ entry: Entry) throws {
        guard let facade = entry.authority, !entry.closing else { return }
        let foreground = try facade.setForeground(isForeground: entry.nativeForeground)
        guard foreground.outcome == .foregroundChanged else { throw HostFailure.foreground }
        entry.obsoleteForegroundDocument = foreground.commands.first
        copyStatus(foreground.status, into: entry)
        // Native bootstraps behind its cover. No command confirms Ready before
        // the actual renderer event has passed through the existing facade.
        guard entry.readyAccepted else { return }
        let refreshed = try facade.refreshView()
        copyStatus(refreshed.status, into: entry)
        try enqueue(refreshed.commands + foreground.commands, entry: entry)
    }

    private func supersedeFirstReady(_ entry: Entry) throws {
        guard !entry.readyConfirmed, let first = entry.commands.first else { throw HostFailure.commandBound }
        let document = first.document
        let captured = first.generation
        entry.commands.removeAll()
        entry.native.setForeground(false)
        entry.native.setForeground(true)
        entry.firstReadyProbe = ["attempted": true, "capturedGeneration": String(captured),
                                 "currentGeneration": String(entry.native.lifecycleGeneration), "completed": false]
        entry.native.deliverDocument(document, lifecycleGeneration: captured, confirmReady: true) { [weak self, weak entry] delivered in
            MainActor.assumeIsolated {
                guard let self, let entry else { return }
                entry.firstReadyProbe["completed"] = true
                entry.firstReadyProbe["accepted"] = delivered
                entry.firstReadyProbe["nativeReadyConfirmedAtRejection"] = self.flag("authorityReadyConfirmed", entry.native.snapshot())
                entry.firstReadyProbe["reportedGenerationBeforeCompletion"] = String(entry.lifecycleGeneration)
                if delivered { self.fail("STALE_FIRST_READY_ACCEPTED", entry: entry) }
            }
        }
    }

    private func enqueue(_ documents: [String], entry: Entry) throws {
        guard !entry.closing else { return }
        let bytes = entry.commands.reduce(0) { $0 + $1.document.utf8.count } + documents.reduce(0) { $0 + $1.utf8.count }
        guard entry.commands.count + documents.count <= 16, bytes <= 262_144,
              documents.allSatisfy({ $0.utf8.count <= 65_536 }) else { throw HostFailure.commandBound }
        let generation = entry.native.lifecycleGeneration
        entry.commands += documents.map { Command(document: $0, generation: generation) }
        pump(entry)
    }

    private func pump(_ entry: Entry) {
        guard pumpHoldDepth == 0, active === entry, !entry.closing, entry.readyAccepted, entry.inFlight == nil else { return }
        while entry.commands.first.map({ $0.generation != entry.native.lifecycleGeneration }) == true { entry.commands.removeFirst() }
        guard !entry.commands.isEmpty else { return }
        let next = entry.commands.removeFirst()
        let captured = next.generation
        let confirmReady = !entry.readyConfirmed
        entry.deliverySerial += 1
        let serial = entry.deliverySerial
        entry.inFlight = serial
        // The completion captures no private command document.
        entry.native.deliverDocument(next.document, lifecycleGeneration: captured, confirmReady: confirmReady) {
            [weak self, weak entry] delivered in
            MainActor.assumeIsolated {
                guard let self, let entry else { return }
                guard self.active === entry, !entry.closing, entry.inFlight == serial else { return }
                entry.inFlight = nil
                if delivered {
                    if confirmReady { entry.readyConfirmed = true }
                } else if captured == entry.native.lifecycleGeneration {
                    self.fail("CURRENT_NATIVE_DELIVERY_REJECTED", entry: entry)
                    return
                }
                self.pump(entry)
                self.poll()
            }
        }
    }

    private func finish(_ entry: Entry, reason: String, authorityAlreadyClosed: Bool = false) {
        guard active === entry, !entry.closing else { return }
        entry.closing = true
        entry.commands.removeAll()
        entry.inFlight = nil
        if let facade = entry.authority {
            do {
                if !authorityAlreadyClosed {
                    // Retain only a public foreground envelope for stale-handle
                    // probes. Recipient views and the launch are never retained.
                    entry.obsoleteForegroundDocument = try facade.setForeground(isForeground: false).commands.first
                    copyStatus(try facade.close().status, into: entry)
                } else {
                    copyStatus(facade.status(), into: entry)
                }
                entry.authorityLaunchCleared = facade.launchDocument.isEmpty
            } catch { errorMessage = "Authority close failed: \(error.localizedDescription)" }
        }
        entry.authority = nil
        entry.closeReason = reason
        entry.closeRequestedAt = ProcessInfo.processInfo.systemUptime
        entry.native.close { [weak self, weak entry] dormant in
            MainActor.assumeIsolated {
                guard let self, let entry else { return }
                entry.closeCompletionObserved = true
                entry.closeCompletedAt = ProcessInfo.processInfo.systemUptime
                entry.closeCompletionNative = self.owner.snapshot()
                entry.closeSucceeded = dormant
                self.lastClosure = self.closureObservation(entry)
                guard self.active === entry else { return }
                self.active = nil
                self.showEngine = false
                self.retired.append(entry)
                if self.retired.count > 4 { self.retired.removeFirst() }
                if !dormant { self.errorMessage = "The native owner did not observe dormant cleanup." }
                self.poll()
                self.persist("close-completed")
                if dormant, let next = self.pendingMode {
                    self.pendingMode = nil
                    // Tests require this immediate open to succeed. The native
                    // completion must have released its old ownership first.
                    self.start(mode: next)
                }
            }
        }
        entry.closeReturnedBeforeCompletion = !entry.closeCompletionObserved
        entry.closeReturnedNative = owner.snapshot()
        if !entry.closeCompletionObserved { probeOpeningWhileClosing(entry) }
        lastClosure = closureObservation(entry)
        poll()
        persist("close-requested")
    }

    private func probeOpeningWhileClosing(_ entry: Entry) {
        do {
            let resources = try inputs()
            let probe = try newFacade(id: UUID().uuidString, mode: entry.mode)
            defer { _ = try? probe.close() }
            do {
                let unexpected: PDGodotPresentation? = try owner.createPresentation(
                    withProjectPath: resources.project, packPath: resources.pack, launchDocument: probe.launchDocument
                )
                entry.openWhileClosingRefused = unexpected == nil
                if unexpected != nil {
                    errorMessage = "The native owner allowed overlapping presentations."
                    owner.shutdown()
                }
            } catch {
                entry.openWhileClosingRefused = true
                entry.openWhileClosingError = error.localizedDescription
            }
        } catch { errorMessage = "The close-order probe could not construct valid inputs: \(error.localizedDescription)" }
    }

    private func closureObservation(_ entry: Entry) -> [String: Any] {
        ["presentationID": entry.id, "entryOrdinal": entry.ordinal, "mode": entry.mode,
         "authorityStatus": entry.status, "authorityReleased": entry.authority == nil,
         "authorityLaunchCleared": entry.authorityLaunchCleared, "reason": entry.closeReason,
         "returnedBeforeCompletion": entry.closeReturnedBeforeCompletion,
         "returnedNative": entry.closeReturnedNative, "completionObserved": entry.closeCompletionObserved,
         "completionNative": entry.closeCompletionNative, "dormant": entry.closeSucceeded,
         "requestedAtUptime": entry.closeRequestedAt, "completedAtUptime": entry.closeCompletedAt,
         "openWhileClosingRefused": entry.openWhileClosingRefused, "openWhileClosingError": entry.openWhileClosingError,
         "handleViewControllerReleased": entry.native.viewController == nil,
         "handleCallbacksCleared": entry.native.eventHandler == nil && entry.native.lifecycleHandler == nil && entry.native.failureHandler == nil,
         "eventCallbacks": entry.eventCallbacks, "lifecycleCallbacks": entry.lifecycleCallbacks,
         "callbacksAfterClose": entry.callbacksAfterClose,
         "closeProbeLifecycleGeneration": String(entry.closeProbeLifecycleGeneration),
         "closeProbeDocumentBytes": entry.closeProbeDocumentBytes,
         "closeProbeBeforeNative": entry.closeProbeBeforeNative, "closeProbeAfterNative": entry.closeProbeAfterNative,
         "closeProbeCallbackObservedBeforeClose": entry.closeProbeCallbackObservedBeforeClose,
         "closeProbeCallbackObserved": entry.closeProbeCallbackObserved, "closeProbeDelivered": entry.closeProbeDelivered,
         "closeProbeCallbackBeforeClose": entry.closeProbeCallbackBeforeClose,
         "closeProbeCallbackBeforeCompletion": entry.closeProbeCallbackBeforeCompletion]
    }

    private func fail(_ code: String, entry: Entry) {
        errorMessage = code
        pendingMode = nil
        finish(entry, reason: "FAILURE")
    }

    private func copyStatus(_ status: IosQualificationStatus, into entry: Entry) {
        entry.status = ["lifecycle": status.lifecycle.name, "phase": status.phase.name, "revision": status.revision,
                        "roundNumber": status.roundNumber, "winnerId": status.winnerId, "foreground": status.foreground,
                        "acceptedRendererEvents": status.acceptedRendererEvents, "acceptedViewerPlays": status.acceptedViewerPlays,
                        "acceptedViewerChallenges": status.acceptedViewerChallenges, "roundsAdvanced": status.roundsAdvanced,
                        "acceptedOpponentActions": status.acceptedOpponentActions]
    }

    private func newFacade(id: String, mode: String) throws -> IosQualificationAuthority {
        try IosQualificationFactory.shared.create(presentationId: id, mode: mode == "3d" ? .threeD : .twoD,
                                                  randomness: .referenceSeed2, reduceMotion: false,
                                                  soundEnabled: true, textScale: 1.0)
    }

    private func inputs() throws -> (project: String, pack: String) {
        guard let resources = Bundle.main.resourceURL else { throw HostFailure.resources }
        let pack = resources.appendingPathComponent("ProbeResources/partydeck-last-light.pck")
        guard FileManager.default.isReadableFile(atPath: pack.path) else { throw HostFailure.resources }
        return (resources.path, pack.path)
    }

    private func persist(_ event: String) {
        guard let bytes = observations.data(using: .utf8),
              let measured = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any] else { return }
        journal.append(["event": event, "observedAtUnixSeconds": Date().timeIntervalSince1970, "measurements": measured])
        if journal.count > 24 { journal.removeFirst() }
        let value: [String: Any] = ["runID": runID, "startedAtUnixSeconds": startedAt,
                                   "arguments": ProcessInfo.processInfo.arguments, "journal": journal]
        if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
           let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            try? data.write(to: directory.appendingPathComponent("retained-runtime-\(runID).json"), options: .atomic)
        }
    }

    private func flag(_ name: String, _ value: [String: Any]) -> Bool { (value[name] as? NSNumber)?.boolValue ?? false }
    private enum HostFailure: Error { case resources, preparation, commandBound, opponentPolicy, foreground }
    private struct Command { let document: String; let generation: UInt64 }

    @MainActor
    private final class Entry {
        let id: String
        let ordinal: Int
        let mode: String
        let native: PDGodotPresentation
        var authority: IosQualificationAuthority?
        var status: [String: Any] = [:]
        var preparedNative: [String: Any] = [:]
        var commands: [Command] = []
        var lifecycleGeneration: UInt64 = 0
        var nativeForeground = false
        var readyAccepted = false
        var readyConfirmed = false
        var closing = false
        var deliverySerial = 0
        var inFlight: Int?
        var eventCallbacks = 0
        var lifecycleCallbacks = 0
        var callbacksAfterClose = 0
        var firstReadyProbe: [String: Any] = [:]
        var obsoleteForegroundDocument: String?
        var authorityLaunchCleared = false
        var closeReason = ""
        var closeRequestedAt: TimeInterval = 0
        var closeCompletedAt: TimeInterval = 0
        var closeReturnedBeforeCompletion = false
        var closeReturnedNative: [String: Any] = [:]
        var closeCompletionObserved = false
        var closeCompletionNative: [String: Any] = [:]
        var closeSucceeded = false
        var openWhileClosingRefused = false
        var openWhileClosingError = ""
        var closeProbeLifecycleGeneration: UInt64 = 0
        var closeProbeDocumentBytes = 0
        var closeProbeBeforeNative: [String: Any] = [:]
        var closeProbeAfterNative: [String: Any] = [:]
        var closeProbeCallbackObservedBeforeClose = false
        var closeProbeCallbackObserved = false
        var closeProbeDelivered = false
        var closeProbeCallbackBeforeClose = false
        var closeProbeCallbackBeforeCompletion = false

        init(id: String, ordinal: Int, mode: String, native: PDGodotPresentation, authority: IosQualificationAuthority) {
            self.id = id; self.ordinal = ordinal; self.mode = mode; self.native = native; self.authority = authority
        }
    }
}
