#if PARTYDECK_GODOT_SHIPPING_SMOKE
#if !DEBUG
#error("Shipping native Leave coverage requires the Debug Simulator test target.")
#endif
#if PARTYDECK_GODOT_SESSION_QUALIFICATION
#error("Shipping native Leave coverage must not compile with qualification observation.")
#endif

import Foundation
import XCTest

/// Actual shipping toolbar Leave, separately from the shared navigation-back route.
/// The runner must bind the shipping profile and select both named cases explicitly.
/// Screenshots require independent pixel review; no renderer observation is enabled here.
final class PartyDeckGodotNativeLeaveShippingUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    @MainActor
    func testShipping2DNativeLeaveCancelAndConfirm() async throws { try await exercise("2d") }

    @MainActor
    func testShipping3DNativeLeaveCancelAndConfirm() async throws { try await exercise("3d") }

    @MainActor
    private func exercise(_ mode: String) async throws {
        let app = XCUIApplication()
        app.launchArguments = []
        app.launchEnvironment = [:]
        app.launch()
        defer { app.terminate() }

        try await wait("Shipping Home must expose the actual practice action.", timeout: 30) {
            app.state == .runningForeground && self.element("home-practice", app).isHittable
        }
        try noObservation(app)
        try await tap("home-practice", app)
        try await wait("Practice must reach the actual Standard table.", timeout: 15) {
            self.element("game-table", app).exists && self.element("presentation-picker", app).isHittable
        }
        try await waitForHumanTurn(app)

        // Compare only this real practice viewer's hand in memory. Never attach its labels.
        // No Play or Challenge is submitted between this point and the cancellation check.
        let standard = StandardTableAcceptance(app)
        let hand = try standard.reveal(count: 5)
        try standard.control("game-hide-hand").tap()
        try standard.concealed()

        try await enter(mode, app)
        try capture("shipping-\(mode)-native-leave-ready", app)
        try await nativeLeaveDialog(app)
        try await tap("leave-cancel", app)
        try await wait("Cancelling native Leave must reveal the retained Standard game.") {
            self.element("game-table", app).exists && self.element("presentation-picker", app).isHittable &&
                self.nativeDismissed(app) && !self.element("home-practice", app).exists &&
                !self.element("leave-confirm", app).exists && !self.element("leave-cancel", app).exists
        }
        try noObservation(app)
        try standard.concealed()
        _ = try standard.reveal(count: 5, expectedLabels: hand)
        try standard.control("game-hide-hand").tap()
        try standard.concealed()
        try capture("shipping-\(mode)-native-leave-cancelled", app)

        // A second real entry is necessary: confirming shared navigation-back would
        // not exercise the native Leave callback or native close a second time.
        try await enter(mode, app)
        try await nativeLeaveDialog(app)
        try capture("shipping-\(mode)-native-leave-confirmation", app)
        try await tap("leave-confirm", app)
        try await wait("Confirming native Leave must return Home and remove the session UI.") {
            self.element("home-practice", app).isHittable && self.nativeDismissed(app) &&
                !self.element("game-table", app).exists && !self.element("presentation-picker", app).exists &&
                !self.element("presentation-options", app).exists &&
                !self.element("leave-confirm", app).exists && !self.element("leave-cancel", app).exists
        }
        try capture("shipping-\(mode)-native-leave-confirmed-home", app)
    }

    @MainActor
    private func enter(_ mode: String, _ app: XCUIApplication) async throws {
        try require(mode == "2d" || mode == "3d", "Only the two real shipping presentations are selected.")
        try noObservation(app)
        try await tap("presentation-picker", app)
        let options = element("presentation-options", app)
        try require(options.waitForExistence(timeout: 10), "The actual table-style picker must open.")
        let identifier = "presentation-choice-godot_\(mode)"
        for _ in 0..<3 where !element(identifier, app).isHittable {
            try require(app.state == .runningForeground && options.exists, "The actual picker must stay open while scrolling.")
            options.swipeUp()
        }
        try await tap(identifier, app)
        try await wait("The selected shipping table must complete its native Ready handoff.", timeout: 60) {
            self.nativeReady(app)
        }
        try noObservation(app)
        try require(!element("game-table", app).exists && !element("presentation-options", app).exists,
                    "Native entry must leave the shared game surface and picker.")
    }

    @MainActor
    private func nativeLeaveDialog(_ app: XCUIApplication) async throws {
        try require(nativeReady(app), "The native toolbar must be ready immediately before native Leave.")
        // Deliberately never use navigation-back or godot-standard-table in this flow.
        try await tap("godot-leave-table", app)
        try await wait("Native Leave must dismiss its surface before exposing shared confirm and cancel.") {
            self.nativeDismissed(app) && !self.element("home-practice", app).exists &&
                self.hittableControl("leave-confirm", app) && self.hittableControl("leave-cancel", app)
        }
        try noObservation(app)
    }

    @MainActor
    private func nativeReady(_ app: XCUIApplication) -> Bool {
        let status = element("godot-session-status", app)
        return app.state == .runningForeground && element("godot-session-table", app).exists &&
            status.exists && status.label == "Your table is ready" &&
            !element("godot-session-privacy-cover", app).exists &&
            hittableControl("godot-standard-table", app) && hittableControl("godot-leave-table", app) &&
            element("godot-standard-table", app).elementType == .button && element("godot-leave-table", app).elementType == .button
        // The inaccessible inner cover's pixels still require independent review.
    }

    @MainActor
    private func nativeDismissed(_ app: XCUIApplication) -> Bool {
        !element("godot-session-table", app).exists && !element("godot-session-status", app).exists &&
            !element("godot-standard-table", app).exists && !element("godot-leave-table", app).exists
    }

    @MainActor
    private func hittableControl(_ identifier: String, _ app: XCUIApplication) -> Bool {
        let matches = app.descendants(matching: .any).matching(identifier: identifier)
        let target = matches.firstMatch
        return matches.count == 1 && target.exists && target.isEnabled && target.isHittable
    }

    @MainActor
    private func element(_ identifier: String, _ app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    @MainActor
    private func tap(_ identifier: String, _ app: XCUIApplication) async throws {
        try await wait("A required shipping control must be unique, enabled and hittable.") {
            app.state == .runningForeground && self.hittableControl(identifier, app)
        }
        element(identifier, app).tap()
    }

    @MainActor
    private func waitForHumanTurn(_ app: XCUIApplication) async throws {
        let play = element("game-play", app)
        let nextRound = element("game-next-round", app)
        let result = element("game-round-result", app)
        let winner = element("game-winner", app)
        let roundLabel = result.descendants(matching: .any)
            .matching(NSPredicate(format: "label MATCHES %@", "ROUND [0-9]+")).firstMatch
        // The same real-bot bound as the shipping picker test; no seeded or injected session.
        for _ in 0..<4 {
            try await wait("Practice must offer a human turn or an actionable round result.", timeout: 30) {
                play.exists || nextRound.exists || winner.exists
            }
            if play.exists { return }
            try require(!winner.exists && roundLabel.exists,
                        "Practice must offer a human turn before finishing and identify any completed round.")
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

    @MainActor
    private func noObservation(_ app: XCUIApplication) throws {
        try require(!element("partydeck-session-qualification", app).exists,
                    "Shipping Leave must not expose the qualification observation badge.")
    }

    @MainActor
    private func capture(_ name: String, _ app: XCUIApplication) throws {
        let privateCards = app.descendants(matching: .any)
            .matching(NSPredicate(format: "identifier BEGINSWITH %@", "game-card-"))
        try require(app.state == .runningForeground && !element("invitation-dialog", app).exists && privateCards.count == 0,
                    "Shipping captures require foreground, concealed Standard cards and no invitation.")
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
