#if DEBUG && PARTYDECK_GODOT_SESSION_QUALIFICATION
import Foundation
import Combine
import PartyDeckKit
import UIKit

/// Opt-in observation of the real app. It has no authority/factory and no action or lifecycle API.
@MainActor
final class GodotSessionQualificationObservation: ObservableObject {
    private let handle: IosAppHandle
    private weak var port: GodotPresentationPort?
    @Published private(set) var document = ""
    private var installed = false
    private var sequence: UInt64 = 0

    init?(handle: IosAppHandle, port: GodotPresentationPort) {
        guard ProcessInfo.processInfo.arguments.contains("--partydeck-observe-godot-session") else { return nil }
        self.handle = handle
        self.port = port
        let activation = port.sessionQualificationObservation()
        if activation["activationValid"] as? Bool == true {
            installed = handle.enableSessionQualificationObservation()
        }
        poll()
    }

    func poll() {
        guard sequence < UInt64.max, let port else { return }
        sequence += 1
        var payload: [String: Any] = ["schemaVersion": 1, "observationSequence": String(sequence),
                                     "observationInstalled": installed, "port": port.sessionQualificationObservation()]
        if installed, let text = handle.sessionQualificationSnapshot(), let data = text.data(using: .utf8),
           data.count <= 8192, let state = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            payload["controller"] = state
        }
        // Keep the existing total observation limit. If added timing metadata
        // exceeds it, omit only that measurement explicitly; never drop privacy
        // fields or represent an omitted timing trace as zero elapsed time.
        var encodedData: Data? = nil
        if JSONSerialization.isValidJSONObject(payload) {
            encodedData = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        }
        if let data = encodedData, data.count > 32768,
           var portDocument = payload["port"] as? [String: Any],
           var native = portDocument["native"] as? [String: Any] {
            native["frameTiming"] = NSNull()
            native["frameTimingStatus"] = "payload_budget"
            portDocument["native"] = native
            payload["port"] = portDocument
            encodedData = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        }
        let document: String
        if let data = encodedData, data.count <= 32768,
            let encoded = String(data: data, encoding: .utf8) {
            document = encoded
        } else { document = "{\"schemaVersion\":1,\"observationError\":true}" }
        self.document = document
        port.setSessionQualificationValue(document)
    }
}
#endif
