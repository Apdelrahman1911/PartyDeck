import PartyDeckKit
#if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
import Combine
#endif
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
    private let godotPort: GodotPresentationPort
    private var godotRegistration: IosGodotRegistration?
    private var reduceMotionObserver: NSObjectProtocol?
    private var contentSizeObserver: NSObjectProtocol?
    #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
    private(set) var qualificationObservation: GodotSessionQualificationObservation?
    #endif

    init() {
        actions = NativeActions()
        handle = IosAppHandle(transportFactory: IosLanTransportFactory(), nativeActions: actions)
        godotPort = GodotPresentationPort(presenter: handle.viewController)
        godotRegistration = handle.installGodotPort(port: godotPort)
        godotPort.attachRegistration(godotRegistration)
        actions.presentingViewController = handle.viewController
        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        qualificationObservation = GodotSessionQualificationObservation(handle: handle, port: godotPort)
        #endif
        refreshAccessibility()
        reduceMotionObserver = NotificationCenter.default.addObserver(
            forName: UIAccessibility.reduceMotionStatusDidChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in self?.refreshAccessibility() }
        }
        contentSizeObserver = NotificationCenter.default.addObserver(
            forName: UIContentSizeCategory.didChangeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in self?.refreshAccessibility() }
        }
    }

    func updateScenePhase(_ phase: ScenePhase) {
        let interactive = phase == .active
        godotPort.setSceneLifecycle(foreground: interactive, backgrounded: phase == .background)
        actions.setForeground(interactive)
        handle.setForeground(value: interactive)
        handle.setBackgrounded(value: phase == .background)
        if interactive { refreshAccessibility() }
    }

    #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
    func pollSessionQualification() { qualificationObservation?.poll() }
    #endif

    func refreshAccessibility() {
        handle.setSystemReduceMotion(value: UIAccessibility.isReduceMotionEnabled)
        let standardBody = UIFont.preferredFont(
            forTextStyle: .body,
            compatibleWith: UITraitCollection(preferredContentSizeCategory: .large)
        ).pointSize
        let preferredBody = UIFont.preferredFont(forTextStyle: .body).pointSize
        handle.setPresentationTextScale(value: Double(preferredBody / standardBody))
    }

    deinit {
        if let reduceMotionObserver {
            NotificationCenter.default.removeObserver(reduceMotionObserver)
        }
        if let contentSizeObserver {
            NotificationCenter.default.removeObserver(contentSizeObserver)
        }
        let retainedActions = actions
        let retainedHandle = handle
        let retainedGodotPort = godotPort
        let retainedGodotRegistration = godotRegistration
        if Thread.isMainThread {
            retainedGodotRegistration?.close()
            retainedHandle.close()
            retainedGodotPort.shutdown()
            retainedActions.close()
        } else {
            DispatchQueue.main.async {
                retainedGodotRegistration?.close()
                retainedHandle.close()
                retainedGodotPort.shutdown()
                retainedActions.close()
            }
        }
    }
}

private struct PartyDeckRoot: View {
    @ObservedObject var owner: PartyDeckOwner
    @Environment(\.scenePhase) private var scenePhase
    #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
    private let qualificationClock = Timer.publish(every: 0.2, on: .main, in: .common).autoconnect()
    #endif

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
            #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
            if scenePhase == .active, let observation = owner.qualificationObservation {
                SessionQualificationBadge(observation: observation)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                    .padding(.top, 2).padding(.trailing, 2)
                    .allowsHitTesting(false)
            }
            #endif
        }
        #if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
        .onReceive(qualificationClock) { _ in owner.pollSessionQualification() }
        #endif
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

#if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
private struct SessionQualificationBadge: View {
    @ObservedObject var observation: GodotSessionQualificationObservation
    var body: some View {
        Text("Q").font(.system(size: 10)).foregroundStyle(.gray)
            .accessibilityLabel("Production session qualification")
            .accessibilityValue(observation.document)
            .accessibilityIdentifier("partydeck-session-qualification")
    }
}
#endif
