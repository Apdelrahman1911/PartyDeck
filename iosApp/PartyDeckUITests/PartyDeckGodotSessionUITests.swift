#if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
import Foundation
import XCTest

/// Explicit qualification cases for the production owner, controller, runtime, authority and renderer.
/// The build must select these two names and independently verify that both actually ran and passed.
final class PartyDeckGodotSessionUITests: XCTestCase {
    private var lastObservation: Observation?
    private var lastDocument: Data?

    override func setUpWithError() throws { continueAfterFailure = false }

    @MainActor
    func testProduction2DPracticeSession() async throws { try await exercise(.twoD) }

    @MainActor
    func testProduction3DPracticeSession() async throws { try await exercise(.threeD) }

    @MainActor
    private func exercise(_ mode: Mode) async throws {
        lastObservation = nil
        lastDocument = nil
        let app = XCUIApplication()
        app.launchArguments = ["--partydeck-observe-godot-session"] // Observation only; never enables a mode.
        app.launch()
        do {
            let home = try await wait(app, "The opted-in observation must exist on the actual Home screen.", timeout: 30) {
                $0.controller?.screen == "HOME" && $0.controller?.sessionPresent == false &&
                    self.element("home-practice", app).isHittable
            }
            try require(!home.port.ownerCreated, "Observation must not acquire a native engine before the user selects a renderer.")
            try await tapElement("home-practice", app)
            let practice = try await playablePractice(app)
            let practiceState = try controller(practice)
            let generation = practiceState.sessionGeneration
            try require(!practice.port.ownerCreated, "The real Standard practice session must not eagerly acquire Godot.")
            try require(practiceState.handCount == 5, "Full native hand acceptance requires the fresh five-card hand before any Play.")
            try StandardTableAcceptance(app).exerciseFiveCardHand { checkpoint in
                guard let observed = try read(app) else { throw Failure("Native hand acceptance requires the real session observation.") }
                let state = try controller(observed)
                try require(state.sessionGeneration == generation && state.sessionRevision == practiceState.sessionRevision &&
                    state.lastViewerReceipt?.serial == practiceState.lastViewerReceipt?.serial && state.handCount == 5 &&
                    state.mode == "COMPOSE" && state.ownTurn && state.canPlay && !observed.port.ownerCreated,
                    "Reveal, native card toggles and Hide must preserve the real session without an authority action or engine acquisition.")
                capture("\(mode.rawValue) Standard \(checkpoint)", app)
            }

            let first = try await enter(mode, app, session: generation)
            capture("\(mode.rawValue) production concealed entry", app)
            try await revealSelectHide(mode, app, session: generation)
            let reveal = try await tapRenderer("reveal", mode, app, session: generation)
            _ = try await live(mode, app, session: generation, after: reveal) { !$0.renderer.handConcealed }
            let card = try await tapRenderer("card", mode, app, session: generation, cardIndex: 0)
            _ = try await live(mode, app, session: generation, after: card) {
                $0.renderer.selectedCount == 1 && $0.renderer.control("card", index: 0)?.selected == true
            }
            let beforePlay = try await tapRenderer("play", mode, app, session: generation)
            let previousSerial = beforePlay.state.lastViewerReceipt?.serial.value ?? 0
            let accepted = try await live(mode, app, session: generation, after: beforePlay) { value in
                guard let receipt = value.state.lastViewerReceipt, receipt.serial.value > previousSerial else { return false }
                try self.require(receipt.serial.value == previousSerial + 1 && receipt.accepted && receipt.error == nil &&
                    receipt.action == "PLAY_CARDS" && receipt.mode == mode.selection &&
                    receipt.sessionGeneration == generation && receipt.presentationOrdinal == beforePlay.state.presentationOrdinal &&
                    receipt.expectedRevision == beforePlay.state.sessionRevision && receipt.revision > receipt.expectedRevision,
                    "A real viewer Play receipt must match this native presentation and the tapped authority revision.")
                return value.state.sessionRevision.map { $0 >= receipt.revision } == true &&
                    value.native.intentEvents > beforePlay.native.intentEvents
            }
            capture("\(mode.rawValue) real authority accepted native Play", app)

            try await tapElement("godot-standard-table", app)
            let standard = try await standardTable(app, session: generation, privacyAfter: accepted.state.privacyEpoch)
            try retained(standard, first: first)
            capture("\(mode.rawValue) same session Standard return", app)
            let standardAction = try await exerciseStandardAuthorityAction(mode, app, session: generation)
            try retained(standardAction, first: first)

            let second = try await enter(mode, app, session: generation, after: first)
            try retained(second.observation, first: first)
            try await tapElement("godot-leave-table", app)
            try await leaveDialog(app)
            try await tapElement("leave-cancel", app)
            let cancelled = try await standardTable(app, session: generation, privacyAfter: second.state.privacyEpoch)
            try retained(cancelled, first: first)
            capture("\(mode.rawValue) Leave cancelled on same concealed session", app)

            let third = try await enter(mode, app, session: generation, after: second)
            try retained(third.observation, first: first)
            try await tapElement("godot-leave-table", app)
            try await leaveDialog(app)
            try await tapElement("leave-confirm", app)
            let left = try await homeAfterLeave(app, after: generation)
            try retained(left, first: first)
            capture("\(mode.rawValue) confirmed Leave ended the session", app)

            try await tapElement("home-practice", app)
            let nextPractice = try await playablePractice(app)
            let nextGeneration = try controller(nextPractice).sessionGeneration
            try require(nextGeneration > generation, "Starting another actual practice table must create a new runtime generation.")
            let fourth = try await enter(mode, app, session: nextGeneration, after: third)
            try retained(fourth.observation, first: first)
            try await revealSelectHide(mode, app, session: nextGeneration, inspectBodyScroll: mode == .threeD)
            capture("\(mode.rawValue) new practice reuses engine and receives fresh input", app)
            try await tapElement("godot-leave-table", app)
            try await leaveDialog(app)
            try await tapElement("leave-confirm", app)
            let finished = try await homeAfterLeave(app, after: nextGeneration)
            try retained(finished, first: first)
            capture("\(mode.rawValue) production smoke cleanup complete", app)
        } catch {
            capture("\(mode.rawValue) production smoke failure", app)
            XCTFail((error as? Failure)?.message ?? "Production smoke could not complete; retained observations and screenshots are authoritative.")
            throw error
        }
    }

