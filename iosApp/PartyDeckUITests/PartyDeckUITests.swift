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

        let standard = StandardTableAcceptance(app)
        try standard.exerciseFiveCardHand { checkpoint in
            capture("Practice Standard \(checkpoint)", app: app)
            try standard.audit()
        }
        _ = try standard.reveal(count: 5)
        try standard.toggle(index: 0, count: 5, selected: true)
        let lastCard = element("game-card-4", in: app)
        let play = try standard.control("game-play")
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
        waitUntil("The entered host name must reach the native field value before hosting.") {
            (name.value as? String) == "Native Host"
        }
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

/// Native labels, values and element actions, shared by ordinary and observed production tests.
/// These checks do not claim VoiceOver speech, focus order or assistive-technology traversal.
@MainActor
struct StandardTableAcceptance {
    let app: XCUIApplication
    init(_ app: XCUIApplication) { self.app = app }

    private let limitMessage = "Choose up to 3 cards."
    private var cards: XCUIElementQuery {
        app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH %@", "game-card-"))
    }
    private func element(_ identifier: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }
    private func text(_ label: String) -> XCUIElementQuery {
        app.descendants(matching: .any).matching(NSPredicate(format: "label == %@", label))
    }

    func exerciseFiveCardHand(checkpoint: (String) throws -> Void = { _ in }) throws {
        try concealed()
        try checkpoint("concealed")
        let labels = try reveal(count: 5)
        try checkpoint("all five native card descriptions")

        // The fifth card must be reached and activated, including a scrolling hand.
        try toggle(index: 4, count: 5, selected: true)
        try wait("Selecting the fifth card must enable Play.") { element("game-play").isEnabled }
        try toggle(index: 4, count: 5, selected: false)
        try wait("Deselecting the fifth card must disable Play.") { !element("game-play").isEnabled }
        for index in 0..<3 { try toggle(index: index, count: 5, selected: true) }
        try card(index: 3, count: 5).tap()
        try wait("A fourth choice must expose the count-only selection limit.") { text(limitMessage).count == 1 }
        let feedback = try reach(text(limitMessage).firstMatch)
        if let value = feedback.value {
            try require((value as? String).map { $0.isEmpty || $0 == limitMessage } == true,
                        "Selection-limit feedback must not add private card information.")
        }
        for index in 0..<5 {
            try state(index: index, count: 5, selected: index < 3, expectedLabel: labels[index])
        }
        try require(text("3 of 3 selected").count == 1 && element("game-play").isEnabled,
                    "Rejecting a fourth card must retain exactly the first three selections.")
        try checkpoint("maximum selection and count-only feedback")

        try toggle(index: 1, count: 5, selected: false)
        try wait("Deselecting must clear the limit feedback and update the public count.") {
            text(limitMessage).count == 0 && text("2 of 3 selected").count == 1
        }
        for index in 0..<5 {
            try state(index: index, count: 5, selected: index == 0 || index == 2, expectedLabel: labels[index])
        }
        try hide(labels: labels)
        try checkpoint("Hide removes private nodes and selection")
        _ = try reveal(count: 5, expectedLabels: labels)
        try checkpoint("fresh Reveal is unselected")
        try hide(labels: labels)
    }

    @discardableResult
    func reveal(count: Int, expectedLabels: [String]? = nil) throws -> [String] {
        try require((1...5).contains(count), "A live Standard hand must have its observed card count.")
        try require(expectedLabels == nil || expectedLabels?.count == count, "The saved hand description count must match this reveal.")
        try concealed()
        try control("game-reveal-hand").tap()
        var labels: [String] = []
        for index in 0..<count {
            try state(index: index, count: count, selected: false, expectedLabel: expectedLabels?[index])
            labels.append(element("game-card-\(index)").label)
        }
        try require(!element("game-play").isEnabled && text(limitMessage).count == 0,
                    "A fresh Reveal must have neither a selection nor old limit feedback.")
        return labels
    }

    func toggle(index: Int, count: Int, selected: Bool) throws {
        try state(index: index, count: count, selected: !selected)
        let target = try card(index: index, count: count)
        let label = target.label
        target.tap()
        try state(index: index, count: count, selected: selected, expectedLabel: label)
    }

    func concealed() throws {
        try wait("The concealed Standard hand must expose no private card nodes.") {
            element("game-reveal-hand").exists && cards.count == 0
        }
        try require(element("game-play").exists && !element("game-play").isEnabled && text(limitMessage).count == 0,
                    "A concealed playable hand must have no retained selection or limit feedback.")
    }

