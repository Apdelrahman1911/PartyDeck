import XCTest

final class ProbeHostUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testRealScenePauseResumeInputExitAndReopenRefusal() async throws {
        let app = try await launchScene()
        XCTAssertEqual(number("bootstrapCount", app), 1)
        XCTAssertEqual(number("readyEvents", app), 1)
        XCTAssertGreaterThanOrEqual(number("rejectedEvents", app), 2, "The real GDScript scene exercises duplicate-key and replay rejection.")
        XCTAssertEqual(metrics(app)["renderingLayerClass"] as? String, "GDTOpenGLLayer")
        capture("Diagnostic rendering", app)

        element("pause-scene", app).tap()
        try await waitUntil("Pause must stop the render loop and cover the old frame.") {
            self.metrics(app)["state"] as? String == "paused" &&
            self.flag("privacyCoverVisible", app) && !self.flag("renderLoopActive", app)
        }
        let pausedIterations = number("iterations", app)
        try await Task.sleep(nanoseconds: 600_000_000)
        XCTAssertEqual(number("iterations", app), pausedIterations)
        capture("Diagnostic paused and covered", app)

        element("pause-scene", app).tap()
        try await waitUntil("Resume must produce a fresh frame before uncovering.") {
            self.number("iterations", app) > pausedIterations + 2 &&
            !self.flag("privacyCoverVisible", app)
        }
        let backgroundTransitions = number("backgroundTransitions", app)
        XCUIDevice.shared.press(.home)
        XCTAssertTrue(app.wait(for: .runningBackground, timeout: 10))
        app.activate()
        try await waitUntil("Application lifecycle must reach Godot's pause/resume path.") {
            self.number("backgroundTransitions", app) > backgroundTransitions &&
            self.metrics(app)["state"] as? String == "running" &&
            !self.flag("privacyCoverVisible", app)
        }
        capture("Diagnostic resumed", app)

