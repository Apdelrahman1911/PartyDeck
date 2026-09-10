import XCTest

final class RetainedHostUITests: XCTestCase {
    private var lastForegroundObservation: [String: Any] = [:]

    override func setUpWithError() throws { continueAfterFailure = false }

    @MainActor
    func testRepeated2DAnd3DKeepOneDormantEngine() async throws {
        let app = launch(idleTimer: false)
        var retainedIdentity: [String: String]?
        var processID: Int?
        var presentationIDs = Set<String>()
        var sceneIDs = Set<String>()
        var treeIDs = Set<String>()
        var previousGeneration: Int64 = 0
        var previousDormant: [String: Any]?
        for (index, mode) in ["2d", "3d", "2d", "3d"].enumerated() {
            let entered = try await enter(mode, app)
            let activeNative = native(entered)
            let id = try string("presentationID", entered)
            XCTAssertTrue(presentationIDs.insert(id).inserted)
            XCTAssertTrue(sceneIDs.insert(try string("sceneIdentity", activeNative)).inserted)
            XCTAssertTrue(treeIDs.insert(try string("treeIdentity", activeNative)).inserted)
            XCTAssertEqual(number("entryCount", entered), index + 1)
            XCTAssertEqual(number("presentationCount", activeNative), index + 1)
            XCTAssertGreaterThan(counter("presentationGeneration", activeNative), previousGeneration)
            previousGeneration = counter("presentationGeneration", activeNative)
            let identity = try stableIdentity(activeNative)
            if let retainedIdentity { XCTAssertEqual(identity, retainedIdentity) } else { retainedIdentity = identity }
            if let processID { XCTAssertEqual(number("processIdentifier", activeNative), processID) }
            else { processID = number("processIdentifier", activeNative) }
            if let previousDormant {
                XCTAssertEqual(activeNative["treeIdentity"] as? String, native(previousDormant)["treeIdentity"] as? String)
                XCTAssertGreaterThan(number("warmupFrames", activeNative), number("warmupFrames", native(previousDormant)))
            }
            try require(concealed(entered), "Each fresh renderer must begin with no private faces, labels, or selection.")
            capture("Entry \(index + 1): fresh concealed \(mode)", app)
            let played = try await revealSelectAndPlay(app)
            XCTAssertEqual(number("acceptedViewerPlays", played), 1)
            XCTAssertGreaterThan(counter("callbackEntries", audio(played)), 0, "Observe actual CoreAudio callbacks before testing suspension")
            _ = try await tapControl("exit", app)
            let closed = try await dormant(app, prior: played)
            XCTAssertEqual(closure(closed)["reason"] as? String, "EXIT_REQUESTED")
            XCTAssertEqual(try stableIdentity(native(closed)), identity)
            XCTAssertEqual(number("processIdentifier", native(closed)), processID)
            previousDormant = try await observeDormantShell(app, baseline: closed)
        }
        capture("Four completed real entries in one retained engine process", app)
    }

    @MainActor
    func testActiveAndDormantBackgroundTransitionsStayConcealed() async throws {
        let app = launch(idleTimer: true)
        _ = try await enter("2d", app)
        try await revealAndSelect(app)
        let beforeCycle = try await diagnostics(app)
        element("cycle-focus", app).tap()
        let cycled = try await diagnostics(app, after: beforeCycle) {
            self.concealed($0) && self.number("focusCycleCount", $0) == self.number("focusCycleCount", beforeCycle) + 1
        }
        assertNoAuthorityAction(beforeCycle, cycled)
        XCTAssertGreaterThan(counter("lifecycleGeneration", native(cycled)), counter("lifecycleGeneration", native(beforeCycle)))
        XCTAssertFalse(flag("privacyCoverVisible", native(cycled)), "Coalesced loss/regain must reconcile the concealed draw and release the cover")
        capture("Coalesced native foreground loss and regain returned concealed", app)
        try await revealAndSelect(app)
        let beforePause = try await diagnostics(app)
        element("pause-table", app).tap()
        let paused = try await diagnostics(app, after: beforePause, foreground: false) {
            self.flag("privacyCoverVisible", self.native($0)) && !self.flag("renderLoopActive", self.native($0)) && self.concealed($0)
        }
        assertNoAuthorityAction(beforePause, paused)
        XCTAssertGreaterThan(counter("lifecycleGeneration", native(paused)), counter("lifecycleGeneration", native(beforePause)))
        let pausedStable = try await observePaused(app, baseline: paused)
        element("pause-table", app).tap()
        let resumed = try await diagnostics(app, after: pausedStable) { self.concealed($0) }
        assertNoAuthorityAction(beforePause, resumed)
        XCTAssertEqual(try stableIdentity(native(resumed)), try stableIdentity(native(beforePause)))

        try await revealAndSelect(app)
        let beforeHome = try await diagnostics(app)
        try await homeAndActivate(app)
        let returned = try await diagnostics(app, after: beforeHome) {
            self.concealed($0) && self.number("applicationBackgroundCount", $0) > self.number("applicationBackgroundCount", beforeHome)
        }
        assertNoAuthorityAction(beforeHome, returned)
        XCTAssertEqual(returned["presentationID"] as? String, beforeHome["presentationID"] as? String)
        XCTAssertEqual(try stableIdentity(native(returned)), try stableIdentity(native(beforeHome)))
        XCTAssertGreaterThan(counter("lifecycleGeneration", native(returned)), counter("lifecycleGeneration", native(beforeHome)))
        capture("Real background and resume kept the same authority concealed", app)
        _ = try await tapControl("exit", app)
        let closed = try await dormant(app, prior: returned)
        let beforeDormantHome = try await observeDormantShell(app, baseline: closed)
        try await homeAndActivate(app)
        let dormantReturned = try await wait(app, "Dormant Home/activate must reach the real native owner.") {
            $0["state"] as? String == "dormant" &&
                self.number("applicationBackgroundCount", $0) > self.number("applicationBackgroundCount", beforeDormantHome)
        }
        try assertDormant(dormantReturned)
        assertNoDormantWork(beforeDormantHome, dormantReturned)
        XCTAssertTrue(flag("applicationActive", native(dormantReturned)))
        XCTAssertFalse(flag("applicationBackgrounded", native(dormantReturned)))
        _ = try await observeDormantShell(app, baseline: dormantReturned)
        let next = try await enter("3d", app)
        XCTAssertNotEqual(next["presentationID"] as? String, returned["presentationID"] as? String)
        XCTAssertEqual(try stableIdentity(native(next)), try stableIdentity(native(returned)))
        XCTAssertTrue(concealed(next))
        _ = try await tapControl("exit", app)
        _ = try await dormant(app, prior: next)
        capture("Dormant application lifecycle did not restart the engine services", app)
    }