    @MainActor
    private func playablePractice(_ app: XCUIApplication) async throws -> Observation {
        // Real bots and the opening seat are random. Only real UI round advances are permitted.
        for _ in 0..<4 {
            let value = try await wait(app, "Practice must offer a human turn or an actionable round result.", timeout: 30) {
                guard let state = $0.controller else { return false }
                return state.sessionPresent && state.practice && state.screen == "SESSION" && state.mode == "COMPOSE" &&
                    state.canSendAction && ((state.ownTurn && state.canPlay && state.handCount > 0) ||
                    state.canAdvanceRound || state.phase == "FINISHED")
            }
            let state = try controller(value)
            try require(element("game-table", app).exists, "Practice must render the actual shared game screen.")
            if state.ownTurn && state.canPlay && state.handCount > 0 { return value }
            try require(state.phase == "ROUND_ENDED" && state.canAdvanceRound,
                        "A practice match must not finish before the human has an opportunity to act.")
            let result = element("game-round-result", app)
            try require(result.waitForExistence(timeout: 10), "The real round result must render before scrolling its controls.")
            for _ in 0..<3 where !element("game-next-round", app).isHittable { result.swipeUp() }
            try await tapElement("game-next-round", app)
            _ = try await wait(app, "A real round advance must leave the previous result.") {
                guard let next = $0.controller else { return false }
                return next.round != state.round || next.phase != state.phase
            }
        }
        throw Failure("Practice did not reach a playable human turn within four real rounds.")
    }

    @MainActor
    private func enter(_ mode: Mode, _ app: XCUIApplication, session: Counter, after previous: Live? = nil) async throws -> Live {
        try await tapElement("presentation-picker", app)
        let options = element("presentation-options", app)
        try require(options.waitForExistence(timeout: 10), "The actual presentation dialog must render before scrolling its choices.")
        let choice = "presentation-choice-\(mode.selection.lowercased())"
        for _ in 0..<3 where !element(choice, app).isHittable { options.swipeUp() }
        try await tapElement(choice, app)
        let opened = try await live(mode, app, session: session, timeout: 60) { value in
            guard let previous else { return value.native.nativePresentedFrames > 0 && value.native.drawCalls > 0 }
            return value.native.presentationGeneration > previous.native.presentationGeneration &&
                value.state.presentationOrdinal > previous.state.presentationOrdinal &&
                value.native.nativePresentedFrames > previous.native.nativePresentedFrames
        }
        try require(opened.renderer.concealed, "The first observed usable renderer frame must be concealed.")
        let fresh = try await live(mode, app, session: session, after: opened) {
            $0.native.nativePresentedFrames > opened.native.nativePresentedFrames && $0.native.drawCalls > opened.native.drawCalls
        }
        try require(fresh.renderer.concealed, "Every real renderer entry must have no private faces, labels or selection.")
        return fresh
    }

    @MainActor
    private func revealSelectHide(_ mode: Mode, _ app: XCUIApplication, session: Counter,
                                  inspectBodyScroll: Bool = false) async throws {
        let beforeReveal = try await tapRenderer("reveal", mode, app, session: session)
        _ = try await live(mode, app, session: session, after: beforeReveal) {
            !$0.renderer.handConcealed && $0.renderer.privateFaceCount > 0 && $0.renderer.selectedCount == 0
        }
        let beforeCard = try await tapRenderer("card", mode, app, session: session, cardIndex: 0)
        _ = try await live(mode, app, session: session, after: beforeCard) {
            $0.renderer.selectedCount == 1 && $0.renderer.control("card", index: 0)?.selected == true
        }
        capture("\(mode.rawValue) real native card selection", app)
        if inspectBodyScroll { try await inspectRendererBodyScroll(mode, app, session: session) }
        let beforeHide = try await tapRenderer("hide", mode, app, session: session)
        let hidden = try await live(mode, app, session: session, after: beforeHide) { $0.renderer.concealed }
        try require(hidden.state.lastViewerReceipt?.serial == beforeReveal.state.lastViewerReceipt?.serial,
                    "Reveal, selection and Hide must remain local to the renderer.")
        capture("\(mode.rawValue) Hide removes private faces labels and selection", app)
    }

    @MainActor
    private func standardTable(_ app: XCUIApplication, session: Counter, privacyAfter: Counter) async throws -> Observation {
        let value = try await dormant(app, "Return must complete native close and reveal the same concealed Standard game.") {
            guard let state = $0.controller else { return false }
            return state.sessionPresent && state.practice && state.sessionGeneration == session &&
                state.screen == "SESSION" && state.privacyEpoch > privacyAfter &&
                state.foreground && !state.backgrounded && state.canSendAction && !state.leaveConfirmation && self.element("game-table", app).exists
        }
        try require(privateCards(app).count == 0, "Standard return must expose no private card nodes to accessibility.")
        if element("game-play", app).exists {
            try require(!element("game-play", app).isEnabled, "The concealed Standard hand must have no retained selection.")
        }
        return value
    }

