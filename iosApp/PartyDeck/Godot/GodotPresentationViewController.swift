import UIKit

enum GodotTableReturn {
    case standard
    case leave
}

/// The shell owns the toolbar and this cover; the native child owns its draw/input privacy gate.
final class GodotPresentationViewController: UIViewController {
    var onVisibilityChanged: ((Bool) -> Void)?
    var onReturn: ((GodotTableReturn) -> Void)?
    var onUnexpectedDismissal: (() -> Void)?

    private let nativeController: UIViewController
    private let engineContainer = UIView()
    private let stage = UIView()
    private let cover = UILabel()
    private let status = UILabel()
    private let buttons = UIStackView()
    private var nativeConstraints: [NSLayoutConstraint] = []
    private var standardButton: UIButton!
    private var leaveButton: UIButton!
    private var establishedSize: CGSize?
    private var returnRequested = false
    private var closing = false
    private var ready = false
    #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
    private var qualificationCoverTransitions: UInt64 = 0
    private var qualificationCoverCounterExhausted = false
    private var qualificationFirstCoverRelease: TimeInterval?
    private var qualificationLastCoverTransition: TimeInterval?
    #endif

    init(nativeController: UIViewController) {
        self.nativeController = nativeController
        super.init(nibName: nil, bundle: nil)
        modalPresentationStyle = .fullScreen
        isModalInPresentation = true
        overrideUserInterfaceStyle = .dark
    }

    required init?(coder: NSCoder) { return nil }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = Self.ink
        view.accessibilityViewIsModal = true
        view.accessibilityIdentifier = "godot-session-table"

        status.textColor = Self.paper
        status.font = UIFont.preferredFont(forTextStyle: .body)
        status.adjustsFontForContentSizeCategory = true
        status.numberOfLines = 2
        status.text = text("Godot.Opening", "Opening your table…")
        status.accessibilityIdentifier = "godot-session-status"
        status.setContentHuggingPriority(.defaultHigh, for: .vertical)

        standardButton = button(
            title: text("Godot.StandardTable", "Standard table"),
            hint: text("Godot.StandardTableHint", "Continue this game with screen-reader controls."),
            action: #selector(useStandardTable),
            identifier: "godot-standard-table"
        )
        leaveButton = button(
            title: text("Godot.LeaveTable", "Leave table"),
            hint: text("Godot.LeaveTableHint", "Open the leave-table confirmation."),
            action: #selector(leaveTable),
            identifier: "godot-leave-table"
        )
        buttons.spacing = 8
        buttons.distribution = .fillEqually
        buttons.addArrangedSubview(standardButton)
        buttons.addArrangedSubview(leaveButton)
        updateButtonLayout()

        cover.backgroundColor = Self.ink
        cover.textColor = Self.paper
        cover.textAlignment = .center
        cover.font = UIFont.preferredFont(forTextStyle: .title2)
        cover.adjustsFontForContentSizeCategory = true
        cover.numberOfLines = 0
        cover.isUserInteractionEnabled = true
        cover.isAccessibilityElement = true
        cover.accessibilityIdentifier = "godot-session-privacy-cover"
        cover.text = text("Godot.Opening", "Opening your table…")
        // The cover stays constrained when hidden. Let the stage take spare height,
        // rather than stretching the status or toolbar to preserve the label's height.
        cover.setContentHuggingPriority(.fittingSizeLevel, for: .vertical)