    @MainActor
    func testStaleFirstReadyAndCloseCompletionReentry() async throws {
        let app = launch(idleTimer: false, supersedeFirstReady: true)
        let first = try await enter("2d", app)
        let probe = (first["firstReadyProbe"] as? [String: Any]) ?? [:]
        XCTAssertTrue(flag("attempted", probe))
        XCTAssertTrue(flag("completed", probe))
        XCTAssertFalse(flag("accepted", probe))
        XCTAssertFalse(flag("nativeReadyConfirmedAtRejection", probe))
        XCTAssertGreaterThan(counter("currentGeneration", probe), counter("capturedGeneration", probe))
        XCTAssertEqual(counter("reportedGenerationBeforeCompletion", probe), counter("currentGeneration", probe))
        XCTAssertTrue(flag("readyConfirmed", first))
        XCTAssertTrue(flag("authorityReadyConfirmed", native(first)))
        XCTAssertEqual(number("readyEvents", native(first)), 1)
        _ = try await wait(app, "The first accepted projection must finish before the close-order probe.") {
            !self.flag("modelDeliveryPending", $0) && self.number("modelQueuedDocuments", $0) == 0
        }
        element("switch-table", app).tap()
        let second = try await diagnostics(app) { $0["mode"] as? String == "3d" && self.number("entryCount", $0) == 2 }
        let closed = closure(second)
        try assertClosure(closed)
        XCTAssertEqual(closed["reason"] as? String, "SWITCH_FROM_CLOSE_COMPLETION")
        XCTAssertNotEqual(second["presentationID"] as? String, first["presentationID"] as? String)
        XCTAssertEqual(try stableIdentity(native(second)), try stableIdentity(native(first)))
        XCTAssertEqual(number("processIdentifier", native(second)), number("processIdentifier", native(first)))
        XCTAssertTrue(concealed(second))

        element("probe-old-handle", app).tap()
        let probed = try await diagnostics(app, after: second) {
            let value = ($0["staleProbe"] as? [String: Any]) ?? [:]
            return self.flag("deliveryCompleted", value) && self.flag("closeCompleted", value)
        }
        let stale = (probed["staleProbe"] as? [String: Any]) ?? [:]
        XCTAssertTrue(flag("callbackRebindingRefused", stale))
        XCTAssertFalse(flag("sendAccepted", stale))
        XCTAssertFalse(flag("deliveryAccepted", stale))
        XCTAssertFalse(flag("readyConfirmationAccepted", stale))
        XCTAssertFalse(flag("diagnosticsAccepted", stale))
        XCTAssertTrue(flag("oldCloseDormant", stale), "Repeated close describes only the old handle's completed cleanup")
        XCTAssertEqual(number("retiredCallbacksAfterClose", probed), 0)
        XCTAssertEqual(probed["presentationID"] as? String, second["presentationID"] as? String)
        XCTAssertEqual(try stableIdentity(native(probed)), try stableIdentity(native(second)))
        assertNoAuthorityAction(second, probed)
        capture("Old native handle refused commands, grants, callbacks, and replacement closure", app)
        let played = try await revealSelectAndPlay(app)
        _ = try await tapControl("exit", app)
        let dormant = try await dormant(app, prior: played)
        _ = try await observeDormantShell(app, baseline: dormant)
    }

