import Combine
import SwiftUI
import UIKit

@main
struct ProbeHostApp: App {
    @UIApplicationDelegateAdaptor(ProbeAppDelegate.self) private var appDelegate
    @StateObject private var model = ProbeModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ProbeScreen(model: model)
                .onChange(of: scenePhase) { phase in
                    model.setApplicationActive(phase == .active)
                }
        }
    }
}

// Owns the application entry point. Godot's export AppDelegate is never installed.
final class ProbeAppDelegate: NSObject, UIApplicationDelegate {
    var window: UIWindow?
}

@MainActor
final class ProbeModel: ObservableObject {
    let runtime = PDGodotRuntime()
    @Published var showEngine = false
    @Published var state = "idle"
    @Published var observations = "{}"
    @Published var iterations = 0
    @Published var hostCounter = 0
    @Published var errorMessage = ""
    @Published var pausedByUser = false
    private var applicationActive = true
    private var reopenDenied = false

    init() {
        // Explicit qualification inputs exercise both possible shell policies.
        // Ordinary launches retain UIKit's actual current value.
        switch ProcessInfo.processInfo.arguments.first(where: { $0.hasPrefix("--host-idle-timer=") }) ?? "" {
        case "--host-idle-timer=on": UIApplication.shared.isIdleTimerDisabled = true
        case "--host-idle-timer=off": UIApplication.shared.isIdleTimerDisabled = false
        default: break
        }
    }

    var sceneName: String {
        switch requestedScene {
        case "2d": return "Last Light 2D fixture"
        case "3d": return "Last Light 3D fixture"
        default: return "Lifecycle diagnostic"
        }
    }

    private var requestedScene: String {
        ProcessInfo.processInfo.arguments.first(where: { $0.hasPrefix("--scene=") })?
            .replacingOccurrences(of: "--scene=", with: "") ?? "diagnostic"
    }

    func start() {
        do {
            let inputs = try launchInputs()
            try runtime.prepare(withProjectPath: inputs.project, packPath: inputs.pack, launchDocument: inputs.document)
            if ProcessInfo.processInfo.arguments.contains("--close-during-initialization") {
                runtime.requestCloseAfterSetupForProbe()
            }
            if ProcessInfo.processInfo.arguments.contains("--close-before-start") {
                runtime.close()
            } else {
                runtime.setForeground(applicationActive && !pausedByUser)
                showEngine = true
            }
            poll()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func tryReopen() {
        do {
            let inputs = try launchInputs()
            let attemptedRuntime = PDGodotRuntime()
            try attemptedRuntime.prepare(withProjectPath: inputs.project, packPath: inputs.pack, launchDocument: inputs.document)
            errorMessage = "Unexpectedly permitted another engine presentation."
        } catch {
            reopenDenied = true
            errorMessage = error.localizedDescription
        }
        poll()
    }

    func togglePause() {
        pausedByUser.toggle()
        runtime.setForeground(applicationActive && !pausedByUser)
        poll()
    }

    func setApplicationActive(_ active: Bool) {
        applicationActive = active
        runtime.setForeground(active && !pausedByUser)
    }

    func poll() {
        var measured = runtime.snapshot()
        state = measured["state"] as? String ?? "unknown"
        iterations = (measured["iterations"] as? NSNumber)?.intValue ?? 0
        measured["hostCounter"] = hostCounter
        measured["reopenDenied"] = reopenDenied
        measured["scene"] = requestedScene
        if let bytes = try? JSONSerialization.data(withJSONObject: measured, options: [.sortedKeys]),
           let document = String(data: bytes, encoding: .utf8) {
            observations = document
            if state == "closed" || state == "failed" {
                if let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
                    try? bytes.write(to: directory.appendingPathComponent("probe-runtime.json"), options: .atomic)
                }
            }
        }
        if state == "closed" || state == "failed" {
            showEngine = false
        }
    }

    private func launchInputs() throws -> (project: String, pack: String?, document: String) {
        guard let resources = Bundle.main.resourceURL,
              let fixtureURL = Bundle.main.url(forResource: "Launch", withExtension: "json", subdirectory: "ProbeResources"),
              var fixture = try JSONSerialization.jsonObject(with: Data(contentsOf: fixtureURL)) as? [String: Any] else {
            throw ProbeError.missingResources
        }
        fixture["presentationId"] = "ios-probe-\(UUID().uuidString)"
        fixture["presentationMode"] = requestedScene == "3d" ? "3d" : "2d"
        let document = String(decoding: try JSONSerialization.data(withJSONObject: fixture, options: [.sortedKeys]), as: UTF8.self)
        if requestedScene == "2d" || requestedScene == "3d" {
            let pack = resources.appendingPathComponent("ProbeResources/partydeck-last-light.pck")
            guard FileManager.default.fileExists(atPath: pack.path) else {
                throw ProbeError.missingPack
            }
            return (resources.path, pack.path, document)
        }
        if ProcessInfo.processInfo.arguments.contains("--missing-main-scene") {
            return (resources.appendingPathComponent("ProbeResources/MissingMainScene").path, nil, document)
        }
        return (resources.appendingPathComponent("ProbeScene").path, nil, document)
    }
}

private enum ProbeError: LocalizedError {
    case missingResources
    case missingPack

