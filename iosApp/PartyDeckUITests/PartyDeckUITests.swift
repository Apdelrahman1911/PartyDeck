import XCTest

final class PartyDeckUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testSharedHomeOpensAPlayablePracticeTable() throws {
        let app = XCUIApplication()
        app.launch()

        let practice = element("home-practice", in: app)
        XCTAssertTrue(practice.waitForExistence(timeout: 30), "The shared Compose home must render.")
        XCTAssertTrue(element("home-host", in: app).exists)
        XCTAssertTrue(element("home-join", in: app).exists)
        capture("Home", app: app)

        practice.tap()
        XCTAssertTrue(element("game-table", in: app).waitForExistence(timeout: 15), "Practice must reach the actual game UI.")
        waitForPlayableTurn(in: app)

        let reveal = element("game-reveal-hand", in: app)
        let firstCard = element("game-card-0", in: app)
        let lastCard = element("game-card-4", in: app)
        let privateCards = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH %@", "game-card-"))
        let play = element("game-play", in: app)
        XCTAssertTrue(reveal.waitForExistence(timeout: 10))
        XCTAssertEqual(privateCards.count, 0, "A concealed hand must not expose any card elements to accessibility.")
        XCTAssertFalse(play.isEnabled, "A play requires an explicit card selection.")
        capture("Practice concealed", app: app)

        reveal.tap()
        XCTAssertTrue(firstCard.waitForExistence(timeout: 10))
        XCTAssertTrue(lastCard.exists, "A new round deals five cards to the human player.")
        firstCard.tap()
        waitUntil("Selecting a card must enable Play.") { play.isEnabled }
        capture("Practice selected", app: app)

        element("game-hide-hand", in: app).tap()
        waitUntil("Hiding the hand must remove every private card element.") { reveal.exists && privateCards.count == 0 }
        XCTAssertFalse(play.isEnabled, "Hiding a hand clears the pending card selection.")
        capture("Practice hidden after selection", app: app)

