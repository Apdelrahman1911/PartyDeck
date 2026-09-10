import Combine
import SwiftUI
import UIKit

@main
struct RetainedHostApp: App {
    @UIApplicationDelegateAdaptor(RetainedAppDelegate.self) private var appDelegate
    @StateObject private var model = RetainedModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RetainedScreen(model: model)
                .onAppear { model.setApplicationActive(scenePhase == .active, backgrounded: scenePhase == .background) }
                .onChange(of: scenePhase) { phase in
                    model.setApplicationActive(phase == .active, backgrounded: phase == .background)
                }
        }
    }
}

// The native application remains the lifecycle owner for every entry.
final class RetainedAppDelegate: NSObject, UIApplicationDelegate { var window: UIWindow? }

private struct RetainedScreen: View {
    @ObservedObject var model: RetainedModel
    private let clock = Timer.publish(every: 0.2, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text("Retained Last Light").font(.headline)
                Spacer()
                if model.canProbeOldHandle {
                    Button("Old handle", action: model.probeOldHandle).accessibilityIdentifier("probe-old-handle")
                }
                Button("Host +1", action: model.countHostInteraction)
                    .accessibilityIdentifier("host-counter-button")
            }
            if model.showEngine {
                HStack {
                    Button(model.pausedByUser ? "Resume" : "Pause", action: model.togglePause)
                        .accessibilityIdentifier("pause-table")
                    Button("Close", action: model.close).accessibilityIdentifier("close-table")
                    Button("Switch", action: model.closeAndSwitch).accessibilityIdentifier("switch-table")
                    Button("Cycle", action: model.cycleFocus).accessibilityIdentifier("cycle-focus")
                }
            }
            if model.showEngine, let controller = model.viewController {
                RetainedSurface(controller: controller, model: model, presentationID: model.presentationID)
                    .id(model.presentationID)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                VStack(spacing: 18) {
                    Text(model.state == "dormant" ? "Native shell · engine dormant" : "Native shell")
                        .font(.title2.bold()).accessibilityIdentifier("retained-shell")
                    Button("Play in 2D") { model.start(mode: "2d") }
                        .accessibilityIdentifier("start-2d").disabled(!model.canEnter)
                    Button("Play in 3D") { model.start(mode: "3d") }
                        .accessibilityIdentifier("start-3d").disabled(!model.canEnter)
                }.frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            if !model.errorMessage.isEmpty {
                Text(model.errorMessage).font(.caption).accessibilityIdentifier("retained-error")
            }
            Text(model.state.capitalized).font(.caption)
                .accessibilityLabel("Retained engine measurements")
                .accessibilityValue(model.observations)
                .accessibilityIdentifier("retained-metrics")
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .buttonStyle(.bordered)
        .onReceive(clock) { _ in model.poll() }
    }
}

private struct RetainedSurface: UIViewControllerRepresentable {
    let controller: UIViewController
    let model: RetainedModel
    let presentationID: String

    func makeUIViewController(context: Context) -> UIViewController { controller }
    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}
    func makeCoordinator() -> SurfaceOwner { SurfaceOwner(model: model, presentationID: presentationID) }
    static func dismantleUIViewController(_ uiViewController: UIViewController, coordinator: SurfaceOwner) {
        coordinator.model?.surfaceDetached(presentationID: coordinator.presentationID)
    }

    @MainActor
    final class SurfaceOwner {
        weak var model: RetainedModel?
        let presentationID: String
        init(model: RetainedModel, presentationID: String) { self.model = model; self.presentationID = presentationID }
    }
}