    @MainActor
    private func launch(idleTimer: Bool, supersedeFirstReady: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["--host-idle-timer=\(idleTimer ? "on" : "off")"]
        if supersedeFirstReady { app.launchArguments.append("--supersede-first-ready") }
        app.launch()
        XCTAssertTrue(element("retained-shell", app).waitForExistence(timeout: 15))
        return app
    }

    @MainActor
    private func enter(_ mode: String, _ app: XCUIApplication) async throws -> [String: Any] {
        let button = element("start-\(mode)", app)
        try require(button.waitForExistence(timeout: 15) && button.isEnabled, "The native shell must permit a fresh entry.")
        button.tap()
        let value = try await diagnostics(app, timeout: 60)
        XCTAssertEqual(value["mode"] as? String, mode)
        XCTAssertEqual(value["lifecycle"] as? String, "READY")
        XCTAssertTrue(flag("retainedEnginePolicy", native(value)))
        XCTAssertEqual(number("readyEvents", native(value)), 1)
        XCTAssertEqual(number("bootstrapCount", native(value)), 1)
        XCTAssertEqual(number("cleanupCount", native(value)), 0)
        XCTAssertGreaterThan(number("processIdentifier", native(value)), 0)
        XCTAssertTrue(flag("authorityReadyConfirmed", native(value)))
        XCTAssertFalse(flag("authorityReleased", value))
        XCTAssertFalse(flag("authorityReadyConfirmed", (value["entryPreparedNative"] as? [String: Any]) ?? [:]))
        XCTAssertGreaterThan(number("nativePresentedFrames", native(value)), 0)
        XCTAssertEqual(number("nativeFailedPresentations", native(value)), 0)
        return value
    }

    @MainActor
    private func revealAndSelect(_ app: XCUIApplication) async throws {
        let beforeReveal = try await tapControl("reveal", app)
        let revealed = try await diagnostics(app, after: beforeReveal) {
            !self.flag("handConcealed", self.renderer($0)) && self.number("privateFaceCount", self.renderer($0)) > 0 &&
                self.number("privateLabelCount", self.renderer($0)) > 0
        }
        assertNoAuthorityAction(beforeReveal, revealed)
        XCTAssertEqual(beforeReveal["revision"] as? String, revealed["revision"] as? String)
        let beforeSelection = try await tapControl("card", app, cardIndex: 0)
        let selected = try await diagnostics(app, after: beforeSelection) {
            self.number("selectedCount", self.renderer($0)) == 1 &&
                self.control("card", in: $0, cardIndex: 0).map { self.flag("selected", $0) } == true
        }
        assertNoAuthorityAction(beforeSelection, selected)
        capture("Real reveal and card selection", app)
    }

    @MainActor
    private func revealSelectAndPlay(_ app: XCUIApplication) async throws -> [String: Any] {
        try await revealAndSelect(app)
        let before = try await tapControl("play", app)
        let played = try await diagnostics(app, after: before) {
            self.number("acceptedViewerPlays", $0) == self.number("acceptedViewerPlays", before) + 1 && self.concealed($0)
        }
        XCTAssertEqual(number("acceptedRendererEvents", played), number("acceptedRendererEvents", before) + 1)
        XCTAssertGreaterThan(number("intentEvents", native(played)), number("intentEvents", native(before)))
        capture("Real play accepted by the Kotlin authority", app)
        return played
    }

    @MainActor
    private func dormant(_ app: XCUIApplication, prior: [String: Any]) async throws -> [String: Any] {
        let value = try await wait(app, "Close must complete only after actual native dormancy.", timeout: 30) {
            $0["state"] as? String == "dormant" && self.flag("completionObserved", self.closure($0))
        }
        try assertDormant(value)
        try assertClosure(closure(value))
        XCTAssertEqual(native(value)["previousTreeIdentity"] as? String, native(prior)["treeIdentity"] as? String)
        XCTAssertEqual(native(value)["previousSceneIdentity"] as? String, native(prior)["sceneIdentity"] as? String)
        XCTAssertNotEqual(native(value)["treeIdentity"] as? String, native(prior)["treeIdentity"] as? String)
        XCTAssertTrue(element("retained-shell", app).exists)
        XCTAssertFalse(element("godot-surface", app).exists, "A detached retained surface is absent from the shell's input hierarchy")
        capture("Whole recipient scene retired; retained services dormant", app)
        return value
    }

