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
        try await waitUntil("Pause must stop the render loop and cover the old frame.", app: app) {
            self.metrics(app)["state"] as? String == "paused" &&
            self.flag("privacyCoverVisible", app) && !self.flag("renderLoopActive", app)
        }
        let pausedIterations = number("iterations", app)
        try await Task.sleep(nanoseconds: 600_000_000)
        XCTAssertEqual(number("iterations", app), pausedIterations)
        capture("Diagnostic paused and covered", app)

        element("pause-scene", app).tap()
        try await waitUntil("Resume must produce a fresh frame before uncovering.", app: app) {
            self.number("iterations", app) > pausedIterations + 2 &&
            !self.flag("privacyCoverVisible", app)
        }
        let backgroundTransitions = number("backgroundTransitions", app)
        XCUIDevice.shared.press(.home)
        XCTAssertTrue(app.wait(for: .runningBackground, timeout: 10))
        app.activate()
        try await waitUntil("Application lifecycle must reach Godot's pause/resume path.", app: app) {
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
        try await waitUntil("A second engine must be refused without a second bootstrap.", app: app) {
            self.flag("reopenDenied", app)
        }
        XCTAssertEqual(number("bootstrapCount", app), 1)
        capture("Diagnostic closed and reopen refused", app)
    }

    @MainActor
    func testCloseInsideActualDrawRunLoopDefersCleanup() async throws {
        let app = try await launchScene(initialIdleTimerDisabled: true)
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
        try await waitUntil("A coalesced false/true pair must preserve concealment and restart drawing.", app: app) {
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
        app.launchArguments = ["--close-before-start", "--host-idle-timer=on"]
        app.launch()
        element("start-scene", app).tap()
        try await waitUntil("A cancelled presentation must close without bootstrapping.", app: app) {
            self.metrics(app)["state"] as? String == "closed"
        }
        XCTAssertEqual(number("bootstrapCount", app), 0)
        XCTAssertEqual(number("cleanupCount", app), 0)
        XCTAssertEqual(number("iterations", app), 0)
        XCTAssertEqual(number("bootstrapExitCode", app), -1)
        XCTAssertEqual(number("setup2ErrorCode", app), -1)
        XCTAssertEqual(number("mainStartExitCode", app), -1)
        XCTAssertFalse(flag("osSingletonPresent", app))
        XCTAssertTrue(flag("previousIdleTimerDisabled", app))
        assertIdleTimerRestored(app)
        element("host-counter-button", app).tap()
        XCTAssertEqual(number("hostCounter", app), 1)
        capture("Closed before engine construction", app)
    }

    @MainActor
    func testCloseDuringInitializationUsesCheckedCleanupBoundary() async throws {
        let app = XCUIApplication()
        app.launchArguments = ["--close-during-initialization", "--host-idle-timer=off"]
        app.launch()
        element("start-scene", app).tap()
        try await assertClosed(app, expectedExitEvents: 0)
        XCTAssertTrue(flag("setup2Succeeded", app))
        XCTAssertEqual(number("bootstrapExitCode", app), 0)
        XCTAssertEqual(number("setup2ErrorCode", app), 0)
        XCTAssertEqual(number("mainStartExitCode", app), -1)
        XCTAssertEqual(number("closeRequestedDuringInitialization", app), 1)
        XCTAssertEqual(number("readyEvents", app), 0)
        XCTAssertEqual(number("iterations", app), 0)
        XCTAssertFalse(flag("previousIdleTimerDisabled", app))
        XCTAssertTrue(flag("idleTimerDisabledAfterSetup", app))
        capture("Closed during checked initialization", app)

        // A second, fresh process reaches the real missing-scene loader error
        // after setup2. This is not a simulated native failure result.
        app.terminate()
        app.launchArguments = ["--missing-main-scene", "--host-idle-timer=on"]
        app.launch()
        element("start-scene", app).tap()
        try await assertClosed(app, expectedExitEvents: 0, expectedState: "failed")
        XCTAssertTrue(flag("setup2Succeeded", app))
        XCTAssertEqual(metrics(app)["failure"] as? String, "MAIN_START_FAILED")
        XCTAssertEqual(number("bootstrapExitCode", app), 0)
        XCTAssertEqual(number("setup2ErrorCode", app), 0)
        XCTAssertEqual(number("mainStartExitCode", app), 1)
        XCTAssertTrue(flag("previousIdleTimerDisabled", app))
        XCTAssertTrue(flag("idleTimerDisabledAfterSetup", app))
        XCTAssertEqual(number("readyEvents", app), 0)
        XCTAssertEqual(number("iterations", app), 0)
        capture("Real scene-load failure restored shell policy", app)
    }

    @MainActor
    private func launchScene(initialIdleTimerDisabled: Bool = false) async throws -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = [initialIdleTimerDisabled ? "--host-idle-timer=on" : "--host-idle-timer=off"]
        app.launch()
        XCTAssertTrue(element("start-scene", app).waitForExistence(timeout: 15))
        element("start-scene", app).tap()
        try await waitUntil("A real Godot scene must emit Ready and execute iterations.", timeout: 45, app: app) {
            self.number("readyEvents", app) == 1 &&
            self.number("iterations", app) >= 3 &&
            self.flag("renderLoopActive", app)
        }
        XCTAssertTrue(flag("idleTimerPolicyCaptured", app))
        XCTAssertEqual(number("bootstrapExitCode", app), 0)
        XCTAssertEqual(number("setup2ErrorCode", app), 0)
        XCTAssertEqual(number("mainStartExitCode", app), 0)
        XCTAssertEqual(flag("previousIdleTimerDisabled", app), initialIdleTimerDisabled)
        XCTAssertTrue(flag("idleTimerDisabledAfterSetup", app))
        XCTAssertTrue(flag("idleTimerDisabled", app))
        return app
    }

    @MainActor
    private func assertClosed(_ app: XCUIApplication, expectedExitEvents: Int, expectedState: String = "closed") async throws {
        try await waitUntil("Close must destroy the OS singleton, stop iteration, and release the native view.", timeout: 30, app: app) {
            self.metrics(app)["state"] as? String == expectedState &&
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
        assertIdleTimerRestored(app)
        let finalIterations = number("iterations", app)
        let hostCounter = number("hostCounter", app)
        element("host-counter-button", app).tap()
        XCTAssertEqual(number("hostCounter", app), hostCounter + 1)
        try await Task.sleep(nanoseconds: 600_000_000)
        XCTAssertEqual(number("iterations", app), finalIterations)
    }

    @MainActor
    private func assertIdleTimerRestored(_ app: XCUIApplication) {
        XCTAssertTrue(flag("idleTimerPolicyCaptured", app))
        XCTAssertTrue(flag("idleTimerPolicyRestored", app))
        XCTAssertEqual(flag("idleTimerDisabled", app), flag("previousIdleTimerDisabled", app))
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
    private func waitUntil(_ message: String, timeout: TimeInterval = 15, app: XCUIApplication, condition: @MainActor () -> Bool) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline {
            try await Task.sleep(nanoseconds: 150_000_000)
        }
        let passed = condition()
        if !passed {
            // Preserve the actual coarse runtime state before an assertion
            // aborts this test. No launch document or renderer payload is logged.
            capture("Failed wait: \(message)", app)
            if let bytes = try? JSONSerialization.data(withJSONObject: metrics(app), options: [.sortedKeys]),
               let document = String(data: bytes, encoding: .utf8) {
                print("Probe failure snapshot: \(document)")
            }
        }
        XCTAssertTrue(passed, message)
        if !passed { throw WaitFailure.conditionTimedOut }
    }

    private enum WaitFailure: Error { case conditionTimedOut }

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