        for child in [status, buttons, stage] {
            child.translatesAutoresizingMaskIntoConstraints = false
            view.addSubview(child)
        }
        for child in [engineContainer, cover] {
            child.translatesAutoresizingMaskIntoConstraints = false
            stage.addSubview(child)
        }
        let safe = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            status.topAnchor.constraint(equalTo: safe.topAnchor, constant: 12),
            status.leadingAnchor.constraint(equalTo: safe.leadingAnchor, constant: 16),
            status.trailingAnchor.constraint(equalTo: safe.trailingAnchor, constant: -16),
            // Status changes must not resize an established native viewport.
            status.heightAnchor.constraint(greaterThanOrEqualToConstant: status.font.lineHeight * 2),
            buttons.topAnchor.constraint(equalTo: status.bottomAnchor, constant: 8),
            buttons.leadingAnchor.constraint(equalTo: safe.leadingAnchor, constant: 12),
            buttons.trailingAnchor.constraint(equalTo: safe.trailingAnchor, constant: -12),
            stage.topAnchor.constraint(equalTo: buttons.bottomAnchor, constant: 12),
            stage.leadingAnchor.constraint(equalTo: safe.leadingAnchor),
            stage.trailingAnchor.constraint(equalTo: safe.trailingAnchor),
            stage.bottomAnchor.constraint(equalTo: safe.bottomAnchor),
            engineContainer.topAnchor.constraint(equalTo: stage.topAnchor),
            engineContainer.leadingAnchor.constraint(equalTo: stage.leadingAnchor),
            engineContainer.trailingAnchor.constraint(equalTo: stage.trailingAnchor),
            engineContainer.bottomAnchor.constraint(equalTo: stage.bottomAnchor),
            cover.topAnchor.constraint(equalTo: stage.topAnchor),
            cover.leadingAnchor.constraint(equalTo: stage.leadingAnchor),
            cover.trailingAnchor.constraint(equalTo: stage.trailingAnchor),
            cover.bottomAnchor.constraint(equalTo: stage.bottomAnchor),
        ])

        addChild(nativeController)
        let nativeView = nativeController.view!
        nativeView.translatesAutoresizingMaskIntoConstraints = false
        engineContainer.addSubview(nativeView)
        nativeConstraints = [
            nativeView.topAnchor.constraint(equalTo: engineContainer.topAnchor),
            nativeView.leadingAnchor.constraint(equalTo: engineContainer.leadingAnchor),
            nativeView.trailingAnchor.constraint(equalTo: engineContainer.trailingAnchor),
            nativeView.bottomAnchor.constraint(equalTo: engineContainer.bottomAnchor),
        ]
        NSLayoutConstraint.activate(nativeConstraints)
        nativeController.didMove(toParent: self)
        conceal()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        guard !closing else { return }
        onVisibilityChanged?(true)
    }

    override func viewWillDisappear(_ animated: Bool) {
        conceal()
        onVisibilityChanged?(false)
        super.viewWillDisappear(animated)
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        if !closing && (isBeingDismissed || presentingViewController == nil) {
            onUnexpectedDismissal?()
        }
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        if let establishedSize, stage.bounds.size != establishedSize, !closing {
            requestReturn(.standard)
        }
    }

    override func viewWillTransition(to size: CGSize, with coordinator: UIViewControllerTransitionCoordinator) {
        if establishedSize != nil && size != view.bounds.size { requestReturn(.standard) }
        super.viewWillTransition(to: size, with: coordinator)
    }

    override func traitCollectionDidChange(_ previousTraitCollection: UITraitCollection?) {
        super.traitCollectionDidChange(previousTraitCollection)
        if isViewLoaded { updateButtonLayout() }
    }

    override var keyCommands: [UIKeyCommand]? {
        [UIKeyCommand(input: UIKeyCommand.inputEscape, modifierFlags: [], action: #selector(leaveTable))]
    }

    override func accessibilityPerformEscape() -> Bool {
        requestReturn(.leave)
        return true
    }

    #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
    func sessionQualificationGeometry() -> [String: Any] {
        guard let child = nativeController.viewIfLoaded, let window = child.window else { return [:] }
        let rect = child.convert(child.bounds, to: window.screen.coordinateSpace)
        return ["coordinateSpace": "screen", "frame": [rect.minX, rect.minY, rect.width, rect.height],
                "bounds": [child.bounds.minX, child.bounds.minY, child.bounds.width, child.bounds.height],
                "outerCoverVisible": !cover.isHidden,
                "engineAccessibilityHidden": engineContainer.accessibilityElementsHidden,
                "surfaceAccessibilityHiddenByContainer": child.isDescendant(of: engineContainer) &&
                    engineContainer.accessibilityElementsHidden]
    }

    private func noteQualificationCoverTransition() {
        let now = ProcessInfo.processInfo.systemUptime
        if qualificationCoverTransitions < UInt64.max { qualificationCoverTransitions += 1 }
        else { qualificationCoverCounterExhausted = true }
        qualificationLastCoverTransition = now
        if cover.isHidden && qualificationFirstCoverRelease == nil { qualificationFirstCoverRelease = now }
    }

    func sessionQualificationCoverTiming() -> [String: Any] {
        return ["snapshotUptime": ProcessInfo.processInfo.systemUptime,
                "outerCoverVisible": !cover.isHidden, "coverTransitions": String(qualificationCoverTransitions),
                "counterExhausted": qualificationCoverCounterExhausted,
                "firstReleaseUptime": qualificationFirstCoverRelease as Any? ?? NSNull(),
                "lastTransitionUptime": qualificationLastCoverTransition as Any? ?? NSNull()]
    }

    func setSessionQualificationValue(_ document: String) {
        guard isViewLoaded else { return }
        // Reuse native chrome; no new layout, input target, or engine accessibility node.
        status.accessibilityValue = document
    }
    #endif

    func conceal() {
        guard isViewLoaded else { return }
        engineContainer.isUserInteractionEnabled = false
        engineContainer.accessibilityElementsHidden = true
        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        let qualificationCoverChanged = cover.isHidden
        #endif
        cover.isHidden = false
        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        if qualificationCoverChanged { noteQualificationCoverTransition() }
        #endif
        if !closing {
            let label = ready ? text("Godot.HandCovered", "Your hand is covered") : text("Godot.Opening", "Opening your table…")
            cover.text = label
            status.text = label
        }
    }

    /// Native keeps its own cover until a current concealed projection has actually been drawn.
    func allowNativePresentation() {
        guard !closing, !returnRequested, isViewLoaded else { return }
        ready = true
        if stage.bounds.width > 0 && stage.bounds.height > 0 { establishedSize = stage.bounds.size }
        status.text = text("Godot.TableReady", "Your table is ready")
        engineContainer.isUserInteractionEnabled = true
        // This visual surface has no mobile accessibility adapter. The native toolbar
        // returns to the complete standard-table controls on the same session.
        engineContainer.accessibilityElementsHidden = true
        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        let qualificationCoverChanged = !cover.isHidden
        #endif
        cover.isHidden = true
        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        if qualificationCoverChanged { noteQualificationCoverTransition() }
        #endif
    }

    func beginClosing() {
        closing = true
        returnRequested = true
        onVisibilityChanged = nil
        onReturn = nil
        onUnexpectedDismissal = nil
        conceal()
        guard isViewLoaded else { return }
        standardButton.isEnabled = false
        leaveButton.isEnabled = false
        let label = text("Godot.Closing", "Returning to the table…")
        status.text = label
        cover.text = label
    }

    /// Called after native dormancy, never as a substitute for native cleanup.
    func detachNativeController() {
        guard nativeController.parent === self else { return }
        nativeController.willMove(toParent: nil)
        NSLayoutConstraint.deactivate(nativeConstraints)
        nativeConstraints.removeAll()
        nativeController.viewIfLoaded?.removeFromSuperview()
        nativeController.removeFromParent()
    }

    @objc private func useStandardTable() { requestReturn(.standard) }
    @objc private func leaveTable() { requestReturn(.leave) }

    private func requestReturn(_ action: GodotTableReturn) {
        guard !closing, !returnRequested else { return }
        returnRequested = true
        conceal()
        onReturn?(action)
    }

    private func updateButtonLayout() {
        buttons.axis = traitCollection.preferredContentSizeCategory.isAccessibilityCategory ? .vertical : .horizontal
    }

    private func button(title: String, hint: String, action: Selector, identifier: String) -> UIButton {
        let result = UIButton(type: .system)
        var configuration = UIButton.Configuration.filled()
        configuration.title = title
        configuration.baseBackgroundColor = Self.paper
        configuration.baseForegroundColor = Self.ink
        configuration.contentInsets = NSDirectionalEdgeInsets(top: 12, leading: 16, bottom: 12, trailing: 16)
        configuration.titleLineBreakMode = .byWordWrapping
        result.configuration = configuration
        result.titleLabel?.font = UIFont.preferredFont(forTextStyle: .body)
        result.titleLabel?.adjustsFontForContentSizeCategory = true
        result.titleLabel?.numberOfLines = 0
        result.accessibilityHint = hint
        result.accessibilityIdentifier = identifier
        result.setContentHuggingPriority(.defaultHigh, for: .vertical)
        result.heightAnchor.constraint(greaterThanOrEqualToConstant: 48).isActive = true
        result.addTarget(self, action: action, for: .touchUpInside)
        return result
    }

    private func text(_ key: String, _ value: String) -> String {
        NSLocalizedString(key, value: value, comment: "Godot table presentation")
    }

    private static let ink = UIColor(red: 25 / 255, green: 21 / 255, blue: 38 / 255, alpha: 1)
    private static let paper = UIColor(red: 244 / 255, green: 240 / 255, blue: 232 / 255, alpha: 1)
}
