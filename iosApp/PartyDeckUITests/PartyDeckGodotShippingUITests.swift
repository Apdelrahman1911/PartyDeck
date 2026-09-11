#if PARTYDECK_GODOT_SHIPPING_SMOKE
#if !DEBUG
#error("The selected shipping UI smoke requires the Debug Simulator test target.")
#endif
#if PARTYDECK_GODOT_SESSION_QUALIFICATION
#error("Shipping UI smoke must not compile with qualification observation enabled.")
#endif

import Foundation
import XCTest

/// Explicit shipping-profile route check. The runner verifies the actual app's profile and build flags.
/// Native screenshots still require pixel review; hidden renderer accessibility is not frame evidence.
final class PartyDeckGodotShippingUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    @MainActor
    func testShippingPickerOpensBothNativeTablesAndReturnsToStandard() async throws {
        let app = XCUIApplication()
        app.launchArguments = []
        app.launchEnvironment = [:]
        app.launch()
        defer { app.terminate() }

        try await wait("Shipping Home must expose the actual practice action.", timeout: 30) {
            app.state == .runningForeground && self.element("home-practice", app).isHittable
        }
        try noObservation(app)
        try capture("shipping-home", app)
        try await tap("home-practice", app)
        try await wait("Practice must reach the real Standard table.", timeout: 15) {
            self.element("game-table", app).exists && self.element("presentation-picker", app).isHittable
        }
        try await waitForHumanTurn(app)

        // Read only this practice viewer's native hand labels in test memory. Never attach or log them.
        // There is no Play/Challenge between entries, so the real human-turn hand must remain unchanged.
        let standard = StandardTableAcceptance(app)
        let initialHand = try standard.reveal(count: 5)
        try standard.control("game-hide-hand").tap()
        try standard.concealed()
        try capture("shipping-standard-before-entry", app)

        for (mode, choice) in [("2d", "godot_2d"), ("3d", "godot_3d")] {
            try await tap("presentation-picker", app)
            let options = element("presentation-options", app)
            try require(options.waitForExistence(timeout: 10), "Table style must open the actual shared picker.")
            for identifier in ["compose", "godot_2d", "godot_3d"] {
                _ = try reachableChoice("presentation-choice-\(identifier)", options: options, app: app)
            }
            let selected = try reachableChoice("presentation-choice-\(choice)", options: options, app: app)
            try capture("shipping-\(mode)-picker", app)
            selected.tap()

            try await wait("The selected shipping table must finish the real native Ready/foreground handoff.", timeout: 60) {
                self.nativeReady(app)
            }
            try noObservation(app)
            do {
                try require(!element("game-table", app).exists && !options.exists,
                            "Native entry must leave the shared game surface and picker.")
            } catch {
                recordEntryAbsenceFailure(mode, app, retainedOptions: options)
                throw error
            }
            try capture("shipping-\(mode)-native-ready", app)
            try require(nativeReady(app), "Native ready state and return controls must survive capture.")
            try await tap("godot-standard-table", app)

            try await wait("Native Standard table must return to the existing shared game.", timeout: 10) {
                self.element("game-table", app).exists && self.element("presentation-picker", app).isHittable &&
                    !self.element("godot-session-table", app).exists &&
                    !self.element("godot-standard-table", app).exists && !self.element("home-practice", app).exists
            }
            try noObservation(app)
            try standard.concealed()
            _ = try standard.reveal(count: 5, expectedLabels: initialHand)
            try standard.control("game-hide-hand").tap()
            try standard.concealed()
            try capture("shipping-\(mode)-standard-return", app)
        }

        try await tap("navigation-back", app)
        try await wait("Leaving the actual practice session must require confirmation.") {
            self.element("leave-confirm", app).isHittable && self.element("leave-cancel", app).exists
        }
        try await tap("leave-confirm", app)
        try await wait("Confirmed Leave must return to Home with no Standard or native game surface.") {
            self.element("home-practice", app).isHittable && !self.element("game-table", app).exists &&
                !self.element("godot-session-table", app).exists
        }
        try capture("shipping-home-after-leave", app)
    }

    @MainActor
    private func element(_ identifier: String, _ app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    @MainActor
    private func noObservation(_ app: XCUIApplication) throws {
        try require(!element("partydeck-session-qualification", app).exists,
                    "Shipping entry must not expose the qualification observation badge.")
    }

    @MainActor
    private func nativeReady(_ app: XCUIApplication) -> Bool {
        let status = element("godot-session-status", app)
        let standard = element("godot-standard-table", app)
        let leave = element("godot-leave-table", app)
        return app.state == .runningForeground && element("godot-session-table", app).exists && status.exists &&
            status.label == "Your table is ready" &&
            !element("godot-session-privacy-cover", app).exists &&
            standard.exists && standard.isEnabled && standard.isHittable &&
            leave.exists && leave.isEnabled && leave.isHittable
        // The inner native cover is inaccessible by design; do not infer its pixels from exists=false.
    }

    @MainActor
    private func tap(_ identifier: String, _ app: XCUIApplication) async throws {
        let target = element(identifier, app)
        try await wait("A required shipping control must be enabled and hittable.") {
            app.state == .runningForeground && target.exists && target.isEnabled && target.isHittable
        }
        target.tap()
    }

    @MainActor
    private func reachableChoice(_ identifier: String, options: XCUIElement, app: XCUIApplication) throws -> XCUIElement {
        let matches = app.descendants(matching: .any).matching(identifier: identifier)
        let target = matches.firstMatch
        // Each search first reaches the top, then traverses downward. This also works after checking 3D.
        for towardTop in [true, false] {
            for _ in 0..<3 {
                try require(app.state == .runningForeground && options.exists, "The actual picker must stay open while scrolling.")
                if matches.count == 1 && target.isEnabled && target.isHittable { return target }
                if towardTop { options.swipeDown() } else { options.swipeUp() }
            }
        }
        try require(matches.count == 1 && target.isEnabled && target.isHittable,
                    "Standard, 2D and 3D must each be a unique reachable shipping choice.")
        return target
    }

    @MainActor
    private func waitForHumanTurn(_ app: XCUIApplication) async throws {
        let play = element("game-play", app)
        let nextRound = element("game-next-round", app)
        let result = element("game-round-result", app)
        let winner = element("game-winner", app)
        let roundLabel = result.descendants(matching: .any)
            .matching(NSPredicate(format: "label MATCHES %@", "ROUND [0-9]+")).firstMatch
        // Actual bots may end a round before the human acts. Only the real next-round control advances it.
        for _ in 0..<4 {
            try await wait("Practice must reach a human turn or an actionable round result.", timeout: 30) {
                play.exists || nextRound.exists || winner.exists
            }
            if play.exists { return }
            try require(!winner.exists && roundLabel.exists,
                        "Practice must offer a human turn before finishing, and identify any completed round.")
            let completedRound = roundLabel.label
            for _ in 0..<3 where !nextRound.isHittable { result.swipeUp() }
            try await tap("game-next-round", app)
            try await wait("A real round advance must leave the previous result.", timeout: 30) {
                play.exists || winner.exists || (nextRound.exists && roundLabel.exists && roundLabel.label != completedRound)
            }
        }
        throw Failure("Practice did not offer a human turn within four real rounds.")
    }

    @MainActor
    private func wait(_ message: String, timeout: TimeInterval = 10, condition: () -> Bool) async throws {
        let deadline = ProcessInfo.processInfo.systemUptime + timeout
        while ProcessInfo.processInfo.systemUptime < deadline {
            if condition() { return }
            try await Task.sleep(nanoseconds: 150_000_000)
        }
        throw Failure(message)
    }

    /// Failure-only evidence, collected before the caller rethrows and its defer terminates the app.
    /// Later absence never changes the failed assertion into a pass. No label, value or tree dump is read.
    @MainActor
    private func recordEntryAbsenceFailure(_ mode: String, _ app: XCUIApplication,
                                          retainedOptions: XCUIElement) {
        let beforeCapture = entryAbsenceSample(app, retainedOptions: retainedOptions)
        let captureName = "shipping-\(mode)-native-entry-absence-failure"
        var captureOutcome = "not_attached"
        do {
            // Reuse every existing foreground/concealment/invitation/observation guard.
            try capture(captureName, app)
            captureOutcome = "attached"
        } catch {
            // A refused diagnostic capture must not replace the original assertion error.
        }
        let afterCapture = entryAbsenceSample(app, retainedOptions: retainedOptions)
        let document: [String: Any] = [
            "schemaVersion": 1,
            "kind": "shipping_native_entry_absence_failure",
            "mode": mode,
            "phase": "before_original_error_rethrow_and_deferred_termination",
            "sampling": "sequential_queries_not_an_atomic_snapshot",
            "frameCoordinateSource": "XCUIElement.frame",
            "frameComponents": ["originX", "originY", "width", "height"],
            "captureName": captureName,
            "captureOutcome": captureOutcome,
            "beforeCapture": beforeCapture,
            "afterCapture": afterCapture,
        ]
        let data = (try? JSONSerialization.data(withJSONObject: document, options: [.sortedKeys])) ??
            Data("{\"schemaVersion\":1,\"kind\":\"shipping_native_entry_absence_failure\",\"diagnosticEncodingFailed\":true}".utf8)
        let attachment = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
        attachment.name = "shipping-\(mode)-native-entry-absence-diagnostic"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    @MainActor
    private func entryAbsenceSample(_ app: XCUIApplication, retainedOptions: XCUIElement) -> [String: Any] {
        let started = ProcessInfo.processInfo.systemUptime
        let foreground = app.state == .runningForeground
        let retainedPicker = entryAbsenceReferenceFacts(retainedOptions)
        let freshPicker = entryAbsenceQueryFacts("presentation-options", app)
        let freshGameTable = entryAbsenceQueryFacts("game-table", app)
        let freshNativeTable = entryAbsenceQueryFacts("godot-session-table", app)
        return [
            "startedUptime": started,
            "finishedUptime": ProcessInfo.processInfo.systemUptime,
            "runningForeground": foreground,
            "retainedPickerReference": retainedPicker,
            "freshPickerQuery": freshPicker,
            "freshGameTableQuery": freshGameTable,
            "freshNativeTableQuery": freshNativeTable,
        ]
    }

    @MainActor
    private func entryAbsenceQueryFacts(_ identifier: String, _ app: XCUIApplication) -> [String: Any] {
        let started = ProcessInfo.processInfo.systemUptime
        let query = app.descendants(matching: .any).matching(identifier: identifier)
        let count = query.count
        var facts = entryAbsenceReferenceFacts(query.firstMatch)
        facts["queryStartedUptime"] = started
        facts["matchCount"] = count
        return facts
    }

    @MainActor
    private func entryAbsenceReferenceFacts(_ target: XCUIElement) -> [String: Any] {
        let started = ProcessInfo.processInfo.systemUptime
        let exists = target.exists
        var facts: [String: Any] = [
            "startedUptime": started,
            "exists": exists,
            // A retained element reference has no separately observed query count.
            "matchCount": NSNull(),
            "isHittable": NSNull(),
            "frame": NSNull(),
        ]
        if exists {
            facts["isHittable"] = target.isHittable
            let frame = target.frame
            let coordinates = [Double(frame.origin.x), Double(frame.origin.y),
                               Double(frame.size.width), Double(frame.size.height)]
            if coordinates.allSatisfy({ $0.isFinite }) { facts["frame"] = coordinates }
        }
        facts["finishedUptime"] = ProcessInfo.processInfo.systemUptime
        return facts
    }

    @MainActor
    private func capture(_ name: String, _ app: XCUIApplication) throws {
        let privateCards = app.descendants(matching: .any)
            .matching(NSPredicate(format: "identifier BEGINSWITH %@", "game-card-"))
        try require(app.state == .runningForeground && !element("invitation-dialog", app).exists && privateCards.count == 0,
                    "Shipping captures require the foreground app, concealed Standard cards and no open invitation.")
        try noObservation(app)
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func require(_ condition: Bool, _ message: String) throws {
        if !condition { throw Failure(message) }
    }

    private struct Failure: Error, CustomStringConvertible {
        let description: String
        init(_ description: String) { self.description = description }
    }
}
#endif
