import Combine
import Foundation
import PartyDeckGodotBridge

// The native runtime delivers synchronously on the main thread after its draw
// and engine scopes return. Keep the Kotlin facade on that same owner, with no
// per-event Task/dispatch queue and no game rules or copied authority state.
final class AuthorityModel: ObservableObject {
    let runtime = PDGodotRuntime()
    @Published private(set) var showEngine = false
    @Published private(set) var state = "idle"
    @Published private(set) var observations = "{}"
    @Published private(set) var errorMessage = ""
    @Published private(set) var pausedByUser = false
    @Published private(set) var mode = ""
    @Published var hostCounter = 0

    private var authority: IosQualificationAuthority?
    private var applicationActive = true
    private var closing = false
    private var generation: UInt64 = 0
    private var receipt: [String: Any] = [:]
    private var lastDiagnosticRequestAt: TimeInterval = 0

    var referenceScenario: Bool {
        ProcessInfo.processInfo.arguments.contains("--reference-seed=2")
    }

    func start(mode selectedMode: String, reduceMotion: Bool, soundEnabled: Bool, textScale: Double) {
        precondition(Thread.isMainThread)
        guard state == "idle", !closing, authority == nil, selectedMode == "2d" || selectedMode == "3d" else { return }
        mode = selectedMode
        receipt["textScale"] = textScale
        receipt["reduceMotion"] = reduceMotion
        receipt["soundEnabled"] = soundEnabled
        generation += 1
        let ownedGeneration = generation
        do {
            guard let resources = Bundle.main.resourceURL else { throw HostFailure.resourcesMissing }
            let pack = resources.appendingPathComponent("ProbeResources/partydeck-last-light.pck")
            guard FileManager.default.isReadableFile(atPath: pack.path) else { throw HostFailure.resourcesMissing }
            let facade = try IosQualificationFactory.shared.create(
                presentationId: UUID().uuidString,
                mode: selectedMode == "3d" ? .threeD : .twoD,
                randomness: referenceScenario ? .referenceSeed2 : .secure,
                reduceMotion: reduceMotion,
                soundEnabled: soundEnabled,
                textScale: textScale
            )
            authority = facade
            copyStatus(facade.status())
            runtime.eventHandler = { [weak self] document in
                self?.receive(document, generation: ownedGeneration)
            }
            try runtime.prepare(withProjectPath: resources.path, packPath: pack.path, launchDocument: facade.launchDocument)
            try applyForeground()
            showEngine = !closing
            poll()
        } catch {
            fail("PREPARATION_FAILED")
        }
    }

    func setApplicationActive(_ active: Bool) {
        precondition(Thread.isMainThread)
        applicationActive = active
        updateForeground()
    }

    func togglePause() {
        precondition(Thread.isMainThread)
        guard authority != nil, !closing else { return }
        pausedByUser.toggle()
        updateForeground()
    }

    func close() {
        precondition(Thread.isMainThread)
        finish(reason: "HOST_CLOSE")
    }