    var errorDescription: String? {
        switch self {
        case .missingResources: return "The diagnostic resources are missing."
        case .missingPack: return "Build this probe with the verified Last Light pack to open that presentation."
        }
    }
}

private struct ProbeScreen: View {
    @ObservedObject var model: ProbeModel
    private let clock = Timer.publish(every: 0.2, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Godot iOS probe").font(.title2.bold())
                    Text(model.sceneName).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Host +1") {
                    model.hostCounter += 1
                    model.poll()
                }
                .accessibilityIdentifier("host-counter-button")
            }
            if model.state == "idle" {
                Button("Start scene", action: model.start)
                    .accessibilityIdentifier("start-scene")
            } else if model.state == "running" || model.state == "paused" || model.state == "prepared" {
                HStack {
                    Button(model.pausedByUser ? "Resume" : "Pause", action: model.togglePause)
                        .accessibilityIdentifier("pause-scene")
                    Button("Close", action: model.runtime.close)
                        .accessibilityIdentifier("close-scene")
                    Button("Close during draw", action: model.runtime.requestCloseDuringNextDrawForProbe)
                        .accessibilityIdentifier("close-during-draw")
                        .disabled(model.state != "running")
                }
            } else if model.state == "closed" {
                Button("Try reopening", action: model.tryReopen)
                    .accessibilityIdentifier("try-reopen")
            }

            if model.showEngine, let controller = model.runtime.viewController {
                GodotSurface(controller: controller, runtime: model.runtime)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                VStack(spacing: 10) {
                    Text(model.state == "closed" ? "Scene closed" : "Host owns this screen")
                        .font(.title3.bold())
                    Text("The native controls stay available before and after the engine presentation.")
                        .multilineTextAlignment(.center)
                        .font(.body)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .padding()
                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
            }

            if model.state == "running" {
                Button("Cycle focus") {
                    model.runtime.setForeground(false)
                    model.runtime.setForeground(true)
                }
                .accessibilityIdentifier("cycle-focus")
            }
            HStack {
                Text(model.state.capitalized).accessibilityIdentifier("probe-state")
                Spacer()
                Text("Iterations \(model.iterations) · Host \(model.hostCounter)")
                    .font(.caption.monospacedDigit())
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Probe measurements")
            .accessibilityValue(model.observations)
            .accessibilityIdentifier("probe-metrics")
            if !model.errorMessage.isEmpty {
                Text(model.errorMessage).font(.caption).foregroundStyle(.secondary)
                    .accessibilityIdentifier("probe-error")
            }
        }
        .padding(16)
        .buttonStyle(.bordered)
        .onReceive(clock) { _ in model.poll() }
    }
}

private struct GodotSurface: UIViewControllerRepresentable {
    let controller: UIViewController
    let runtime: PDGodotRuntime

    func makeUIViewController(context: Context) -> UIViewController { controller }
    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}
    func makeCoordinator() -> PDGodotRuntime { runtime }
    static func dismantleUIViewController(_ uiViewController: UIViewController, coordinator: PDGodotRuntime) {
        coordinator.close()
    }
}