    @MainActor
    private func exerciseStandardAuthorityAction(_ mode: Mode, _ app: XCUIApplication, session: Counter) async throws -> Observation {
        // Real bots can challenge the native Play and eliminate the viewer. An outcome never
        // replaces the five-card checks above; it determines the legal authority action here.
        let choices: [StandardAction] = [.play, .challenge, .nextRound, .returnToLobby]
        let origin = try await dormant(app, "The same Standard session must expose a currently legal authority action.") { value in
            guard self.standardContext(value, session: session), let state = value.controller else { return false }
            return choices.contains { self.available($0, state: state, app: app) }
        }
        let state = try controller(origin)
        guard let action = choices.first(where: { available($0, state: state, app: app) }) else {
            throw Failure("No supported Standard authority action was observed.")
        }
        let result = try await submitStandard(action, mode, app, session: session, origin: origin)
        guard action == .returnToLobby else { return result }

        // Return to lobby is an accepted action, not a Play pass. Start the next real match
        // inside this same authority/session before the existing retained-entry checks continue.
        let lobby = try await dormant(app, "The retained practice authority must expose its real lobby Start control.") { value in
            guard self.standardContext(value, session: session), let state = value.controller else { return false }
            return self.available(.startGame, state: state, app: app)
        }
        return try await submitStandard(.startGame, mode, app, session: session, origin: lobby)
    }

    private func standardContext(_ value: Observation, session: Counter) -> Bool {
        guard let state = value.controller else { return false }
        return state.sessionPresent && state.practice && state.sessionGeneration == session && state.screen == "SESSION" &&
            state.mode == "COMPOSE" && state.lifecycle == "COMPOSE" && state.foreground && !state.backgrounded &&
            !state.leaveConfirmation && state.canSendAction && state.pending == nil && state.sessionRevision != nil
    }

    @MainActor
    private func available(_ action: StandardAction, state: Controller, app: XCUIApplication) -> Bool {
        switch action {
        case .play:
            return state.phase == "PLAYING" && state.ownTurn && state.canPlay && state.handCount > 0 && element("game-play", app).exists
        case .challenge:
            return state.phase == "PLAYING" && state.ownTurn && !state.canPlay &&
                element("game-challenge", app).exists && element("game-challenge", app).isEnabled
        case .nextRound:
            return state.phase == "ROUND_ENDED" && state.canAdvanceRound &&
                element("game-next-round", app).exists && element("game-next-round", app).isEnabled
        case .returnToLobby:
            return state.phase == "FINISHED" && element("game-rematch", app).exists && element("game-rematch", app).isEnabled
        case .startGame:
            return state.phase == nil && state.round == 0 && state.handCount == 0 && !element("game-table", app).exists &&
                element("lobby-start", app).exists && element("lobby-start", app).isEnabled
        }
    }

    @MainActor
    private func submitStandard(_ action: StandardAction, _ mode: Mode, _ app: XCUIApplication,
                                session: Counter, origin: Observation) async throws -> Observation {
        let originState = try controller(origin)
        let standard = StandardTableAcceptance(app)
        if action == .play {
            _ = try standard.reveal(count: originState.handCount)
            try standard.toggle(index: 0, count: originState.handCount, selected: true)
        }
        let button = try standard.control(action.identifier)
        let before = try await dormant(app, "The Standard action must still match its exact pre-tap session and revision.") { value in
            guard self.standardContext(value, session: session), let state = value.controller else { return false }
            return state.sessionRevision == originState.sessionRevision && state.phase == originState.phase &&
                state.round == originState.round && state.handCount == originState.handCount &&
                state.lastViewerReceipt?.serial == originState.lastViewerReceipt?.serial &&
                self.available(action, state: state, app: app) && button.isEnabled && button.isHittable
        }
        let beforeState = try controller(before)
        let beforeNative = try native(before)
        guard let revision = beforeState.sessionRevision else { throw Failure("A Standard authority action needs an observed revision.") }
        let serial = beforeState.lastViewerReceipt?.serial.value ?? 0
        button.tap()
        let accepted = try await dormant(app, "The actual Standard action must receive one accepted, session-bound authority receipt.") { value in
            guard self.standardContext(value, session: session), let state = value.controller,
                  let receipt = state.lastViewerReceipt, receipt.serial.value > serial,
                  let native = value.port.native else { return false }
            try self.require(receipt.serial.value == serial + 1 && receipt.accepted && receipt.error == nil &&
                receipt.action == action.rawValue && receipt.mode == "COMPOSE" && receipt.presentationOrdinal.value == 0 &&
                receipt.sessionGeneration == session && receipt.expectedRevision == revision && receipt.revision > revision,
                "A Standard receipt must identify the tapped action, authority generation and exact pre-tap revision.")
            guard state.sessionRevision.map({ $0 >= receipt.revision }) == true else { return false }
            let transition: Bool
            switch action {
            case .play:
                transition = state.round == beforeState.round && (state.handCount == beforeState.handCount - 1 ||
                    (["ROUND_ENDED", "FINISHED"].contains(state.phase ?? "") && state.handCount == 0))
            case .challenge:
                transition = state.round == beforeState.round && ["ROUND_ENDED", "FINISHED"].contains(state.phase ?? "")
            case .nextRound:
                transition = state.round == beforeState.round + 1 && ["PLAYING", "ROUND_ENDED", "FINISHED"].contains(state.phase ?? "")
            case .returnToLobby:
                transition = state.phase == nil && state.round == 0 && state.handCount == 0 &&
                    !self.element("game-table", app).exists && self.element("lobby-start", app).exists
            case .startGame:
                transition = state.round == 1 && ["PLAYING", "ROUND_ENDED"].contains(state.phase ?? "") && self.element("game-table", app).exists
            }
            try self.require(transition && native.intentEvents == beforeNative.intentEvents &&
                native.presentationGeneration == beforeNative.presentationGeneration,
                "The accepted Standard action must change the real authority as specified while the retained renderer remains dormant.")
            return true
        }
        capture("\(mode.rawValue) real Standard authority accepted \(action.rawValue)", app)
        return accepted
    }