    func poll() {
        precondition(Thread.isMainThread)
        let now = ProcessInfo.processInfo.systemUptime
        if !closing, authority != nil, receipt["lifecycle"] as? String == "READY",
           now - lastDiagnosticRequestAt >= 0.5, runtime.requestRendererDiagnostics() {
            lastDiagnosticRequestAt = now
        }
        let native = runtime.snapshot()
        let nativeState = native["state"] as? String ?? "unknown"
        if (nativeState == "failed" || nativeState == "closed"), !closing, authority != nil {
            // Native bootstrap/renderer failures may terminate without a bridge
            // event. Dispose of the real gate in this path too.
            fail("NATIVE_RUNTIME_ENDED")
        }
        state = nativeState
        if nativeState == "closed" || nativeState == "failed" { showEngine = false }
        var measured = receipt
        measured["native"] = native
        measured["state"] = state
        measured["mode"] = mode
        measured["referenceSeed2"] = referenceScenario
        measured["authorityReleased"] = authority == nil
        measured["hostCounter"] = hostCounter
        measured["kmpFactoryQualified"] = false
        if let bytes = try? JSONSerialization.data(withJSONObject: measured, options: [.sortedKeys]),
           let document = String(data: bytes, encoding: .utf8) {
            observations = document
            if closing, let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
                try? bytes.write(to: directory.appendingPathComponent("authority-runtime.json"), options: .atomic)
            }
        }
    }

    private func receive(_ document: String, generation receivedGeneration: UInt64) {
        precondition(Thread.isMainThread)
        guard !closing, receivedGeneration == generation, let facade = authority else { return }
        do {
            let result = try facade.handleRendererEvent(document: document)
            copyStatus(result.status)
            receipt["lastOutcome"] = result.outcome.name
            receipt["lastReasonCode"] = result.reasonCode
            if isTerminal(result.outcome) {
                if result.outcome == .rendererFailed {
                    receipt["failureCode"] = "RENDERER_FAILED"
                    errorMessage = "The table could not continue. Relaunch the comparison to try again."
                }
                try deliver(result.commands)
                finish(reason: result.outcome.name, alreadyClosed: true)
            } else {
                var commands = try boundedCommands(result.commands)
                if result.outcome == .accepted {
                    // This calls the existing safe-view opponent policy. Round
                    // continuation remains a real renderer intent.
                    let opponents = try facade.advanceOtherPlayers()
                    copyStatus(opponents.status)
                    commands = try joined(commands, opponents.commands)
                    if opponents.outcome == .rejected || opponents.outcome == .authorityRejected {
                        throw HostFailure.opponentPolicyFailed
                    }
                } else if result.outcome == .rejected || result.outcome == .authorityRejected {
                    let refresh = try facade.refreshView()
                    copyStatus(refresh.status)
                    commands = try joined(commands, refresh.commands)
                }
                try deliver(commands)
            }
        } catch {
            fail("AUTHORITY_OR_BRIDGE_FAILED")
        }
        poll()
    }

    private func updateForeground() {
        guard authority != nil, !closing else { return }
        do {
            try applyForeground()
        } catch {
            fail("FOREGROUND_DELIVERY_FAILED")
        }
        poll()
    }

    private func applyForeground() throws {
        guard let facade = authority, !closing else { return }
        let foreground = applicationActive && !pausedByUser
        // Cover UIKit immediately, before entering Kotlin or waiting for any
        // renderer command. Resume is delivered only after the gate changes.
        if !foreground { runtime.setForeground(false) }
        let result = try facade.setForeground(isForeground: foreground)
        guard result.outcome == .foregroundChanged else { throw HostFailure.foregroundFailed }
        copyStatus(result.status)
        try deliver(result.commands)
        if foreground, result.status.lifecycle == .ready {
            // Ready may have arrived while the app was losing foreground.
            // Resume the existing policy too, so an opponent turn cannot stall.
            let opponents = try facade.advanceOtherPlayers()
            guard opponents.outcome == .accepted || opponents.outcome == .noChange else {
                throw HostFailure.opponentPolicyFailed
            }
            copyStatus(opponents.status)
            try deliver(opponents.commands)
        }
    }

    private func boundedCommands(_ commands: [String]) throws -> [String] {
        guard commands.count <= 16 else { throw HostFailure.commandBound }
        var bytes = 0
        for document in commands {
            let count = document.utf8.count
            guard count <= 65_536 else { throw HostFailure.commandBound }
            bytes += count
            guard bytes <= 262_144 else { throw HostFailure.commandBound }
        }
        return commands
    }

    private func joined(_ prefix: [String], _ suffix: [String]) throws -> [String] {
        guard prefix.count + suffix.count <= 16 else { throw HostFailure.commandBound }
        return try boundedCommands(prefix + suffix)
    }

    private func deliver(_ commands: [String]) throws {
        for document in try boundedCommands(commands) {
            try runtime.sendDocument(document)
        }
    }

    private func isTerminal(_ outcome: IosQualificationOutcome) -> Bool {
        outcome == .returnToLobby || outcome == .exitRequested || outcome == .rendererFailed || outcome == .closed
    }

    private func copyStatus(_ status: IosQualificationStatus) {
        receipt["lifecycle"] = status.lifecycle.name
        receipt["phase"] = status.phase.name
        receipt["revision"] = status.revision
        receipt["roundNumber"] = status.roundNumber
        receipt["winnerId"] = status.winnerId
        receipt["foreground"] = status.foreground
        receipt["acceptedRendererEvents"] = status.acceptedRendererEvents
        receipt["acceptedViewerPlays"] = status.acceptedViewerPlays
        receipt["acceptedViewerChallenges"] = status.acceptedViewerChallenges
        receipt["roundsAdvanced"] = status.roundsAdvanced
        receipt["acceptedOpponentActions"] = status.acceptedOpponentActions
    }

    private func fail(_ code: String) {
        receipt["failureCode"] = code
        errorMessage = "The table could not continue. Relaunch the comparison to try again."
        finish(reason: "FAILURE")
    }

    private func finish(reason: String, alreadyClosed: Bool = false) {
        guard !closing else { return }
        closing = true
        generation += 1
        receipt["closeReason"] = reason
        runtime.setForeground(false)
        runtime.eventHandler = nil
        if let facade = authority, !alreadyClosed {
            do {
                let result = try facade.close()
                copyStatus(result.status)
                // The native runtime may already have closed after an engine
                // failure. Native close below always runs even if delivery fails.
                try deliver(result.commands)
            } catch {
                receipt["terminalDeliveryFailed"] = true
            }
        }
        authority = nil
        runtime.close()
        poll()
    }

    private enum HostFailure: Error {
        case resourcesMissing, commandBound, foregroundFailed, opponentPolicyFailed
    }
}
