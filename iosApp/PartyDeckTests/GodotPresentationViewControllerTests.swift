import UIKit
import XCTest
@testable import PartyDeck

/// Real UIKit shell layout with a plain child controller; these do not qualify Godot rendering.
@MainActor
final class GodotPresentationViewControllerTests: XCTestCase {
    func testPortraitStageUsesAvailableHeightWithStandardText() throws {
        try checkStageLayout(category: .large)
    }

    func testPortraitStageUsesAvailableHeightWithAccessibilityText() throws {
        try checkStageLayout(category: .accessibilityExtraExtraExtraLarge)
    }

    func testNativeChildRemainsInsideTheHiddenAccessibilityContainer() throws {
        let fixture = try makeFixture(category: .large)
        defer { fixture.close() }
        let container = try XCTUnwrap(fixture.native.view.superview)
        fixture.native.view.accessibilityElementsHidden = false
        fixture.host.allowNativePresentation()
        fixture.layout()

        XCTAssertFalse(fixture.native.view.accessibilityElementsHidden)
        XCTAssertTrue(fixture.native.view.isDescendant(of: container))
        XCTAssertTrue(container.accessibilityElementsHidden)
        XCTAssertTrue(container.isUserInteractionEnabled)

        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        XCTAssertEqual(fixture.host.sessionQualificationGeometry()["surfaceAccessibilityHiddenByContainer"] as? Bool, true)
        container.accessibilityElementsHidden = false
        XCTAssertTrue(fixture.native.view.isDescendant(of: container))
        XCTAssertEqual(fixture.host.sessionQualificationGeometry()["surfaceAccessibilityHiddenByContainer"] as? Bool, false)
        container.accessibilityElementsHidden = true
        XCTAssertEqual(fixture.host.sessionQualificationGeometry()["surfaceAccessibilityHiddenByContainer"] as? Bool, true)
        // An unrelated hidden container must not certify a child reparented into the same window.
        fixture.native.view.removeFromSuperview()
        fixture.host.view.addSubview(fixture.native.view)
        XCTAssertTrue(container.accessibilityElementsHidden)
        XCTAssertEqual(fixture.host.sessionQualificationGeometry()["surfaceAccessibilityHiddenByContainer"] as? Bool, false)
        #endif
    }

    private func checkStageLayout(category: UIContentSizeCategory) throws {
        let fixture = try makeFixture(category: category)
        defer { fixture.close() }
        var returns = 0
        fixture.host.onReturn = { _ in returns += 1 }
        let cover = try XCTUnwrap(find("godot-session-privacy-cover", in: fixture.host.view))
        let initial = try checkGeometry(fixture, category: category)
        XCTAssertFalse(cover.isHidden)

        fixture.host.allowNativePresentation()
        fixture.layout()
        XCTAssertTrue(cover.isHidden)
        assertSameFrame(try checkGeometry(fixture, category: category), initial)

        fixture.host.conceal()
        fixture.layout()
        XCTAssertFalse(cover.isHidden)
        assertSameFrame(try checkGeometry(fixture, category: category), initial)

        fixture.host.allowNativePresentation()
        fixture.layout()
        XCTAssertTrue(cover.isHidden)
        assertSameFrame(try checkGeometry(fixture, category: category), initial)
        XCTAssertEqual(returns, 0, "Cover and status changes must not resize an established native stage.")
    }