    @MainActor
    private func homeAfterLeave(_ app: XCUIApplication, after generation: Counter) async throws -> Observation {
        try await dormant(app, "Confirmed Leave must end the real session and return Home.") {
            guard let state = $0.controller else { return false }
            return !state.sessionPresent && !state.practice && state.screen == "HOME" && !state.leaveConfirmation &&
                state.foreground && !state.backgrounded && state.sessionGeneration > generation && self.element("home-practice", app).isHittable &&
                !self.element("game-table", app).exists
        }
    }

    @MainActor
    private func dormant(_ app: XCUIApplication, _ message: String,
                         predicate: (Observation) throws -> Bool) async throws -> Observation {
        let first = try await wait(app, message, timeout: 30) {
            guard let state = $0.controller, let native = $0.port.native else { return false }
            guard state.mode == "COMPOSE", state.lifecycle == "COMPOSE",
                  !$0.port.active, !$0.port.closing, $0.port.lastCloseSucceeded == true,
                  native.dormant, native.emptyTree, !native.surfaceAttached, !native.inputViewEnabled,
                  !native.nativeForeground, !native.authorityForegroundGrant, !native.renderLoopActive,
                  native.queuedCommands == 0, native.queuedEvents == 0, native.queuedBytes == 0 else { return false }
            return try predicate($0)
        }
        let baseline = try native(first)
        return try await wait(app, "The retained engine must stay dormant through fresh observations.") { value in
            guard value.observationSequence.value >= first.observationSequence.value + 2, let next = value.port.native else { return false }
            try self.require(!value.port.active && next.dormant && next.emptyTree && !next.surfaceAttached &&
                !next.inputViewEnabled && !next.renderLoopActive && next.queuedCommands == 0 && next.queuedEvents == 0 &&
                next.queuedBytes == 0 && next.nativePresentedFrames == baseline.nativePresentedFrames &&
                next.iterations == baseline.iterations && next.drawCalls == baseline.drawCalls,
                "A closed production presentation must not resume rendering, input or queued work.")
            return try predicate(value)
        }
    }

    private func retained(_ value: Observation, first: Live) throws {
        let current = try native(value)
        try require(current.bootstrapCount == 1 && current.processIdentifier == first.native.processIdentifier &&
            current.retainedEnginePolicy && current.retainedIdentitiesMatchFirstEntry,
            "The production app must retain the actual engine, controller, view and layer in this process.")
    }

    @MainActor
    private func live(_ mode: Mode, _ app: XCUIApplication, session: Counter, after previous: Live? = nil,
                      timeout: TimeInterval = 15, predicate: (Live) throws -> Bool = { _ in true }) async throws -> Live {
        var result: Live?
        _ = try await wait(app, "Observe fresh, current production renderer diagnostics.", timeout: timeout) { value in
            guard let state = value.controller, let native = value.port.native,
                  let scene = value.port.renderer, let geometry = value.port.geometry,
                  state.sessionPresent, state.practice, state.sessionGeneration == session,
                  state.screen == "SESSION", state.mode == mode.selection, state.lifecycle == "ACTIVE",
                  state.foreground, !state.backgrounded, !state.leaveConfirmation,
                  value.port.active, !value.port.closing, value.port.portReadyConfirmed,
                  native.bootstrapCount == 1, native.processIdentifier > 0, native.retainedEnginePolicy,
                  native.retainedIdentitiesMatchFirstEntry, native.authorityReadyConfirmed, native.readyEvents == 1,
                  native.nativeForeground, native.authorityForegroundGrant, !native.applicationBackgrounded,
                  native.inputViewEnabled, native.surfaceAttached, geometry.surfaceAccessibilityHiddenByContainer,
                  native.renderLoopActive, !native.dormant, !native.emptyTree, !native.privacyCoverVisible,
                  !geometry.outerCoverVisible, geometry.engineAccessibilityHidden,
                  scene.schemaVersion == 1, scene.presentationMode == mode, scene.coordinateSpace == "root_viewport",
                  scene.foreground, scene.sceneStateApplied, scene.revision == state.projectedRendererRevision,
                  state.sessionRevision != nil, state.sessionRevision == state.projectedSessionRevision else { return false }
            let current = Live(observation: value, state: state, native: native, renderer: scene, geometry: geometry)
            if let previous {
                guard current.samePresentation(as: previous), scene.sequence > previous.renderer.sequence,
                      value.observationSequence > previous.observation.observationSequence else { return false }
            }
            guard try predicate(current) else { return false }
            result = current
            return true
        }
        guard let result else { throw Failure("Current renderer diagnostics were unavailable.") }
        return result
    }

