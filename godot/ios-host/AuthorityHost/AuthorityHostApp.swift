import Combine
import SwiftUI
import UIKit

@main
struct AuthorityHostApp: App {
    @UIApplicationDelegateAdaptor(AuthorityAppDelegate.self) private var appDelegate
    @StateObject private var model = AuthorityModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            AuthorityScreen(model: model)
                .onChange(of: scenePhase) { phase in
                    model.setApplicationActive(phase == .active)
                }
        }
    }
}

// The application owns its entry point and scene lifecycle. Godot's export
// app delegate is never installed by the qualification host.
final class AuthorityAppDelegate: NSObject, UIApplicationDelegate {
    var window: UIWindow?
}

private struct AuthorityScreen: View {
    @ObservedObject var model: AuthorityModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var soundEnabled = true
    @ScaledMetric(relativeTo: .body) private var scaledBodySize: CGFloat = 17
    private let clock = Timer.publish(every: 0.2, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Last Light").font(.headline)
                    Text(model.mode.isEmpty ? "Choose your table" : "\(model.mode.uppercased()) table")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                if model.showEngine {
                    Button(model.pausedByUser ? "Resume" : "Pause", action: model.togglePause)
                        .accessibilityIdentifier("pause-table")
                    Button("Close", action: model.close)
                        .accessibilityIdentifier("close-table")
                }
            }
            if model.state == "idle" {
                VStack(spacing: 18) {
                    Text("Keep your hand hidden. Make your claim.\nDecide who to believe.")
                        .multilineTextAlignment(.center)
                    Button("Play in 2D") { start("2d") }
                        .accessibilityIdentifier("start-2d")
                    Button("Play in 3D") { start("3d") }
                        .accessibilityIdentifier("start-3d")
                    Toggle("Sound", isOn: $soundEnabled).frame(maxWidth: 240)
                    if model.referenceScenario {
                        Text("Repeatable comparison scenario")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if model.showEngine, let controller = model.runtime.viewController {
                AuthoritySurface(controller: controller, model: model)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                VStack(spacing: 10) {
                    Text(model.state == "closed" ? "Table closed" : "Table unavailable")
                        .font(.title2.bold())
                    Text("Relaunch the comparison to choose another table.")
                        .multilineTextAlignment(.center)
                    Button("Host +1") {
                        model.hostCounter += 1
                        model.poll()
                    }
                    .accessibilityIdentifier("host-counter-button")
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            if !model.errorMessage.isEmpty {
                Text(model.errorMessage).font(.caption).foregroundStyle(.secondary)
                    .accessibilityIdentifier("authority-error")
            }
            Text(model.state.capitalized)
                .font(.caption)
                .accessibilityLabel("Authority measurements")
                .accessibilityValue(model.observations)
                .accessibilityIdentifier("authority-metrics")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .buttonStyle(.bordered)
        .onReceive(clock) { _ in model.poll() }
    }

    private func start(_ mode: String) {
        let arguments = ProcessInfo.processInfo.arguments
        let textScale = arguments.contains("--text-scale=2") ? 2.0 :
            arguments.contains("--text-scale=1") ? 1.0 : min(2.0, max(1.0, Double(scaledBodySize) / 17.0))
        model.start(mode: mode, reduceMotion: reduceMotion, soundEnabled: soundEnabled, textScale: textScale)
    }
}

private struct AuthoritySurface: UIViewControllerRepresentable {
    let controller: UIViewController
    let model: AuthorityModel

    func makeUIViewController(context: Context) -> UIViewController { controller }
    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}
    func makeCoordinator() -> AuthorityModel { model }
    static func dismantleUIViewController(_ uiViewController: UIViewController, coordinator: AuthorityModel) {
        coordinator.close()
    }
}