    private func checkGeometry(_ fixture: Fixture, category: UIContentSizeCategory) throws -> CGRect {
        let host = fixture.host.view!
        let status = try XCTUnwrap(find("godot-session-status", in: host) as? UILabel)
        let standard = try XCTUnwrap(find("godot-standard-table", in: host) as? UIButton)
        let leave = try XCTUnwrap(find("godot-leave-table", in: host) as? UIButton)
        let toolbar = try XCTUnwrap(standard.superview as? UIStackView)
        let container = try XCTUnwrap(fixture.native.view.superview)
        let stage = try XCTUnwrap(container.superview)
        let safe = host.safeAreaLayoutGuide.layoutFrame
        let frame = fixture.native.view.convert(fixture.native.view.bounds, to: host)
        let tolerance: CGFloat = 1

        XCTAssertGreaterThan(host.bounds.height, host.bounds.width, "This regression uses the portrait acceptance runner.")
        XCTAssertGreaterThan(host.safeAreaInsets.top, 0, "The pinned iPhone runner must supply its actual top safe area.")
        XCTAssertGreaterThan(host.safeAreaInsets.bottom, 0, "The pinned iPhone runner must supply its actual bottom safe area.")
        XCTAssertEqual(fixture.host.traitCollection.preferredContentSizeCategory, category)
        let expectedFont = UIFont.preferredFont(forTextStyle: .body, compatibleWith: fixture.host.traitCollection)
        XCTAssertEqual(status.font.pointSize, expectedFont.pointSize, accuracy: tolerance)
        XCTAssertEqual(toolbar.axis, category.isAccessibilityCategory ? .vertical : .horizontal)
        for button in [standard, leave] {
            XCTAssertGreaterThanOrEqual(button.bounds.height, 48 - tolerance)
            XCTAssertGreaterThanOrEqual(button.bounds.width, 48 - tolerance)
        }

        let statusHeight = max(status.font.lineHeight * 2,
            status.sizeThatFits(CGSize(width: status.bounds.width, height: .greatestFiniteMagnitude)).height)
        let buttonHeight = max(48, [standard, leave].map { button in
            button.systemLayoutSizeFitting(
                CGSize(width: button.bounds.width, height: UIView.layoutFittingCompressedSize.height),
                withHorizontalFittingPriority: .required, verticalFittingPriority: .fittingSizeLevel
            ).height
        }.max() ?? 0)
        let toolbarHeight = category.isAccessibilityCategory ? buttonHeight * 2 + toolbar.spacing : buttonHeight
        let availableStageHeight = safe.height - 12 - statusHeight - 8 - toolbarHeight - 12

        XCTAssertLessThanOrEqual(status.bounds.height, statusHeight + tolerance,
            "The status must keep its reserved text height instead of taking the native stage's space.")
        XCTAssertLessThanOrEqual(toolbar.bounds.height, toolbarHeight + tolerance)
        XCTAssertGreaterThan(availableStageHeight, 44)
        XCTAssertGreaterThanOrEqual(frame.height, availableStageHeight - tolerance,
            "The stage must fill the remaining safe-area height; a label-height strip is unusable.")
        XCTAssertEqual(frame.minX, safe.minX, accuracy: tolerance)
        XCTAssertEqual(frame.maxX, safe.maxX, accuracy: tolerance)
        XCTAssertEqual(frame.minY, toolbar.convert(toolbar.bounds, to: host).maxY + 12, accuracy: tolerance)
        XCTAssertEqual(frame.maxY, safe.maxY, accuracy: tolerance)
        assertSameFrame(frame, stage.convert(stage.bounds, to: host))
        return frame
    }

    private func assertSameFrame(_ actual: CGRect, _ expected: CGRect) {
        XCTAssertEqual(actual.minX, expected.minX, accuracy: 1)
        XCTAssertEqual(actual.minY, expected.minY, accuracy: 1)
        XCTAssertEqual(actual.width, expected.width, accuracy: 1)
        XCTAssertEqual(actual.height, expected.height, accuracy: 1)
    }

    private func find(_ identifier: String, in view: UIView) -> UIView? {
        if view.accessibilityIdentifier == identifier { return view }
        for child in view.subviews {
            if let match = find(identifier, in: child) { return match }
        }
        return nil
    }

    private func makeFixture(category: UIContentSizeCategory) throws -> Fixture {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }, "Host layout acceptance requires the app's active window scene.")
        let window = UIWindow(windowScene: scene)
        window.frame = scene.coordinateSpace.bounds
        let root = UIViewController()
        let native = UIViewController()
        let host = GodotPresentationViewController(nativeController: native)
        window.rootViewController = root
        root.loadViewIfNeeded()
        root.addChild(host)
        root.setOverrideTraitCollection(UITraitCollection(preferredContentSizeCategory: category), forChild: host)
        host.view.translatesAutoresizingMaskIntoConstraints = false
        root.view.addSubview(host.view)
        NSLayoutConstraint.activate([
            host.view.topAnchor.constraint(equalTo: root.view.topAnchor),
            host.view.leadingAnchor.constraint(equalTo: root.view.leadingAnchor),
            host.view.trailingAnchor.constraint(equalTo: root.view.trailingAnchor),
            host.view.bottomAnchor.constraint(equalTo: root.view.bottomAnchor),
        ])
        host.didMove(toParent: root)
        window.isHidden = false
        let fixture = Fixture(window: window, root: root, host: host, native: native)
        fixture.layout()
        XCTAssertFalse(window.isHidden)
        XCTAssertTrue(host.view.window === window)
        XCTAssertTrue(native.view.window === window)
        return fixture
    }

    @MainActor
    private struct Fixture {
        let window: UIWindow
        let root: UIViewController
        let host: GodotPresentationViewController
        let native: UIViewController

        func layout() {
            root.view.setNeedsLayout()
            root.view.layoutIfNeeded()
            host.view.layoutIfNeeded()
        }

        func close() {
            window.isHidden = true
            window.rootViewController = nil
        }
    }
}