    @MainActor
    private func inspectRendererBodyScroll(_ mode: Mode, _ app: XCUIApplication, session: Counter) async throws {
        // The fourth entry follows playablePractice and the existing real card selection.
        // Inspect disabled controls too; this path never submits Play, Challenge or lobby.
        let origin = try await live(mode, app, session: session)
        try require(mode == .threeD && origin.state.phase == "PLAYING" && origin.state.ownTurn &&
            origin.state.canPlay && origin.state.canSendAction && origin.state.pending == nil &&
            origin.native.queuedEvents == 0 && origin.state.handCount > 0 && !origin.renderer.handConcealed &&
            origin.renderer.selectedCount == 1,
            "The later native scroll check requires the real playable hand and its existing selected card.")
        let actions = origin.state.canChallenge ? ["lobby", "play", "challenge"] : ["lobby", "play"]
        try require(origin.state.canChallenge || !origin.renderer.controls.contains(where: { $0.group == "partydeck_action_challenge" }),
                    "A Challenge control may be absent only when the current authority reports it unavailable.")
        for action in actions {
            try require(origin.renderer.control(action, index: -1) != nil,
                        "Every currently required authority control must have one real renderer target.")
        }
        attach(lastDocument, "\(mode.rawValue) round \(origin.state.round) selected hand before body scroll")
        var gestures = 0
        var latest = origin
        for action in actions {
            let reached = try await reachRenderer(action, mode, app, session: session, performTap: false)
            try requireScrollPreservedInput(origin, reached.value)
            gestures += reached.gestures
            latest = reached.value
        }
        try require(gestures > 0, "Native scroll coverage requires an actual measured body drag; fitting without a drag is not scroll evidence.")
        let fresh = try await live(mode, app, session: session, after: latest) {
            $0.native.nativePresentedFrames > latest.native.nativePresentedFrames && $0.native.iterations > latest.native.iterations
        }
        try requireScrollPreservedInput(origin, fresh)
        _ = try measuredFrame(fresh, app)
        let viewport = CGRect(origin: .zero, size: fresh.renderer.viewport.size)
        var bounds: [[String: Any]] = []
        for action in actions {
            guard let control = fresh.renderer.control(action, index: -1) else {
                throw Failure("A required renderer control disappeared after the native scroll.")
            }
            let rect = try rectangle(control.rect)
            let clip = try rectangle(control.clipRect)
            try require(control.visible && viewport.insetBy(dx: -0.5, dy: -0.5).contains(clip) &&
                clip.insetBy(dx: -0.5, dy: -0.5).contains(rect) &&
                rect.width >= 48 && rect.height >= 48,
                "Every inspected action must retain its whole 48-point-or-larger bounds inside the real clip after scrolling.")
            bounds.append(["action": action, "enabled": control.enabled, "rect": control.rect, "clipRect": control.clipRect])
        }
        let evidence: [String: Any] = [
            "schemaVersion": 1, "round": fresh.state.round, "controls": bounds, "scrollGestures": gestures,
            "canChallenge": fresh.state.canChallenge,
            "challengeCoverage": fresh.state.canChallenge ? "full_bounds_after_native_scroll" : "authority_unavailable_not_exercised",
            "beforeObservationSequence": String(origin.observation.observationSequence.value),
            "afterObservationSequence": String(fresh.observation.observationSequence.value),
            "beforeRendererSequence": String(origin.renderer.sequence.value),
            "afterRendererSequence": String(fresh.renderer.sequence.value),
            "selectedCount": fresh.renderer.selectedCount, "handConcealed": fresh.renderer.handConcealed,
            "authorityIntentCountBefore": origin.native.intentEvents, "authorityIntentCountAfter": fresh.native.intentEvents
        ]
        attach(try JSONSerialization.data(withJSONObject: evidence, options: [.sortedKeys]),
               "\(mode.rawValue) round \(fresh.state.round) actual body scroll coverage")
        capture("\(mode.rawValue) round \(fresh.state.round) full native action bounds preserve selection", app)
    }

    private func requireScrollPreservedInput(_ before: Live, _ after: Live) throws {
        let selectedBefore = before.renderer.controls.filter { $0.group == "partydeck_hand_card" && $0.selected }.map(\.cardIndex).sorted()
        let selectedAfter = after.renderer.controls.filter { $0.group == "partydeck_hand_card" && $0.selected }.map(\.cardIndex).sorted()
        try require(after.sameTouchContext(as: before) && after.isInteractive &&
            after.state.phase == before.state.phase && after.state.round == before.state.round &&
            after.state.handCount == before.state.handCount && after.state.ownTurn == before.state.ownTurn &&
            after.state.canSendAction == before.state.canSendAction && after.state.pending == before.state.pending &&
            after.state.canPlay == before.state.canPlay && after.state.canChallenge == before.state.canChallenge &&
            after.state.lastViewerReceipt?.serial == before.state.lastViewerReceipt?.serial &&
            after.native.intentEvents == before.native.intentEvents && after.native.exitEvents == before.native.exitEvents &&
            after.native.rejectedEvents == before.native.rejectedEvents && after.native.queuedEvents == 0 &&
            after.renderer.handConcealed == before.renderer.handConcealed &&
            after.renderer.selectedCount == before.renderer.selectedCount && selectedAfter == selectedBefore &&
            after.renderer.privateFaceCount == before.renderer.privateFaceCount &&
            after.renderer.privateLabelCount == before.renderer.privateLabelCount,
            "A body scroll must preserve the current input/privacy context, selected cards and private content counts without any authority action.")
    }

    @MainActor
    private func tapRenderer(_ action: String, _ mode: Mode, _ app: XCUIApplication, session: Counter,
                             cardIndex: Int = -1) async throws -> Live {
        let reached = try await reachRenderer(action, mode, app, session: session, cardIndex: cardIndex, performTap: true)
        return reached.value
    }