    private func hide(labels: [String]) throws {
        try control("game-hide-hand").tap()
        try concealed()
        try require(labels.allSatisfy { label in
            app.descendants(matching: .any).matching(NSPredicate(format: "label == %@ OR value == %@", label, label)).count == 0
        },
                    "Hide must remove every previously exposed private card description, including untagged copies.")
    }

    private func state(index: Int, count: Int, selected: Bool, expectedLabel: String? = nil) throws {
        let target = try card(index: index, count: count)
        let state = selected ? "Selected" : "Not selected"
        try wait("Each card must expose the matching native selected trait and explicit state value.") {
            target.isSelected == selected && (target.value as? String) == state
        }
        let allowedLabels = ["Crown", "Moon", "Star", "Wild"].map { "\($0). Card \(index + 1) of \(count)." }
        try require(allowedLabels.contains(target.label) && (expectedLabel == nil || target.label == expectedLabel),
                    "Each native card label must contain its full rank, position and count and remain stable while toggled.")
    }

    private func card(index: Int, count: Int) throws -> XCUIElement {
        let matches = app.descendants(matching: .any).matching(identifier: "game-card-\(index)")
        let target = try reach(matches.firstMatch, cardIndex: index, cardCount: count)
        try require(matches.count == 1 && target.elementType == .button,
                    "Each reached card must be one native button with its exact card identifier.")
        try require(app.buttons.matching(NSPredicate(format: "label == %@", target.label)).count == 1,
                    "Each reached card must expose one exact description on its native button.")
        return target
    }

    func control(_ identifier: String) throws -> XCUIElement { try reach(element(identifier)) }

    private func reach(_ target: XCUIElement, cardIndex: Int? = nil, cardCount: Int = 0) throws -> XCUIElement {
        let table = element("game-table")
        let hand = element("game-hand")
        for _ in 0..<12 {
            try require(app.state == .runningForeground, "Standard controls require the actual foreground app.")
            // Compose may adjust accessibility bounds. This checks native onscreen/hittable
            // geometry, not complete visual unclipping or assistive-technology traversal.
            if target.exists && target.isEnabled && target.isHittable &&
                target.frame.width > 0 && target.frame.height > 0 && app.frame.contains(target.frame) { return target }
            let surface = table.exists ? table : app
            if target.exists && target.frame.height > 0 && target.frame.minY < app.frame.minY {
                surface.swipeDown()
            } else if target.exists && target.frame.height > 0 && target.frame.maxY > app.frame.maxY {
                surface.swipeUp()
            } else if cardIndex != nil && hand.exists && target.exists && target.frame.width > 0 && target.frame.minX < app.frame.minX {
                hand.swipeRight()
            } else if cardIndex != nil && hand.exists && target.exists && target.frame.width > 0 && target.frame.maxX > app.frame.maxX {
                hand.swipeLeft()
            } else if let index = cardIndex, hand.exists {
                let visible = (0..<cardCount).filter { element("game-card-\($0)").isHittable }
                if let first = visible.first, index < first { hand.swipeRight() }
                else if !visible.isEmpty { hand.swipeLeft() }
                else { surface.swipeUp() }
            } else {
                surface.swipeUp()
            }
        }
        throw Failure("A required Standard control did not expose onscreen, hittable native accessibility geometry after bounded scrolling.")
    }

    func audit() throws {
        try require(element("game-table").exists && !element("godot-standard-table").exists &&
            !element("partydeck-session-qualification").exists,
            "Audit the ordinary native Standard route without a Godot surface or test-only observation badge.")
        if #available(iOS 17.0, *) {
            // No issue handler or audit-type exclusions: every reported Standard issue fails.
            try app.performAccessibilityAudit(for: .all)
        } else {
            throw Failure("Native accessibility acceptance requires the supported iOS 17+ audit runner.")
        }
    }

    private func wait(_ message: String, condition: @escaping () -> Bool) throws {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in condition() }, object: nil)
        try require(XCTWaiter.wait(for: [expectation], timeout: 10) == .completed, message)
    }
    private func require(_ condition: Bool, _ message: String) throws { if !condition { throw Failure(message) } }
    private struct Failure: Error, CustomStringConvertible {
        let description: String
        init(_ description: String) { self.description = description }
    }
}
