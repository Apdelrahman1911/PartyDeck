import AVFoundation
import PartyDeckKit
import UIKit
import UniformTypeIdentifiers

/// UIKit presentation stays with the native scene; no invitation text is logged or persisted.
final class NativeActions: NSObject, IosNativeActions {
    weak var presentingViewController: UIViewController?
    private let feedbackService = NativeFeedback()
    private weak var scanner: QRScannerViewController?
    private var foreground = false
    private var closed = false

    var feedback: any IosNativeFeedback { feedbackService }

    var canScanInvitation: Bool {
        AVCaptureDevice.default(for: .video) != nil
    }

    func doCopyText(value: String) -> Bool {
        guard !closed, foreground else { return false }
        UIPasteboard.general.setItems(
            [[UTType.utf8PlainText.identifier: value]],
            options: [.localOnly: true, .expirationDate: Date(timeIntervalSinceNow: 120)]
        )
        return true
    }

    func shareText(value: String) -> Bool {
        guard let presenter = activePresenter() else { return false }
        let activity = UIActivityViewController(activityItems: [value], applicationActivities: nil)
        if let popover = activity.popoverPresentationController {
            popover.sourceView = presenter.view
            popover.sourceRect = CGRect(x: presenter.view.bounds.midX, y: presenter.view.bounds.midY, width: 1, height: 1)
            popover.permittedArrowDirections = []
        }
        presenter.present(activity, animated: !UIAccessibility.isReduceMotionEnabled)
        return true
    }

    func scanInvitation(result: any IosScanResult) -> Bool {
        guard scanner == nil, canScanInvitation, let presenter = activePresenter() else { return false }
        let scanner = QRScannerViewController { [weak self] value in
            self?.scanner = nil
            result.complete(value: value)
        }
        self.scanner = scanner
        scanner.setForeground(foreground)
        let navigation = UINavigationController(rootViewController: scanner)
        navigation.modalPresentationStyle = .fullScreen
        navigation.overrideUserInterfaceStyle = .dark
        presenter.present(navigation, animated: !UIAccessibility.isReduceMotionEnabled)
        return true
    }

    func setForeground(_ value: Bool) {
        guard !closed else { return }
        foreground = value
        scanner?.setForeground(value)
    }

    func close() {
        guard !closed else { return }
        closed = true
        foreground = false
        scanner?.cancelFromOwner()
        scanner = nil
        feedbackService.close()
        presentingViewController = nil
    }

    private func activePresenter() -> UIViewController? {
        guard !closed, foreground, var presenter = presentingViewController else { return nil }
        while let presented = presenter.presentedViewController {
            guard !presented.isBeingDismissed else { return nil }
            presenter = presented
        }
        guard presenter.viewIfLoaded?.window != nil, !presenter.isBeingPresented else { return nil }
        return presenter
    }
}