    private func assertClosure(_ value: [String: Any]) throws {
        try require(flag("completionObserved", value) && flag("dormant", value), "Observe the actual native close completion result.")
        XCTAssertTrue(flag("returnedBeforeCompletion", value))
        XCTAssertTrue(flag("openWhileClosingRefused", value))
        XCTAssertFalse((value["openWhileClosingError"] as? String ?? "").isEmpty)
        XCTAssertTrue(flag("authorityReleased", value))
        XCTAssertTrue(flag("authorityLaunchCleared", value))
        XCTAssertEqual((value["authorityStatus"] as? [String: Any])?["lifecycle"] as? String, "CLOSED")
        XCTAssertTrue(flag("handleViewControllerReleased", value))
        XCTAssertTrue(flag("handleCallbacksCleared", value))
        XCTAssertEqual(number("callbacksAfterClose", value), 0)
        let returned = (value["returnedNative"] as? [String: Any]) ?? [:]
        let completed = (value["completionNative"] as? [String: Any]) ?? [:]
        XCTAssertTrue(flag("privacyCoverVisible", returned))
        XCTAssertFalse(flag("presentationActive", returned))
        XCTAssertFalse(flag("renderLoopActive", returned))
        XCTAssertFalse(flag("eventHandlerPresent", returned))
        XCTAssertEqual(number("queuedPrivateDocuments", returned), 0)
        XCTAssertEqual(completed["state"] as? String, "dormant")
        XCTAssertEqual(number("retirementDepth", completed), 0)
        XCTAssertGreaterThanOrEqual(decimal("completedAtUptime", value) - decimal("requestedAtUptime", value),
                                    decimal("audioObservationMinimumSeconds", completed))
        if value["reason"] as? String == "SWITCH_FROM_CLOSE_COMPLETION" {
            let before = (value["closeProbeBeforeNative"] as? [String: Any]) ?? [:]
            let after = (value["closeProbeAfterNative"] as? [String: Any]) ?? [:]
            for name in ["queuedCommands", "queuedPrivateDocuments"] {
                XCTAssertGreaterThanOrEqual(number(name, before), 0, name)
                XCTAssertEqual(number(name, after), number(name, before) + 1, name)
            }
            XCTAssertGreaterThanOrEqual(number("queuedBytes", before), 0)
            XCTAssertGreaterThan(number("closeProbeDocumentBytes", value), 0)
            XCTAssertEqual(number("queuedBytes", after), number("queuedBytes", before) + number("closeProbeDocumentBytes", value))
            XCTAssertTrue(flag("presentationActive", before))
            XCTAssertTrue(flag("presentationActive", after))
            XCTAssertGreaterThan(counter("presentationGeneration", before), 0)
            XCTAssertEqual(counter("presentationGeneration", after), counter("presentationGeneration", before))
            XCTAssertGreaterThan(counter("closeProbeLifecycleGeneration", value), 0)
            XCTAssertEqual(counter("lifecycleGeneration", before), counter("closeProbeLifecycleGeneration", value))
            XCTAssertEqual(counter("lifecycleGeneration", after), counter("closeProbeLifecycleGeneration", value))
            XCTAssertEqual(number("iterations", after), number("iterations", before))
            XCTAssertNotNil(value["closeProbeCallbackObservedBeforeClose"])
            XCTAssertFalse(flag("closeProbeCallbackObservedBeforeClose", value))
            XCTAssertTrue(flag("closeProbeCallbackObserved", value))
            XCTAssertFalse(flag("closeProbeDelivered", value))
            XCTAssertNotNil(value["closeProbeCallbackBeforeClose"])
            XCTAssertFalse(flag("closeProbeCallbackBeforeClose", value))
            XCTAssertTrue(flag("closeProbeCallbackBeforeCompletion", value))
        }
    }

