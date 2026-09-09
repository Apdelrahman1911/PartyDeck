import PartyDeckKit
import SwiftUI
import UIKit

@main
@MainActor
struct PartyDeckApp: App {
    @StateObject private var owner = PartyDeckOwner()

    var body: some Scene {
        WindowGroup {
            PartyDeckRoot(owner: owner)
                .preferredColorScheme(.dark)
        }
    }
}

/// The scene retains the shared controller across SwiftUI updates and temporary interruptions.
@MainActor
private final class PartyDeckOwner: ObservableObject {
    let actions: NativeActions
    let handle: IosAppHandle
    private var reduceMotionObserver: NSObjectProtocol?

    init() {
        actions = NativeActions()
        handle = IosAppHandle(transportFactory: IosLanTransportFactory(), nativeActions: actions)
        actions.presentingViewController = handle.viewController
        refreshAccessibility()
        reduceMotionObserver = NotificationCenter.default.addObserver(
            forName: UIAccessibility.reduceMotionStatusDidChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in self?.refreshAccessibility() }
        }
    }

    func updateScenePhase(_ phase: ScenePhase) {
        let interactive = phase == .active
        actions.setForeground(interactive)
        handle.setForeground(value: interactive)
        handle.setBackgrounded(value: phase == .background)
        if interactive { refreshAccessibility() }
    }

    func refreshAccessibility() {
        handle.setSystemReduceMotion(value: UIAccessibility.isReduceMotionEnabled)
    }

    deinit {
        if let reduceMotionObserver {
            NotificationCenter.default.removeObserver(reduceMotionObserver)
        }
        let retainedActions = actions
        let retainedHandle = handle
        if Thread.isMainThread {
            retainedActions.close()
            retainedHandle.close()
        } else {
            DispatchQueue.main.async {
                retainedActions.close()
                retainedHandle.close()
            }
        }
    }
}

private struct PartyDeckRoot: View {
    @ObservedObject var owner: PartyDeckOwner
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ZStack {
            Color(red: 25 / 255, green: 21 / 255, blue: 38 / 255).ignoresSafeArea()
            ComposeContent(controller: owner.handle.viewController)
                .ignoresSafeArea()
                .accessibilityHidden(scenePhase != .active)
                .allowsHitTesting(scenePhase == .active)
            if scenePhase != .active {
                PrivacyCover()
                    .accessibilityIdentifier("native-privacy-cover")
            }
        }
        .onAppear { owner.updateScenePhase(scenePhase) }
        .onChange(of: scenePhase) { phase in
            owner.updateScenePhase(phase)
        }
    }
}

private struct ComposeContent: UIViewControllerRepresentable {
    let controller: UIViewController

    func makeUIViewController(context: Context) -> UIViewController { controller }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}
}

private struct PrivacyCover: View {
    var body: some View {
        ZStack {
            Color(red: 25 / 255, green: 21 / 255, blue: 38 / 255)
            VStack(spacing: 12) {
                Text("PartyDeck")
                    .font(.system(size: 38, weight: .semibold, design: .serif))
                    .foregroundStyle(Color(red: 244 / 255, green: 240 / 255, blue: 232 / 255))
                Text("THE TABLE CAN WAIT")
                    .font(.system(size: 12, weight: .semibold))
                    .tracking(2)
                    .foregroundStyle(Color(red: 214 / 255, green: 239 / 255, blue: 130 / 255))
            }
            .accessibilityElement(children: .combine)
        }
        .ignoresSafeArea()
    }
}