        // This coordinate lands on the real Godot Button; no native command
        // substitutes for the touch -> Godot input -> GDScript -> bridge path.
        let surface = element("godot-surface", app)
        XCTAssertTrue(surface.isHittable)
        surface.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.51)).tap()
        try await assertClosed(app, expectedExitEvents: 1)
        element("try-reopen", app).tap()
        try await waitUntil("A second engine must be refused without a second bootstrap.") {
            self.flag("reopenDenied", app)
        }
        XCTAssertEqual(number("bootstrapCount", app), 1)
        capture("Diagnostic closed and reopen refused", app)
    }

    @MainActor
    func testCloseInsideActualDrawRunLoopDefersCleanup() async throws {
        let app = try await launchScene()
        element("close-during-draw", app).tap()
        try await assertClosed(app, expectedExitEvents: 0)
        XCTAssertEqual(number("closeRequestedDuringDraw", app), 1)
        XCTAssertEqual(number("cleanupDepth", app), 0, "Cleanup must run after the outer draw returns.")
        capture("Close requested inside draw", app)
    }

    @MainActor
    func testImmediateForegroundLossAndResumeRestartsDrawing() async throws {
        let app = try await launchScene()
        let before = number("iterations", app)
        let covers = number("privacyCoverCount", app)
        let losses = number("backgroundTransitions", app)
        element("cycle-focus", app).tap()
        try await waitUntil("A coalesced false/true pair must preserve concealment and restart drawing.") {
            self.number("backgroundTransitions", app) == losses + 1 &&
            self.number("privacyCoverCount", app) == covers + 1 &&
            self.number("iterations", app) > before + 2 &&
            !self.flag("privacyCoverVisible", app)
        }
        element("close-scene", app).tap()
        try await assertClosed(app, expectedExitEvents: 0)
        capture("Immediate focus loss and resume", app)
    }

    @MainActor
    func testCloseBeforePresentationDoesNotConstructEngine() async throws {
        let app = XCUIApplication()
        app.launchArguments = ["--close-before-start"]
        app.launch()
        element("start-scene", app).tap()
        try await waitUntil("A cancelled presentation must close without bootstrapping.") {
            self.metrics(app)["state"] as? String == "closed"
        }
        XCTAssertEqual(number("bootstrapCount", app), 0)
        XCTAssertEqual(number("cleanupCount", app), 0)
        XCTAssertEqual(number("iterations", app), 0)
        XCTAssertFalse(flag("osSingletonPresent", app))
        element("host-counter-button", app).tap()
        XCTAssertEqual(number("hostCounter", app), 1)
        capture("Closed before engine construction", app)
    }

    @MainActor
    func testCloseDuringInitializationUsesCheckedCleanupBoundary() async throws {
        let app = XCUIApplication()
        app.launchArguments = ["--close-during-initialization"]
        app.launch()
        element("start-scene", app).tap()
        try await assertClosed(app, expectedExitEvents: 0)
        XCTAssertTrue(flag("setup2Succeeded", app))
        XCTAssertEqual(number("closeRequestedDuringInitialization", app), 1)
        XCTAssertEqual(number("readyEvents", app), 0)
        XCTAssertEqual(number("iterations", app), 0)
        capture("Closed during checked initialization", app)
    }

    @MainActor
    private func launchScene() async throws -> XCUIApplication {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(element("start-scene", app).waitForExistence(timeout: 15))
        element("start-scene", app).tap()
        try await waitUntil("A real Godot scene must emit Ready and execute iterations.", timeout: 45) {
            self.number("readyEvents", app) == 1 &&
            self.number("iterations", app) >= 3 &&
            self.flag("renderLoopActive", app)
        }
        return app
    }

    @MainActor
    private func assertClosed(_ app: XCUIApplication, expectedExitEvents: Int) async throws {
        try await waitUntil("Close must destroy the OS singleton, stop iteration, and release the native view.", timeout: 30) {
            self.metrics(app)["state"] as? String == "closed" &&
            self.flag("viewReleased", app) && self.flag("controllerReleased", app)
        }
        XCTAssertEqual(number("cleanupCount", app), 1)
        XCTAssertEqual(number("cleanupDepth", app), 0)
        XCTAssertEqual(number("exitEvents", app), expectedExitEvents)
        XCTAssertFalse(flag("osSingletonPresent", app))
        XCTAssertFalse(flag("bridgeRegistered", app))
        XCTAssertFalse(flag("renderLoopActive", app))
        XCTAssertFalse(flag("quarantined", app))
        XCTAssertEqual(number("queuedCommands", app), 0)
        XCTAssertEqual(number("queuedEvents", app), 0)
        let finalIterations = number("iterations", app)
        let hostCounter = number("hostCounter", app)
        element("host-counter-button", app).tap()
        XCTAssertEqual(number("hostCounter", app), hostCounter + 1)
        try await Task.sleep(nanoseconds: 600_000_000)
        XCTAssertEqual(number("iterations", app), finalIterations)
    }

    @MainActor
    private func element(_ identifier: String, _ app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    @MainActor
    private func metrics(_ app: XCUIApplication) -> [String: Any] {
        guard let document = element("probe-metrics", app).value as? String,
              let bytes = document.data(using: .utf8),
              let result = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any] else {
            return [:]
        }
        return result
    }

    @MainActor
    private func number(_ name: String, _ app: XCUIApplication) -> Int {
        (metrics(app)[name] as? NSNumber)?.intValue ?? -1
    }

    @MainActor
    private func flag(_ name: String, _ app: XCUIApplication) -> Bool {
        (metrics(app)[name] as? NSNumber)?.boolValue ?? false
    }

    @MainActor
    private func waitUntil(_ message: String, timeout: TimeInterval = 15, condition: @MainActor () -> Bool) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline {
            try await Task.sleep(nanoseconds: 150_000_000)
        }
        XCTAssertTrue(condition(), message)
    }

    @MainActor
    private func capture(_ name: String, _ app: XCUIApplication) {
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = name
        screenshot.lifetime = .keepAlways
        add(screenshot)
        if let data = try? JSONSerialization.data(withJSONObject: metrics(app), options: [.prettyPrinted, .sortedKeys]) {
            let receipt = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
            receipt.name = "\(name) measurements"
            receipt.lifetime = .keepAlways
            add(receipt)
        }
    }
}