    private func assertDormant(_ value: [String: Any]) throws {
        let native = native(value)
        try require(native["state"] as? String == "dormant" && flag("dormant", native), "The real owner must report dormancy.")
        XCTAssertTrue(flag("osSingletonPresent", native))
        XCTAssertTrue(flag("bridgeRegistered", native))
        XCTAssertEqual(number("bootstrapCount", native), 1)
        XCTAssertEqual(number("cleanupCount", native), 0)
        XCTAssertFalse(flag("quarantined", native))
        XCTAssertTrue(flag("emptyTree", native))
        XCTAssertEqual(number("emptyTreeNodeCount", native), 1)
        XCTAssertTrue(flag("oldSceneObjectsAbsent", native))
        XCTAssertGreaterThan(number("retiredNodeCount", native), 1)
        XCTAssertEqual(number("bridgeConnections", native), 0)
        XCTAssertTrue(flag("neutralFramePresented", native))
        XCTAssertFalse(flag("surfaceAttached", native))
        XCTAssertFalse(flag("renderLoopActive", native))
        XCTAssertNotNil(native["inputViewEnabled"])
        XCTAssertFalse(flag("inputViewEnabled", native))
        XCTAssertTrue(flag("surfaceAccessibilityHidden", native))
        XCTAssertFalse(flag("eventHandlerPresent", native))
        XCTAssertFalse(flag("sdlEnabled", native))
        XCTAssertTrue(flag("idleTimerPolicyRestored", native))
        XCTAssertEqual(flag("idleTimerDisabled", native), flag("previousIdleTimerDisabled", native))
        for name in ["queuedCommands", "queuedEvents", "queuedBytes", "queuedPrivateDocuments", "cancelledDeliveryCallbacks", "drawDepth", "retirementDepth"] {
            XCTAssertEqual(number(name, native), 0, name)
        }
        XCTAssertTrue(((native["rendererDiagnostics"] as? [String: Any]) ?? [:]).isEmpty)
        XCTAssertTrue(flag("authorityReleased", value))
        XCTAssertEqual(number("modelQueuedDocuments", value), 0)
        XCTAssertFalse(flag("modelDeliveryPending", value))
        XCTAssertEqual(number("retiredCallbacksAfterClose", value), 0)
        let audio = audio(value)
        XCTAssertEqual(audio["driver"] as? String, "CoreAudio")
        XCTAssertTrue(flag("observed", audio))
        XCTAssertTrue(flag("outputUnitPresent", audio))
        XCTAssertFalse(flag("inputUnitPresent", audio))
        XCTAssertFalse(flag("active", audio))
        XCTAssertEqual(number("callbacksInFlight", audio), 0)
        XCTAssertEqual(number("lastStopStatus", audio), 0)
        XCTAssertGreaterThan(number("stopAttempts", audio), 0)
        XCTAssertEqual(number("stoppedStartAttempt", audio), number("startAttempts", audio))
        XCTAssertTrue(flag("audioQuiescenceObserved", native))
        let retirement = (native["audioRetirement"] as? [String: Any]) ?? [:]
        XCTAssertEqual(number("error", retirement), 0)
        for name in ["preflightPassed", "playbackCleanupSucceeded", "callbackCleanupSucceeded", "busDetailsCleanupSucceeded",
                     "oldBusDetailsCleanupSucceeded", "residualsObserved", "serverBuffersNeutral", "driverBufferNeutral", "driverQuiescent"] {
            XCTAssertTrue(flag(name, retirement), name)
        }
        for name in ["playbacksRemaining", "callbacksRemaining", "busDetailsRemaining", "samplePlaybacksRemaining"] {
            XCTAssertEqual(number(name, retirement), 0, name)
        }
        let motion = (native["motion"] as? [String: Any]) ?? [:]
        XCTAssertNotNil(motion["available"], "A simulator's unavailable sensor is an observation, not a passed physical sensor test")
        XCTAssertFalse(flag("active", motion))
    }

    @MainActor
    private func observeDormantShell(_ app: XCUIApplication, baseline: [String: Any]) async throws -> [String: Any] {
        element("host-counter-button", app).tap()
        var value = try await wait(app, "The native shell must respond while Godot is dormant.") {
            self.number("hostCounter", $0) == self.number("hostCounter", baseline) + 1
        }
        let minimum = max(0.8, decimal("audioObservationMinimumSeconds", native(baseline)))
        var observed = 0
        repeat {
            let previousPoll = number("pollCount", value)
            value = try await wait(app, "Observe another real native-shell sample.") { self.number("pollCount", $0) > previousPoll }
            try assertDormant(value)
            assertNoDormantWork(baseline, value)
            observed += 1
        } while observed < 2 || decimal("observedUptime", value) - decimal("observedUptime", baseline) < minimum
        attach(["before": baseline, "after": value, "samples": observed], "Measured dormant shell interval")
        return value
    }

    private func assertNoDormantWork(_ before: [String: Any], _ after: [String: Any]) {
        for name in ["iterations", "drawCalls", "nativePresentedFrames", "nativeFailedPresentations", "readyEvents", "intentEvents", "exitEvents"] {
            XCTAssertEqual(number(name, native(after)), number(name, native(before)), name)
        }
        XCTAssertEqual(counter("callbackEntries", audio(after)), counter("callbackEntries", audio(before)))
        XCTAssertEqual(counter("engineFramesDrawn", native(after)), counter("engineFramesDrawn", native(before)))
        for name in ["startAttempts", "stopAttempts"] { XCTAssertEqual(number(name, audio(after)), number(name, audio(before)), name) }
        XCTAssertEqual(native(after)["treeIdentity"] as? String, native(before)["treeIdentity"] as? String)
    }

    @MainActor
    private func observePaused(_ app: XCUIApplication, baseline: [String: Any]) async throws -> [String: Any] {
        let value = try await wait(app, "A paused native presentation must remain stopped across measured time.") {
            self.decimal("observedUptime", $0) - self.decimal("observedUptime", baseline) >= 0.8 &&
                self.number("pollCount", $0) > self.number("pollCount", baseline)
        }
        XCTAssertEqual(number("iterations", native(value)), number("iterations", native(baseline)))
        XCTAssertFalse(flag("renderLoopActive", native(value)))
        XCTAssertFalse(flag("active", audio(value)))
        XCTAssertEqual(counter("callbackEntries", audio(value)), counter("callbackEntries", audio(baseline)))
        XCTAssertFalse(flag("active", (native(value)["motion"] as? [String: Any]) ?? [:]))
        return value
    }

