import XCTest

final class AuthorityHostUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testReferenceMatchIn2D() async throws {
        try await referenceMatch(mode: "2d", textScale: 1)
    }

    @MainActor
    func testReferenceMatchIn3D() async throws {
        try await referenceMatch(mode: "3d", textScale: 1)
    }

    @MainActor
    func testReferenceMatchIn2DAt200Percent() async throws {
        try await referenceMatch(mode: "2d", textScale: 2)
    }

    @MainActor
    func testReferenceMatchIn3DAt200Percent() async throws {
        try await referenceMatch(mode: "3d", textScale: 2)
    }

    @MainActor
    func testSecureTableRendererExit() async throws {
        let app = try await launch(mode: "2d", textScale: 1, reference: false)
        let before = try await currentDiagnostics(app)
        XCTAssertFalse(flag("referenceSeed2", before))
        _ = try await tapControl("exit", app)
        let closed = try await assertClosed(app, reason: "EXIT_REQUESTED")
        XCTAssertEqual(number("acceptedViewerPlays", closed), number("acceptedViewerPlays", before))
        XCTAssertEqual(number("acceptedViewerChallenges", closed), number("acceptedViewerChallenges", before))
        XCTAssertEqual(number("roundsAdvanced", closed), number("roundsAdvanced", before))
        XCTAssertEqual(number("exitEvents", native(closed)), 1)
        capture("Secure default table exited through Godot input", app)
    }

    @MainActor
    private func referenceMatch(mode: String, textScale: Int) async throws {
        let app = try await launch(mode: mode, textScale: textScale, reference: true)
        var value = try await currentDiagnostics(app)
        XCTAssertEqual(value["mode"] as? String, mode)
        XCTAssertEqual(number("textScale", value), textScale)
        XCTAssertTrue(flag("referenceSeed2", value))
        try require(concealed(value), "The initial real hand must be concealed.")
        capture("01 concealed \(mode) text \(textScale)", app)

        try await revealAndSelect(app)
        capture("02 revealed and selected \(mode) text \(textScale)", app)
        let beforeHide = try await tapControl("hide", app)
        value = try await currentDiagnostics(app, after: beforeHide) { self.concealed($0) }
        assertLocalOnly(beforeHide, value)
        capture("03 private bindings cleared \(mode) text \(textScale)", app)
        try await pauseAndBackground(app)

        try await revealAndSelect(app)
        value = try await submit("play", counter: "acceptedViewerPlays", app)
        capture("04 actual viewer play \(mode) text \(textScale)", app)
        var capturedOutcome = false
        var capturedChallenge = false
        for _ in 0..<64 {
            let phase = value["phase"] as? String ?? ""
            if phase == "ROUND_ENDED" || phase == "FINISHED" {
                try require(concealed(value), "A real outcome must clear private cards and selection.")
                if !capturedOutcome {
                    capture("05 public outcome \(mode) text \(textScale)", app)
                    capturedOutcome = true
                }
            }
            if phase == "FINISHED" {
                XCTAssertEqual(number("roundNumber", value), 14)
                XCTAssertEqual(value["revision"] as? String, "41")
                XCTAssertEqual(number("acceptedViewerPlays", value), 2)
                XCTAssertEqual(number("acceptedViewerChallenges", value), 2)
                XCTAssertEqual(number("roundsAdvanced", value), 13)
                try require(!(value["winnerId"] as? String ?? "").isEmpty, "The real authority must identify its winner.")
                capture("07 real winner \(mode) text \(textScale)", app)
                _ = try await tapControl("lobby", app)
                if mode == "2d" {
                    _ = try await currentDiagnostics(app) {
                        self.control("lobby_confirm", in: $0).map { self.flag("visible", $0) } ?? false
                    }
                    capture("08 return confirmation \(mode) text \(textScale)", app)
                    _ = try await tapControl("lobby_confirm", app)
                }
                let closed = try await assertClosed(app, reason: "RETURN_TO_LOBBY")
                XCTAssertEqual(number("acceptedViewerPlays", closed), 2)
                XCTAssertEqual(number("acceptedViewerChallenges", closed), 2)
                XCTAssertEqual(number("roundsAdvanced", closed), 13)
                capture("09 table returned through authority \(mode) text \(textScale)", app)
                return
            }
            if phase == "ROUND_ENDED" {
                let priorRound = number("roundNumber", value)
                value = try await submit("next_round", counter: "roundsAdvanced", app)
                XCTAssertEqual(number("roundNumber", value), priorRound + 1)
            } else if control("challenge", in: value).map({ flag("enabled", $0) }) == true {
                value = try await submit("challenge", counter: "acceptedViewerChallenges", app)
                if !capturedChallenge {
                    capture("06 actual viewer challenge \(mode) text \(textScale)", app)
                    capturedChallenge = true
                }
            } else {
                try require(phase == "PLAYING", "The authority reported an unsupported phase.")
                try await revealAndSelect(app)
                value = try await submit("play", counter: "acceptedViewerPlays", app)
            }
        }
        throw Failure.matchActionBound
    }

    @MainActor
    private func launch(mode: String, textScale: Int, reference: Bool) async throws -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--text-scale=\(textScale)"]
        if reference { app.launchArguments.append("--reference-seed=2") }
        app.launch()
        try require(element("start-\(mode)", app).waitForExistence(timeout: 15), "The native table chooser must appear.")
        element("start-\(mode)", app).tap()
        let value = try await currentDiagnostics(app, timeout: 60)
        XCTAssertEqual(value["lifecycle"] as? String, "READY")
        XCTAssertEqual(number("readyEvents", native(value)), 1)
        XCTAssertEqual(number("bootstrapCount", native(value)), 1)
        XCTAssertGreaterThanOrEqual(number("iterations", native(value)), 3)
        XCTAssertFalse(flag("authorityReleased", value))
        try validateGeometry(value, app)
        return app
    }

    @MainActor
    private func revealAndSelect(_ app: XCUIApplication) async throws {
        let beforeReveal = try await tapControl("reveal", app)
        let revealed = try await currentDiagnostics(app, after: beforeReveal) {
            let diagnostic = self.diagnostics($0)
            return !self.flag("handConcealed", diagnostic) && self.number("privateFaceCount", diagnostic) > 0 &&
                self.number("privateLabelCount", diagnostic) > 0
        }
        assertLocalOnly(beforeReveal, revealed)
        let beforeSelect = try await tapControl("card", app, cardIndex: 0)
        let selected = try await currentDiagnostics(app, after: beforeSelect) {
            self.number("selectedCount", self.diagnostics($0)) == 1 &&
                self.control("card", in: $0, cardIndex: 0).map { self.flag("selected", $0) } == true
        }
        assertLocalOnly(beforeSelect, selected)
    }

    @MainActor
    private func pauseAndBackground(_ app: XCUIApplication) async throws {
        try await revealAndSelect(app)
        let before = try await currentDiagnostics(app)
        element("pause-table", app).tap()
        let paused = try await currentDiagnostics(app, after: before, foreground: false) {
            $0["state"] as? String == "paused" && self.flag("privacyCoverVisible", self.native($0)) &&
                !self.flag("renderLoopActive", self.native($0)) && self.concealed($0)
        }
        assertLocalOnly(before, paused)
        let pausedIterations = number("iterations", native(paused))
        try await Task.sleep(nanoseconds: 600_000_000)
        XCTAssertEqual(number("iterations", native(metrics(app))), pausedIterations)
        capture("Native cover with paused private bindings cleared", app)
        element("pause-table", app).tap()
        let resumed = try await currentDiagnostics(app, after: paused) { self.concealed($0) }
        assertLocalOnly(paused, resumed)

        try await revealAndSelect(app)
        let beforeHome = try await currentDiagnostics(app)
        XCUIDevice.shared.press(.home)
        try require(app.wait(for: .runningBackground, timeout: 10), "The real application must enter the background.")
        let home = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        home.name = "Actual home screen while game is backgrounded"
        home.lifetime = .keepAlways
        add(home)
        app.activate()
        let returned = try await currentDiagnostics(app, after: beforeHome) {
            self.concealed($0) && self.number("backgroundTransitions", self.native($0)) > self.number("backgroundTransitions", self.native(beforeHome)) &&
                self.number("privacyCoverCount", self.native($0)) > self.number("privacyCoverCount", self.native(beforeHome))
        }
        assertLocalOnly(beforeHome, returned)
        XCTAssertEqual(number("bootstrapCount", native(returned)), 1)
        capture("Same authority resumed with concealed cards", app)
    }

    @MainActor
    private func submit(_ action: String, counter: String, _ app: XCUIApplication) async throws -> [String: Any] {
        let before = try await tapControl(action, app)
        let after = try await currentDiagnostics(app, after: before) {
            self.number(counter, $0) == self.number(counter, before) + 1 && self.concealed($0)
        }
        XCTAssertEqual(number("acceptedRendererEvents", after), number("acceptedRendererEvents", before) + 1)
        for untouched in ["acceptedViewerPlays", "acceptedViewerChallenges", "roundsAdvanced"] where untouched != counter {
            XCTAssertEqual(number(untouched, after), number(untouched, before))
        }
        XCTAssertNotEqual(after["revision"] as? String, before["revision"] as? String)
        return after
    }

    @MainActor
    private func assertClosed(_ app: XCUIApplication, reason: String) async throws -> [String: Any] {
        let closed = try await waitSnapshot(app, "The authority and native surface must close.", timeout: 30) {
            $0["state"] as? String == "closed" && self.flag("authorityReleased", $0) &&
                self.flag("viewReleased", self.native($0)) && self.flag("controllerReleased", self.native($0))
        }
        XCTAssertEqual(closed["lifecycle"] as? String, "CLOSED")
        XCTAssertEqual(closed["closeReason"] as? String, reason)
        XCTAssertEqual(number("cleanupCount", native(closed)), 1)
        XCTAssertEqual(number("cleanupDepth", native(closed)), 0)
        XCTAssertFalse(flag("osSingletonPresent", native(closed)))
        XCTAssertFalse(flag("bridgeRegistered", native(closed)))
        XCTAssertFalse(flag("renderLoopActive", native(closed)))
        XCTAssertFalse(flag("quarantined", native(closed)))
        XCTAssertTrue(flag("idleTimerPolicyRestored", native(closed)))
        XCTAssertEqual(number("queuedCommands", native(closed)), 0)
        XCTAssertEqual(number("queuedEvents", native(closed)), 0)
        let iterations = number("iterations", native(closed))
        element("host-counter-button", app).tap()
        _ = try await waitSnapshot(app, "The native shell remains responsive after authority disposal.") {
            self.number("hostCounter", $0) == self.number("hostCounter", closed) + 1
        }
        try await Task.sleep(nanoseconds: 600_000_000)
        XCTAssertEqual(number("iterations", native(metrics(app))), iterations)
        return metrics(app)
    }

    @MainActor
    private func tapControl(_ action: String, _ app: XCUIApplication, cardIndex: Int = -1) async throws -> [String: Any] {
        var value = try await currentDiagnostics(app)
        for _ in 0..<8 {
            try validateGeometry(value, app)
            guard let target = control(action, in: value, cardIndex: cardIndex) else { throw Failure.controlMissing }
            try require(flag("enabled", target), "The actual Godot control must be enabled.")
            let rect = try rectangle(target["rect"])
            let clip = try rectangle(target["clipRect"])
            let viewport = viewportSize(value)
            let bounds = CGRect(origin: .zero, size: viewport)
            try require(bounds.insetBy(dx: -0.5, dy: -0.5).contains(clip), "The reported clip must stay inside the root viewport.")
            let surface = element("godot-surface", app)
            if flag("visible", target), clip.insetBy(dx: -0.5, dy: -0.5).contains(rect) {
                try require(rect.width >= 44 && rect.height >= 44, "The scene touch target must provide at least 44 logical points.")
                let latest = metrics(app)
                try require(latest["revision"] as? String == value["revision"] as? String &&
                    !flag("privacyCoverVisible", native(latest)), "Input must target the current uncovered authority view.")
                guard let latestTarget = control(action, in: latest, cardIndex: cardIndex),
                      NSDictionary(dictionary: target).isEqual(to: latestTarget), viewportSize(latest) == viewport else {
                    value = try await currentDiagnostics(app, after: value)
                    continue
                }
                value = latest
                attachGeometry(action, value: value, target: target)
                surface.coordinate(withNormalizedOffset: CGVector(dx: rect.midX / viewport.width, dy: rect.midY / viewport.height)).tap()
                return value
            }
            try require(clip.width >= 32 && clip.height >= 32 && rect.width <= clip.width + 0.5 && rect.height <= clip.height + 0.5,
                        "The control must fit wholly inside its real scroll viewport.")
            let start: CGPoint
            let end: CGPoint
            if rect.minY < clip.minY {
                start = CGPoint(x: clip.midX, y: clip.minY + clip.height * 0.25)
                end = CGPoint(x: clip.midX, y: clip.minY + clip.height * 0.75)
            } else if rect.maxY > clip.maxY {
                start = CGPoint(x: clip.midX, y: clip.minY + clip.height * 0.75)
                end = CGPoint(x: clip.midX, y: clip.minY + clip.height * 0.25)
            } else if rect.minX < clip.minX {
                start = CGPoint(x: clip.minX + clip.width * 0.25, y: clip.midY)
                end = CGPoint(x: clip.minX + clip.width * 0.75, y: clip.midY)
            } else if rect.maxX > clip.maxX {
                start = CGPoint(x: clip.minX + clip.width * 0.75, y: clip.midY)
                end = CGPoint(x: clip.minX + clip.width * 0.25, y: clip.midY)
            } else {
                throw Failure.controlHidden
            }
            let origin = surface.coordinate(withNormalizedOffset: CGVector(dx: start.x / viewport.width, dy: start.y / viewport.height))
            let destination = surface.coordinate(withNormalizedOffset: CGVector(dx: end.x / viewport.width, dy: end.y / viewport.height))
            origin.press(forDuration: 0.1, thenDragTo: destination)
            value = try await currentDiagnostics(app, after: value)
        }
        throw Failure.scrollBound
    }

    @MainActor
    private func currentDiagnostics(_ app: XCUIApplication, after: [String: Any]? = nil, foreground: Bool = true,
                                    timeout: TimeInterval = 15, predicate: ([String: Any]) -> Bool = { _ in true }) async throws -> [String: Any] {
        try await waitSnapshot(app, "The real renderer must report current bounded diagnostics.", timeout: timeout) { value in
            let diagnostic = self.diagnostics(value)
            let newer = after == nil || self.counter("sequence", diagnostic) > self.counter("sequence", self.diagnostics(after!))
            return value["lifecycle"] as? String == "READY" && !diagnostic.isEmpty && newer &&
                diagnostic["revision"] as? String == value["revision"] as? String &&
                self.flag("foreground", diagnostic) == foreground && self.flag("foreground", value) == foreground &&
                (!foreground || (self.flag("renderLoopActive", self.native(value)) && !self.flag("privacyCoverVisible", self.native(value)) &&
                    self.number("iterations", self.native(value)) >= 3)) && predicate(value)
        }
    }

    @MainActor
    private func waitSnapshot(_ app: XCUIApplication, _ message: String, timeout: TimeInterval = 15,
                              predicate: ([String: Any]) -> Bool) async throws -> [String: Any] {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            let value = metrics(app)
            if value["failureCode"] != nil || native(value)["state"] as? String == "failed" {
                capture("Failed authority runtime", app)
                XCTFail("The native authority owner reported a terminal failure.")
                throw Failure.nativeFailure
            }
            if predicate(value) { return value }
            try await Task.sleep(nanoseconds: 150_000_000)
        }
        capture("Failed authority wait", app)
        XCTFail(message)
        throw Failure.waitTimedOut
    }

    @MainActor
    private func validateGeometry(_ value: [String: Any], _ app: XCUIApplication) throws {
        let viewport = viewportSize(value)
        let surface = element("godot-surface", app)
        let measured = native(value)["surfaceSize"] as? [String: Any] ?? [:]
        try require(surface.isHittable && viewport.width > 0 && viewport.height > 0, "The actual native surface must be visible and measurable.")
        try require(abs(viewport.width - CGFloat(decimal("width", measured))) <= 1 &&
            abs(viewport.height - CGFloat(decimal("height", measured))) <= 1,
                    "Godot logical coordinates must agree with actual UIKit points.")
        try require(abs(surface.frame.width - viewport.width) <= 1 && abs(surface.frame.height - viewport.height) <= 1 &&
            app.frame.insetBy(dx: -0.5, dy: -0.5).contains(surface.frame), "The Godot surface must fit inside the native application.")
        try require(decimal("displayScale", native(value)) >= 0.5, "The native display must report its actual scale.")
    }

    private func rectangle(_ value: Any?) throws -> CGRect {
        guard let parts = value as? [NSNumber], parts.count == 4 else { throw Failure.invalidGeometry }
        return CGRect(x: CGFloat(parts[0].doubleValue), y: CGFloat(parts[1].doubleValue),
                      width: CGFloat(parts[2].doubleValue), height: CGFloat(parts[3].doubleValue))
    }

    private func viewportSize(_ value: [String: Any]) -> CGSize {
        let viewport = diagnostics(value)["viewport"] as? [String: Any] ?? [:]
        return CGSize(width: CGFloat(decimal("width", viewport)), height: CGFloat(decimal("height", viewport)))
    }

    private func control(_ action: String, in value: [String: Any], cardIndex: Int = -1) -> [String: Any]? {
        let group = action == "card" ? "partydeck_hand_card" : "partydeck_action_\(action)"
        return (diagnostics(value)["controls"] as? [[String: Any]])?.first {
            $0["group"] as? String == group && number("cardIndex", $0) == cardIndex
        }
    }

    private func concealed(_ value: [String: Any]) -> Bool {
        let diagnostic = diagnostics(value)
        return flag("handConcealed", diagnostic) && number("selectedCount", diagnostic) == 0 &&
            number("privateFaceCount", diagnostic) == 0 && number("privateLabelCount", diagnostic) == 0
    }

    private func assertLocalOnly(_ before: [String: Any], _ after: [String: Any]) {
        XCTAssertEqual(before["revision"] as? String, after["revision"] as? String)
        for counter in ["acceptedRendererEvents", "acceptedViewerPlays", "acceptedViewerChallenges", "roundsAdvanced", "acceptedOpponentActions"] {
            XCTAssertEqual(number(counter, before), number(counter, after))
        }
    }

    @MainActor
    private func element(_ identifier: String, _ app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    @MainActor
    private func metrics(_ app: XCUIApplication) -> [String: Any] {
        guard let document = element("authority-metrics", app).value as? String,
              let bytes = document.data(using: .utf8),
              let value = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any] else { return [:] }
        return value
    }

    private func native(_ value: [String: Any]) -> [String: Any] { value["native"] as? [String: Any] ?? [:] }
    private func diagnostics(_ value: [String: Any]) -> [String: Any] { native(value)["rendererDiagnostics"] as? [String: Any] ?? [:] }
    private func number(_ name: String, _ value: [String: Any]) -> Int { (value[name] as? NSNumber)?.intValue ?? -1 }
    private func decimal(_ name: String, _ value: [String: Any]) -> Double { (value[name] as? NSNumber)?.doubleValue ?? -1 }
    private func flag(_ name: String, _ value: [String: Any]) -> Bool { (value[name] as? NSNumber)?.boolValue ?? false }
    private func counter(_ name: String, _ value: [String: Any]) -> Int64 { Int64(value[name] as? String ?? "") ?? -1 }

    private func require(_ condition: Bool, _ message: String) throws {
        if !condition {
            XCTFail(message)
            throw Failure.invalidObservation
        }
    }

    @MainActor
    private func capture(_ name: String, _ app: XCUIApplication) {
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = name
        screenshot.lifetime = .keepAlways
        add(screenshot)
        attachJSON(metrics(app), name: "\(name) measurements")
    }

    private func attachGeometry(_ action: String, value: [String: Any], target: [String: Any]) {
        attachJSON(["action": action, "revision": value["revision"] ?? "", "diagnosticSequence": diagnostics(value)["sequence"] ?? "",
                    "viewport": diagnostics(value)["viewport"] ?? [:], "surfaceSize": native(value)["surfaceSize"] ?? [:],
                    "control": target], name: "Actual native touch geometry: \(action)")
    }

    private func attachJSON(_ value: [String: Any], name: String) {
        if let bytes = try? JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]) {
            let attachment = XCTAttachment(data: bytes, uniformTypeIdentifier: "public.json")
            attachment.name = name
            attachment.lifetime = .keepAlways
            add(attachment)
        }
    }

    private enum Failure: Error {
        case waitTimedOut, nativeFailure, matchActionBound, controlMissing, controlHidden, scrollBound, invalidGeometry, invalidObservation
    }
}