        reveal.tap()
        XCTAssertTrue(firstCard.waitForExistence(timeout: 10))
        firstCard.tap()
        waitUntil("The revealed hand must allow a new selection.") { play.isEnabled }
        play.tap()
        let fourthCard = element("game-card-3", in: app)
        let roundResult = element("game-round-result", in: app)
        let winner = element("game-winner", in: app)
        waitUntil("Playing one card must change the authoritative hand or produce a round outcome.") {
            !lastCard.exists && (fourthCard.exists || roundResult.exists || winner.exists)
        }
        capture("Practice after accepted play", app: app)
        leaveTable(in: app)
    }

    @MainActor
    func testSharedControllerHostsANativeTableAndShowsItsInvitation() throws {
        let app = XCUIApplication()
        app.launch()

        let host = element("home-host", in: app)
        XCTAssertTrue(host.waitForExistence(timeout: 30))
        host.tap()
        let name = element("host-name", in: app)
        XCTAssertTrue(name.waitForExistence(timeout: 10))
        name.tap()
        let existingName = name.value as? String ?? ""
        if !existingName.isEmpty {
            name.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: existingName.count))
        }
        name.typeText("Native Host")
        XCTAssertEqual(name.value as? String, "Native Host", "The host name must replace the previous field value.")
        let create = element("host-create", in: app)
        for _ in 0..<3 where !create.isHittable { app.swipeUp() }
        XCTAssertTrue(create.isHittable, "Host creation must remain reachable above the keyboard.")
        XCTAssertTrue(create.isEnabled)
        create.tap()

        let invitation = element("lobby-invitation", in: app)
        XCTAssertTrue(invitation.waitForExistence(timeout: 20), "The shared controller must create a real native host and publish its invitation.")
        XCTAssertTrue(app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", "Native Host")).firstMatch.exists,
                      "The host roster must show the entered name.")
        capture("Native host lobby", app: app)
        invitation.tap()
        let dialog = element("invitation-dialog", in: app)
        XCTAssertTrue(dialog.waitForExistence(timeout: 10))
        XCTAssertTrue(element("invitation-qr", in: app).waitForExistence(timeout: 10))
        let copy = element("invitation-copy", in: app)
        for _ in 0..<3 where !copy.isHittable { dialog.swipeUp() }
        XCTAssertTrue(element("invitation-share", in: app).exists)
        XCTAssertTrue(copy.isHittable, "Invitation actions must be reachable by scrolling the dialog.")
        element("invitation-done", in: app).tap()
        waitUntil("The invitation dialog must close before leaving the table.") { !dialog.exists }
        capture("Native host invitation closed", app: app)
        leaveTable(in: app)
        XCTAssertFalse(invitation.exists, "Leaving must remove the retained hosting session from the UI.")
    }

    @MainActor
    func testNativeHostCanNavigateSharedSettings() throws {
        let app = XCUIApplication()
        app.launch()

        let settings = element("home-settings", in: app)
        XCTAssertTrue(settings.waitForExistence(timeout: 30))
        settings.tap()
        XCTAssertTrue(element("settings-sound", in: app).waitForExistence(timeout: 10))
        XCTAssertTrue(element("settings-haptics", in: app).exists)
        XCTAssertTrue(element("settings-reduce-motion", in: app).exists)
        capture("Settings", app: app)

        let back = element("navigation-back", in: app)
        XCTAssertTrue(back.exists)
        back.tap()
        XCTAssertTrue(element("home-practice", in: app).waitForExistence(timeout: 10))
    }

    @MainActor
    private func element(_ identifier: String, in app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    @MainActor
    private func waitForPlayableTurn(in app: XCUIApplication) {
        let play = element("game-play", in: app)
        let nextRound = element("game-next-round", in: app)
        let result = element("game-round-result", in: app)
        let roundLabel = result.descendants(matching: .any).matching(NSPredicate(format: "label MATCHES %@", "ROUND [0-9]+")).firstMatch
        let winner = element("game-winner", in: app)
        // The opening seat is random. Bots can end a round before the human acts;
        // advancing rotates the opener through the surviving seats. The human
        // cannot be penalized before acting, and the last bot cannot end a round
        // without a human action, so a winner here would violate those rules.
        for _ in 0..<4 {
            waitUntil("Practice must reach a human turn or an actionable round result.") { play.exists || nextRound.exists || winner.exists }
            if play.exists { return }
            if winner.exists {
                XCTFail("Practice must offer a human turn before the match can finish.")
                return
            }
            XCTAssertTrue(roundLabel.exists, "A round result must identify the completed round.")
            let completedRound = roundLabel.label
            for _ in 0..<3 where !nextRound.isHittable { result.swipeUp() }
            XCTAssertTrue(nextRound.isHittable)
            XCTAssertTrue(nextRound.isEnabled)
            nextRound.tap()
            waitUntil("Advancing must leave the previous round result before another advance.") {
                play.exists || winner.exists || (nextRound.exists && roundLabel.exists && roundLabel.label != completedRound)
            }
        }
        XCTFail("Practice did not offer the human player a playable turn within four rounds.")
    }

    @MainActor
    private func leaveTable(in app: XCUIApplication) {
        let back = element("navigation-back", in: app)
        XCTAssertTrue(back.waitForExistence(timeout: 10))
        back.tap()
        let confirm = element("leave-confirm", in: app)
        XCTAssertTrue(confirm.waitForExistence(timeout: 10), "Leaving a live table requires confirmation.")
        XCTAssertTrue(element("leave-cancel", in: app).exists)
        confirm.tap()
        XCTAssertTrue(element("home-practice", in: app).waitForExistence(timeout: 10))
        XCTAssertFalse(element("game-table", in: app).exists)
    }

    @MainActor
    private func waitUntil(_ message: String, condition: @escaping () -> Bool) {
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in condition() }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 10), .completed, message)
    }

    @MainActor
    private func capture(_ name: String, app: XCUIApplication) {
        // A live invitation is a bearer credential. Do not retain its QR or URI.
        guard !element("invitation-dialog", in: app).exists else { return }
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