    @MainActor
    private func homeAndActivate(_ app: XCUIApplication) async throws {
        XCUIDevice.shared.press(.home)
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let deadline = Date().addingTimeInterval(20)
        var last: [String: Any] = [:]
        var observed = false
        while Date() < deadline {
            var dock: [[String: Any]] = []
            if springboard.state == .runningForeground && app.state != .notRunning {
                let screen = springboard.frame
                for identifier in ["Safari", "Messages"] {
                    let icon = springboard.icons.matching(identifier: identifier).firstMatch
                    guard icon.exists && icon.isHittable else { continue }
                    let frame = icon.frame
                    if frame.width > 0 && frame.height > 0 && screen.contains(frame) && frame.midY > screen.minY + screen.height * 0.75 {
                        dock.append(["identifier": icon.identifier, "frame": [frame.minX, frame.minY, frame.width, frame.height]])
                    }
                }
            }
            last = ["applicationState": app.state.rawValue, "springboardState": springboard.state.rawValue,
                    "dockIcons": dock, "observedAtUnixSeconds": Date().timeIntervalSince1970]
            if dock.count == 2 && springboard.alerts.count == 0 { observed = true; break }
            if app.state == .notRunning { break }
            try await Task.sleep(nanoseconds: 150_000_000)
        }
        attach(last, "Actual Home state and dock observation")
        let hierarchy = XCTAttachment(string: springboard.debugDescription)
        hierarchy.name = "Actual SpringBoard hierarchy"; hierarchy.lifetime = .keepAlways; add(hierarchy)
        let screenshot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        screenshot.name = "Actual Home screen"; screenshot.lifetime = .keepAlways; add(screenshot)
        try require(observed, "Observe the actual Home dock before reactivating the retained app.")
        app.activate()
    }

    @MainActor
    private func tapControl(_ action: String, _ app: XCUIApplication, cardIndex: Int = -1) async throws -> [String: Any] {
        var value = try await diagnostics(app)
        var gestures = 0
        for _ in 0..<16 {
            guard let candidate = control(action, in: value, cardIndex: cardIndex) else { throw Failure.controlMissing }
            let revision = value["revision"] as? String
            let size = viewport(value)
            let iterations = number("iterations", native(value))
            let confirmed = try await diagnostics(app, after: value) { self.number("iterations", self.native($0)) > iterations }
            value = confirmed
            guard revision == value["revision"] as? String, size == viewport(value),
                  let target = control(action, in: value, cardIndex: cardIndex), NSDictionary(dictionary: candidate).isEqual(to: target) else { continue }
            try require(flag("enabled", target), "Only an actual enabled renderer control can receive a test tap.")
            let rect = try rectangle(target["rect"])
            let clip = try rectangle(target["clipRect"])
            let surface = element("godot-surface", app)
            let actual = (native(value)["surfaceSize"] as? [String: Any]) ?? [:]
            try require(surface.isHittable && size.width > 0 && size.height > 0 &&
                        abs(surface.frame.width - size.width) <= 1 && abs(surface.frame.height - size.height) <= 1 &&
                        abs(CGFloat(decimal("width", actual)) - size.width) <= 1 &&
                        abs(CGFloat(decimal("height", actual)) - size.height) <= 1,
                        "Godot's actual input coordinates must agree with the visible UIKit surface.")
            try require(CGRect(origin: .zero, size: size).insetBy(dx: -0.5, dy: -0.5).contains(clip), "The control clip must remain inside the renderer viewport.")
            attach(["action": action, "control": target, "metrics": value], "Measured real touch target")
            if flag("visible", target) && clip.insetBy(dx: -0.5, dy: -0.5).contains(rect) {
                try require(rect.width >= 44 && rect.height >= 44, "The actual touch target must be at least 44 points.")
                let latest = metrics(app)
                guard flag("sceneStateApplied", renderer(latest)),
                      latest["revision"] as? String == revision, !flag("privacyCoverVisible", native(latest)),
                      let current = control(action, in: latest, cardIndex: cardIndex), NSDictionary(dictionary: target).isEqual(to: current) else { continue }
                surface.coordinate(withNormalizedOffset: CGVector(dx: rect.midX / size.width, dy: rect.midY / size.height)).tap()
                return value
            }
            try require(gestures < 8 && clip.width >= 32 && clip.height >= 32 && rect.width <= clip.width + 0.5 && rect.height <= clip.height + 0.5,
                        "A clipped control must fit its actual scroll area within the gesture bound.")
            let start: CGPoint
            let end: CGPoint
            let distance: CGFloat
            if rect.minY < clip.minY {
                distance = scrollDistance(clip.minY - rect.minY, span: clip.height, target: rect.height)
                start = CGPoint(x: clip.midX, y: clip.minY + clip.height * 0.2); end = CGPoint(x: start.x, y: start.y + distance)
            } else if rect.maxY > clip.maxY {
                distance = scrollDistance(rect.maxY - clip.maxY, span: clip.height, target: rect.height)
                start = CGPoint(x: clip.midX, y: clip.minY + clip.height * 0.8); end = CGPoint(x: start.x, y: start.y - distance)
            } else if rect.minX < clip.minX {
                distance = scrollDistance(clip.minX - rect.minX, span: clip.width, target: rect.width)
                start = CGPoint(x: clip.minX + clip.width * 0.2, y: clip.midY); end = CGPoint(x: start.x + distance, y: start.y)
            } else {
                distance = scrollDistance(rect.maxX - clip.maxX, span: clip.width, target: rect.width)
                start = CGPoint(x: clip.minX + clip.width * 0.8, y: clip.midY); end = CGPoint(x: start.x - distance, y: start.y)
            }
            let from = surface.coordinate(withNormalizedOffset: CGVector(dx: start.x / size.width, dy: start.y / size.height))
            let to = surface.coordinate(withNormalizedOffset: CGVector(dx: end.x / size.width, dy: end.y / size.height))
            from.press(forDuration: 0.1, thenDragTo: to, withVelocity: XCUIGestureVelocity(rawValue: min(180, max(60, distance))), thenHoldForDuration: 0.35)
            gestures += 1
            value = try await diagnostics(app, after: value)
        }
        capture("Renderer control failed to settle", app)
        throw Failure.geometry
    }