    @MainActor
    private func reachRenderer(_ action: String, _ mode: Mode, _ app: XCUIApplication, session: Counter,
                               cardIndex: Int = -1, performTap: Bool) async throws -> (value: Live, gestures: Int) {
        var value = try await live(mode, app, session: session)
        var gestures = 0
        for _ in 0..<16 {
            guard let candidate = value.renderer.control(action, index: cardIndex) else {
                throw Failure("The requested real renderer control is missing.")
            }
            let confirmed = try await live(mode, app, session: session, after: value) {
                $0.native.nativePresentedFrames > value.native.nativePresentedFrames && $0.native.iterations > value.native.iterations
            }
            guard confirmed.sameTouchContext(as: value),
                  confirmed.renderer.control(action, index: cardIndex) == candidate else { value = confirmed; continue }
            value = confirmed
            let rect = try rectangle(candidate.rect)
            let clip = try rectangle(candidate.clipRect)
            let frame = try measuredFrame(value, app)
            let viewport = CGRect(origin: .zero, size: value.renderer.viewport.size)
            try require((!performTap || candidate.enabled) && viewport.insetBy(dx: -0.5, dy: -0.5).contains(clip),
                        "Only enabled controls with a measured clip inside the native viewport may receive input.")
            guard let latestObservation = try read(app), let latestScene = latestObservation.port.renderer,
                  let latestNative = latestObservation.port.native, let latestState = latestObservation.controller,
                  let latestGeometry = latestObservation.port.geometry else { continue }
            let latest = Live(observation: latestObservation, state: latestState, native: latestNative,
                              renderer: latestScene, geometry: latestGeometry)
            guard latest.sameTouchContext(as: value), latest.isInteractive,
                  latestScene.control(action, index: cardIndex) == candidate else { value = try await live(mode, app, session: session); continue }
            _ = try measuredFrame(latest, app)
            if candidate.visible && clip.insetBy(dx: -0.5, dy: -0.5).contains(rect) {
                try require(rect.width >= 44 && rect.height >= 44, "A real engine touch target must measure at least 44 points.")
                if performTap {
                    attach(lastDocument, "\(mode.rawValue) measured \(action) before actual coordinate tap")
                    coordinate(CGPoint(x: frame.minX + rect.midX, y: frame.minY + rect.midY), app).tap()
                } else {
                    attach(lastDocument, "\(mode.rawValue) measured whole \(action) bounds without tapping")
                }
                return (latest, gestures)
            }
            try require(gestures < 8 && clip.width >= 44 && clip.height >= 44 &&
                        rect.width <= clip.width + 0.5 && rect.height <= clip.height + 0.5,
                        "A clipped control must fit the measured scroll area within the real gesture bound.")
            let start: CGPoint
            let end: CGPoint
            if rect.minY < clip.minY {
                start = CGPoint(x: clip.midX, y: clip.minY + clip.height * 0.2)
                end = CGPoint(x: start.x, y: start.y + scrollDistance(clip.minY - rect.minY, span: clip.height, target: rect.height))
            } else if rect.maxY > clip.maxY {
                start = CGPoint(x: clip.midX, y: clip.minY + clip.height * 0.8)
                end = CGPoint(x: start.x, y: start.y - scrollDistance(rect.maxY - clip.maxY, span: clip.height, target: rect.height))
            } else if rect.minX < clip.minX {
                start = CGPoint(x: clip.minX + clip.width * 0.2, y: clip.midY)
                end = CGPoint(x: start.x + scrollDistance(clip.minX - rect.minX, span: clip.width, target: rect.width), y: start.y)
            } else {
                start = CGPoint(x: clip.minX + clip.width * 0.8, y: clip.midY)
                end = CGPoint(x: start.x - scrollDistance(rect.maxX - clip.maxX, span: clip.width, target: rect.width), y: start.y)
            }
            attach(lastDocument, "\(mode.rawValue) measured \(action) before actual scroll")
            let from = coordinate(CGPoint(x: frame.minX + start.x, y: frame.minY + start.y), app)
            let to = coordinate(CGPoint(x: frame.minX + end.x, y: frame.minY + end.y), app)
            from.press(forDuration: 0.1, thenDragTo: to)
            gestures += 1
            if performTap {
                value = try await live(mode, app, session: session, after: latest)
            } else {
                value = try await live(mode, app, session: session, after: latest) {
                    $0.native.nativePresentedFrames > latest.native.nativePresentedFrames && $0.native.iterations > latest.native.iterations
                }
                try requireScrollPreservedInput(latest, value)
            }
        }
        throw Failure("The actual renderer target did not settle inside its clip within the bounded touch attempts.")
    }

    @MainActor
    private func measuredFrame(_ value: Live, _ app: XCUIApplication) throws -> CGRect {
        let frame = try rectangle(value.geometry.frame)
        let bounds = try rectangle(value.geometry.bounds)
        let viewport = value.renderer.viewport
        let surface = value.native.surfaceSize
        try require(value.geometry.coordinateSpace == "screen" && abs(bounds.minX) <= 0.5 && abs(bounds.minY) <= 0.5 &&
            viewport.width.isFinite && viewport.height.isFinite && viewport.width > 0 && viewport.height > 0 &&
            abs(Double(frame.width) - viewport.width) <= 1 && abs(Double(frame.height) - viewport.height) <= 1 &&
            abs(Double(bounds.width) - viewport.width) <= 1 && abs(Double(bounds.height) - viewport.height) <= 1 &&
            abs(surface.width - viewport.width) <= 1 && abs(surface.height - viewport.height) <= 1 &&
            app.frame.insetBy(dx: -0.5, dy: -0.5).contains(frame),
            "Renderer logical coordinates must agree with the actual UIKit bounds and screen coordinate frame.")
        return frame
    }

    @MainActor
    private func coordinate(_ screenPoint: CGPoint, _ app: XCUIApplication) -> XCUICoordinate {
        app.coordinate(withNormalizedOffset: .zero).withOffset(
            CGVector(dx: screenPoint.x - app.frame.minX, dy: screenPoint.y - app.frame.minY))
    }

    private func rectangle(_ parts: [Double]) throws -> CGRect {
        try require(parts.count == 4 && parts.allSatisfy(\.isFinite) && parts[2] > 0 && parts[3] > 0,
                    "A touch rectangle must contain four finite coordinates and positive dimensions.")
        return CGRect(x: parts[0], y: parts[1], width: parts[2], height: parts[3])
    }

    private func scrollDistance(_ gap: CGFloat, span: CGFloat, target: CGFloat) -> CGFloat {
        min(span * 0.45, max(24, gap + min(12, max(0, (span - target) / 2))))
    }

    @MainActor
    private func tapElement(_ identifier: String, _ app: XCUIApplication) async throws {
        let target = try await reachable(identifier, app)
        target.tap()
    }

    @MainActor
    private func leaveDialog(_ app: XCUIApplication) async throws {
        _ = try await reachable("leave-confirm", app)
        _ = try await reachable("leave-cancel", app)
        capture("Actual production Leave confirmation", app)
    }

    @MainActor
    private func reachable(_ identifier: String, _ app: XCUIApplication) async throws -> XCUIElement {
        // A Compose dialog may hide the SwiftUI badge. Its actual user controls remain sufficient
        // for the dialog action; session/privacy/close observations are required after it dismisses.
        let deadline = ProcessInfo.processInfo.systemUptime + 15
        while ProcessInfo.processInfo.systemUptime < deadline {
            try require(app.state != .notRunning, "The production app exited while awaiting a user control.")
            _ = try read(app)
            let target = element(identifier, app)
            if target.exists && target.isEnabled && target.isHittable { return target }
            try await Task.sleep(nanoseconds: 150_000_000)
        }
        throw Failure("The actual \(identifier) control was not enabled and reachable.")
    }

