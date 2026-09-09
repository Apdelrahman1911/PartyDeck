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
        capture("Practice table", app: app)
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
    private func capture(_ name: String, app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