    @MainActor
    private func diagnostics(_ app: XCUIApplication, after: [String: Any]? = nil, foreground: Bool = true, timeout: TimeInterval = 15,
                             predicate: ([String: Any]) -> Bool = { _ in true }) async throws -> [String: Any] {
        try await wait(app, "Observe current renderer diagnostics for the retained presentation.", timeout: timeout) { value in
            let scene = self.renderer(value)
            let newer = after == nil || self.counter("sequence", scene) > self.counter("sequence", self.renderer(after!)) ||
                value["presentationID"] as? String != after?["presentationID"] as? String
            return value["lifecycle"] as? String == "READY" && self.flag("readyConfirmed", value) && !scene.isEmpty &&
                self.flag("sceneStateApplied", scene) && newer &&
                scene["presentationId"] as? String == value["presentationID"] as? String &&
                scene["revision"] as? String == value["revision"] as? String &&
                self.flag("foreground", scene) == foreground && self.flag("foreground", value) == foreground &&
                (!foreground || (self.flag("renderLoopActive", self.native(value)) && !self.flag("privacyCoverVisible", self.native(value)))) && predicate(value)
        }
    }

    @MainActor
    private func wait(_ app: XCUIApplication, _ message: String, timeout: TimeInterval = 15,
                      predicate: ([String: Any]) -> Bool) async throws -> [String: Any] {
        let startedAt = ProcessInfo.processInfo.systemUptime
        let deadline = Date().addingTimeInterval(timeout)
        var lastRejectedMeasurements: [String: Any] = [:]
        while Date() < deadline {
            let value = metrics(app)
            if app.state == .notRunning || !(value["failure"] as? String ?? "").isEmpty || flag("quarantined", native(value)) || native(value)["state"] as? String == "failed" {
                capture("Actual retained owner failure", app)
                XCTFail("The retained owner or native application failed.")
                throw Failure.native
            }
            if predicate(value) { return value }
            lastRejectedMeasurements = value
            try await Task.sleep(nanoseconds: 150_000_000)
        }
        // Screenshot capture can wait on the app and observe a later frame.
        // Keep the rejected value before requesting any further app work.
        attach(["timeoutSeconds": timeout,
                "elapsedSeconds": ProcessInfo.processInfo.systemUptime - startedAt,
                "measurements": lastRejectedMeasurements], "Last rejected retained wait observation")
        capture("Failed retained observation", app)
        XCTFail(message)
        throw Failure.timeout
    }

    private func stableIdentity(_ native: [String: Any]) throws -> [String: String] {
        var result: [String: String] = [:]
        for name in ["engineIdentity", "controllerIdentity", "viewIdentity", "layerIdentity"] {
            let id = try string(name, native)
            try require(id != "0x0" && id != "(nil)", "The retained \(name) must be an actual live native identity.")
            result[name] = id
        }
        return result
    }

    private func assertNoAuthorityAction(_ before: [String: Any], _ after: [String: Any]) {
        for name in ["acceptedRendererEvents", "acceptedViewerPlays", "acceptedViewerChallenges", "roundsAdvanced", "acceptedOpponentActions"] {
            XCTAssertEqual(number(name, after), number(name, before), name)
        }
    }