    @MainActor
    private func wait(_ app: XCUIApplication, _ message: String, timeout: TimeInterval = 15,
                      predicate: (Observation) throws -> Bool) async throws -> Observation {
        let deadline = ProcessInfo.processInfo.systemUptime + timeout
        while ProcessInfo.processInfo.systemUptime < deadline {
            try require(app.state != .notRunning, "The production app exited before completing the smoke.")
            if let value = try read(app), try predicate(value) { return value }
            try await Task.sleep(nanoseconds: 150_000_000)
        }
        throw Failure(message)
    }

    @MainActor
    private func read(_ app: XCUIApplication) throws -> Observation? {
        guard app.state == .runningForeground else { return nil }
        // Leave can remove native chrome between an existence check and a live value query.
        // Select and read from one captured hierarchy, keeping native status ahead of the badge.
        var pending: [any XCUIElementSnapshot] = [try app.snapshot()]
        var node: (any XCUIElementSnapshot)?
        while let snapshot = pending.popLast() {
            if snapshot.identifier == "godot-session-status" {
                node = snapshot
                break
            }
            if snapshot.identifier == "partydeck-session-qualification" && node == nil {
                node = snapshot
            }
            pending.append(contentsOf: snapshot.children.reversed())
        }
        guard let text = node?.value as? String, !text.isEmpty else { return nil }
        guard let data = text.data(using: .utf8), data.count <= 32768,
              let value = try? JSONDecoder().decode(Observation.self, from: data) else {
            throw Failure("Production qualification observation is malformed; missing values cannot pass a privacy assertion.")
        }
        lastDocument = data
        try require(value.schemaVersion == 1 && value.observationInstalled && value.port.activationValid &&
            value.port.profile == "qualification" && value.port.enabledModes.count == 2 &&
            Set(value.port.enabledModes) == Set([Mode.twoD, Mode.threeD]),
            "Both explicitly built qualification modes and the observation condition are required; shipping activation must fail this smoke.")
        let state = try controller(value)
        try require(state.supported && !state.exhausted && state.problem == nil &&
            !value.port.quarantined && !value.port.disposed,
            "The real practice controller and native port must remain healthy.")
        if let native = value.port.native {
            try require(!native.failurePresent && !native.quarantined && native.nativeFailedPresentations == 0 && native.rejectedEvents == 0,
                        "The retained native owner reported a real failure or rejected production event.")
        }
        if let lastObservation {
            try require(value.observationSequence >= lastObservation.observationSequence,
                        "The selected production observation must not regress to an older sample.")
        }
        lastObservation = value
        return value
    }

    private func controller(_ value: Observation) throws -> Controller {
        guard let state = value.controller else { throw Failure("The production controller observation was not installed.") }
        return state
    }
    private func native(_ value: Observation) throws -> Native {
        guard let state = value.port.native else { throw Failure("The actual retained native owner was not observed.") }
        return state
    }
    private func require(_ condition: Bool, _ message: String) throws { if !condition { throw Failure(message) } }

    @MainActor
    private func element(_ identifier: String, _ app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }
    @MainActor
    private func privateCards(_ app: XCUIApplication) -> XCUIElementQuery {
        app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH %@", "game-card-"))
    }
    @MainActor
    private func capture(_ name: String, _ app: XCUIApplication) {
        // Tests use local practice only. Keep the existing invitation screenshot prohibition as a final guard.
        if app.state != .runningForeground || !element("invitation-dialog", app).exists {
            let screenshot = XCTAttachment(screenshot: app.state == .runningForeground ? app.screenshot() : XCUIScreen.main.screenshot())
            screenshot.name = name; screenshot.lifetime = .keepAlways; add(screenshot)
        }
        attach(lastDocument, "\(name) latest sanitized observation")
    }
    private func attach(_ data: Data?, _ name: String) {
        guard let data else { return }
        let attachment = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }

    private struct Failure: Error { let message: String; init(_ message: String) { self.message = message } }
    private enum Mode: String, Decodable, Hashable {
        case twoD = "2d", threeD = "3d"
        var selection: String { self == .twoD ? "GODOT_2D" : "GODOT_3D" }
    }
    private enum StandardAction: String {
        case play = "PLAY_CARDS", challenge = "CHALLENGE", nextRound = "NEXT_ROUND"
        case returnToLobby = "RETURN_TO_LOBBY", startGame = "START_GAME"
        var identifier: String {
            switch self {
            case .play: return "game-play"
            case .challenge: return "game-challenge"
            case .nextRound: return "game-next-round"
            case .returnToLobby: return "game-rematch"
            case .startGame: return "lobby-start"
            }
        }
    }
    // JSONDecoder requires every nonoptional field and enforces Boolean/numeric types.
    // Long counters are decimal strings on the Kotlin/native boundary, never lossy JSON doubles.
    private struct Counter: Decodable, Comparable {
        let value: UInt64
        init(from decoder: Decoder) throws {
            let text = try decoder.singleValueContainer().decode(String.self)
            guard !text.isEmpty, text.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }),
                  text == "0" || text.first != "0", let value = UInt64(text) else {
                throw Failure("A required production counter is malformed.")
            }
            self.value = value
        }
        static func < (left: Counter, right: Counter) -> Bool { left.value < right.value }
    }
    private struct Observation: Decodable {
        let schemaVersion: Int
        let observationSequence: Counter
        let observationInstalled: Bool
        let controller: Controller?
        let port: Port
    }
    private struct Controller: Decodable {
        let supported: Bool, exhausted: Bool, sessionPresent: Bool, practice: Bool
        let sessionGeneration: Counter, privacyEpoch: Counter, presentationOrdinal: Counter
        let sessionRevision: Counter?, projectedRendererRevision: Counter?, projectedSessionRevision: Counter?
        let screen: String, mode: String, lifecycle: String
        let phase: String?, pending: String?, problem: String?
        let round: Int, handCount: Int
        let ownTurn: Bool, canSendAction: Bool, canPlay: Bool, canChallenge: Bool, canAdvanceRound: Bool
        let foreground: Bool, backgrounded: Bool, leaveConfirmation: Bool
        let lastViewerReceipt: Receipt?
    }
    private struct Receipt: Decodable {
        let serial: Counter, sessionGeneration: Counter, presentationOrdinal: Counter
        let expectedRevision: Counter, revision: Counter
        let mode: String, action: String
        let accepted: Bool
        let error: String?
    }
    private struct Port: Decodable {
        let activationValid: Bool, profile: String, enabledModes: [Mode]
        let ownerCreated: Bool, active: Bool, closing: Bool, quarantined: Bool, disposed: Bool, portReadyConfirmed: Bool
        let lastCloseSucceeded: Bool?
        let native: Native?
        let geometry: Geometry?
        let renderer: Renderer?
    }
    private struct Native: Decodable {
        let bootstrapCount: UInt64, processIdentifier: UInt64
        let presentationGeneration: Counter, lifecycleGeneration: Counter, inputGeneration: Counter
        let readyEvents: UInt64, intentEvents: UInt64, exitEvents: UInt64, rejectedEvents: UInt64
        let nativePresentedFrames: UInt64, nativeFailedPresentations: UInt64, iterations: UInt64, drawCalls: UInt64
        let authorityReadyConfirmed: Bool, nativeForeground: Bool, authorityForegroundGrant: Bool, applicationBackgrounded: Bool
        let inputViewEnabled: Bool, privacyCoverVisible: Bool, renderLoopActive: Bool, dormant: Bool, emptyTree: Bool
        let surfaceAttached: Bool, surfaceAccessibilityHidden: Bool, retainedEnginePolicy: Bool
        let failurePresent: Bool, quarantined: Bool, retainedIdentitiesMatchFirstEntry: Bool
        let queuedCommands: UInt64, queuedEvents: UInt64, queuedBytes: UInt64
        let surfaceSize: Size
    }
    private struct Geometry: Decodable, Equatable {
        let coordinateSpace: String
        let frame: [Double], bounds: [Double]
        let outerCoverVisible: Bool, engineAccessibilityHidden: Bool
        // The actual native child must remain inside the container that hides its subtree.
        // Native's separate surfaceAccessibilityHidden is only the child-local property.
        let surfaceAccessibilityHiddenByContainer: Bool
    }
    private struct Size: Decodable, Equatable {
        let width: Double, height: Double
        var size: CGSize { CGSize(width: width, height: height) }
    }
    private struct Control: Decodable, Equatable {
        let group: String, cardIndex: Int
        let rect: [Double], clipRect: [Double]
        let visible: Bool, enabled: Bool, selected: Bool
    }
    private struct Renderer: Decodable {
        let schemaVersion: Int
        let requestId: Counter, sequence: Counter, revision: Counter
        let presentationMode: Mode, coordinateSpace: String, foreground: Bool
        let viewport: Size
        let sceneStateApplied: Bool, handConcealed: Bool
        let selectedCount: UInt64, privateFaceCount: UInt64, privateLabelCount: UInt64
        let controls: [Control]
        var concealed: Bool { handConcealed && selectedCount == 0 && privateFaceCount == 0 && privateLabelCount == 0 }
        func control(_ action: String, index: Int) -> Control? {
            let group = action == "card" ? "partydeck_hand_card" : "partydeck_action_\(action)"
            let matches = controls.filter { $0.group == group && $0.cardIndex == index }
            return matches.count == 1 ? matches[0] : nil
        }
    }
    private struct Live {
        let observation: Observation, state: Controller, native: Native, renderer: Renderer, geometry: Geometry
        var isInteractive: Bool {
            observation.port.active && !observation.port.closing && observation.port.portReadyConfirmed &&
                state.sessionPresent && state.practice && state.screen == "SESSION" && state.mode == renderer.presentationMode.selection &&
                state.lifecycle == "ACTIVE" && state.foreground && !state.backgrounded && !state.leaveConfirmation &&
                native.nativeForeground && native.authorityForegroundGrant && native.authorityReadyConfirmed &&
                native.inputViewEnabled && native.renderLoopActive && !native.privacyCoverVisible && !native.dormant &&
                !native.emptyTree && native.surfaceAttached && geometry.surfaceAccessibilityHiddenByContainer && geometry.engineAccessibilityHidden &&
                !geometry.outerCoverVisible && renderer.foreground && renderer.sceneStateApplied && renderer.revision == state.projectedRendererRevision &&
                state.sessionRevision != nil && state.sessionRevision == state.projectedSessionRevision
        }
        func samePresentation(as other: Live) -> Bool {
            state.sessionGeneration == other.state.sessionGeneration && state.presentationOrdinal == other.state.presentationOrdinal &&
                native.presentationGeneration == other.native.presentationGeneration && renderer.presentationMode == other.renderer.presentationMode
        }
        func sameTouchContext(as other: Live) -> Bool {
            samePresentation(as: other) && native.lifecycleGeneration == other.native.lifecycleGeneration &&
                native.inputGeneration == other.native.inputGeneration && state.privacyEpoch == other.state.privacyEpoch &&
                state.sessionRevision == other.state.sessionRevision && state.projectedRendererRevision == other.state.projectedRendererRevision &&
                state.projectedSessionRevision == other.state.projectedSessionRevision && renderer.revision == other.renderer.revision &&
                renderer.viewport == other.renderer.viewport && geometry == other.geometry
        }
    }
}
#endif