    private func concealed(_ value: [String: Any]) -> Bool {
        let scene = renderer(value)
        return flag("handConcealed", scene) && number("selectedCount", scene) == 0 && number("privateFaceCount", scene) == 0 && number("privateLabelCount", scene) == 0
    }

    private func control(_ action: String, in value: [String: Any], cardIndex: Int = -1) -> [String: Any]? {
        let group = action == "card" ? "partydeck_hand_card" : "partydeck_action_\(action)"
        return (renderer(value)["controls"] as? [[String: Any]])?.first { $0["group"] as? String == group && number("cardIndex", $0) == cardIndex }
    }

    private func viewport(_ value: [String: Any]) -> CGSize {
        let size = (renderer(value)["viewport"] as? [String: Any]) ?? [:]
        return CGSize(width: CGFloat(decimal("width", size)), height: CGFloat(decimal("height", size)))
    }

    private func rectangle(_ value: Any?) throws -> CGRect {
        guard let parts = value as? [NSNumber], parts.count == 4 else { throw Failure.geometry }
        return CGRect(x: parts[0].doubleValue, y: parts[1].doubleValue, width: parts[2].doubleValue, height: parts[3].doubleValue)
    }

    private func scrollDistance(_ gap: CGFloat, span: CGFloat, target: CGFloat) -> CGFloat {
        min(span * 0.45, max(24, gap + min(12, max(0, (span - target) / 2))))
    }

    @MainActor
    private func metrics(_ app: XCUIApplication) -> [String: Any] {
        guard app.state == .runningForeground else { return ["observedApplicationState": app.state.rawValue] }
        // RetainedHost emits this identifier on Text; native AX records StaticText.
        // A typed query does not remove the need for current native readiness.
        // https://developer.apple.com/documentation/xcuiautomation/xcuielementtypequeryprovider/statictexts
        let queryStartedAt = ProcessInfo.processInfo.systemUptime
        let queriedValue = app.staticTexts.matching(identifier: "retained-metrics").firstMatch.value
        let querySeconds = ProcessInfo.processInfo.systemUptime - queryStartedAt
        guard let document = queriedValue as? String, let data = document.data(using: .utf8),
              var value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return ["observedApplicationState": app.state.rawValue,
                    "observedMetricsQuerySeconds": querySeconds]
        }
        value["observedApplicationState"] = app.state.rawValue
        value["observedMetricsQuerySeconds"] = querySeconds
        lastForegroundObservation = value
        return value
    }

    @MainActor
    private func element(_ id: String, _ app: XCUIApplication) -> XCUIElement { app.descendants(matching: .any).matching(identifier: id).firstMatch }
    private func native(_ value: [String: Any]) -> [String: Any] { (value["native"] as? [String: Any]) ?? [:] }
    private func renderer(_ value: [String: Any]) -> [String: Any] { (native(value)["rendererDiagnostics"] as? [String: Any]) ?? [:] }
    private func audio(_ value: [String: Any]) -> [String: Any] { (native(value)["audio"] as? [String: Any]) ?? [:] }
    private func closure(_ value: [String: Any]) -> [String: Any] { (value["lastClosure"] as? [String: Any]) ?? [:] }
    private func number(_ name: String, _ value: [String: Any]) -> Int { (value[name] as? NSNumber)?.intValue ?? -1 }
    private func decimal(_ name: String, _ value: [String: Any]) -> Double { (value[name] as? NSNumber)?.doubleValue ?? -1 }
    private func flag(_ name: String, _ value: [String: Any]) -> Bool { (value[name] as? NSNumber)?.boolValue ?? false }
    private func counter(_ name: String, _ value: [String: Any]) -> Int64 { Int64((value[name] as? String) ?? "") ?? -1 }
    private func string(_ name: String, _ value: [String: Any]) throws -> String {
        guard let text = value[name] as? String, !text.isEmpty else { throw Failure.observation }
        return text
    }
    private func require(_ condition: Bool, _ message: String) throws {
        if !condition { XCTFail(message); throw Failure.observation }
    }

    @MainActor
    private func capture(_ name: String, _ app: XCUIApplication) {
        let screenshot = XCTAttachment(screenshot: app.state == .runningForeground ? app.screenshot() : XCUIScreen.main.screenshot())
        screenshot.name = name; screenshot.lifetime = .keepAlways; add(screenshot)
        attach(metrics(app), "\(name) measurements")
        if app.state != .runningForeground { attach(lastForegroundObservation, "\(name) last foreground observation") }
    }

    private func attach(_ value: [String: Any], _ name: String) {
        guard let data = try? JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]) else {
            XCTFail("Could not serialize the actual retained observation.")
            return
        }
        let attachment = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
        attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }

    private enum Failure: Error { case native, timeout, controlMissing, geometry, observation }
}
