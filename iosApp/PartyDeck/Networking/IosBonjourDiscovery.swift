import Foundation
import Network
import PartyDeckKit

/// Network.framework DNS-SD uses the system privacy prompt and never advertises credentials.
final class IosBonjourDiscovery {
    static let serviceType = "_partydeck._tcp"

    private let queue: DispatchQueue
    private let observer: () -> (any NativeLanObserver)?
    private var browser: NWBrowser?
    private var operationId: String?
    private var endpoints: [String: NWEndpoint] = [:]

    init(queue: DispatchQueue, observer: @escaping () -> (any NativeLanObserver)?) {
        self.queue = queue
        self.observer = observer
    }

    func start(operationId: String) {
        close()
        self.operationId = operationId
        let parameters = NWParameters.tcp
        parameters.includePeerToPeer = false
        parameters.prohibitedInterfaceTypes = [.cellular]
        let browser = NWBrowser(
            for: .bonjourWithTXTRecord(type: Self.serviceType, domain: nil),
            using: parameters
        )
        self.browser = browser
        browser.stateUpdateHandler = { [weak self, weak browser] state in
            guard let self, let browser, self.browser === browser else { return }
            switch state {
            case .ready:
                self.observer()?.onDiscoveryStarted(operationId: operationId)
            case .waiting(let error):
                if IosLanDriver.isPermissionFailure(error) {
                    self.fail(operationId, code: .permissionDenied, message: "Allow local network access to find games")
                }
            case .failed(let error):
                let code: TransportFailureCode = IosLanDriver.isPermissionFailure(error) ? .permissionDenied : .unavailable
                self.fail(operationId, code: code, message: "Local discovery is unavailable; use an invitation")
            case .cancelled:
                self.fail(operationId, code: .unavailable, message: "Local discovery stopped")
            default:
                break
            }
        }
        browser.browseResultsChangedHandler = { [weak self, weak browser] results, _ in
            guard let self, let browser, self.browser === browser else { return }
            var hosts: [DiscoveredHost] = []
            var currentEndpoints: [String: NWEndpoint] = [:]
            for result in results {
                guard hosts.count < 64 else { break }
                guard case let .service(name, type, domain, _) = result.endpoint,
                      type.trimmingCharacters(in: CharacterSet(charactersIn: ".")) == Self.serviceType,
                      domain == "local." || domain == "local",
                      !name.isEmpty, name.utf8.count <= 63, !Self.hasControlCharacters(name),
                      case let .bonjour(record) = result.metadata
                else { continue }
                let fields = record.dictionary
                guard fields["v"] == "1", let portText = fields["port"],
                      let port = UInt16(portText), port > 0
                else { continue }
                let displayName = fields["name"] ?? name
                guard !displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                      displayName.utf8.count <= 80, !Self.hasControlCharacters(displayName)
                else { continue }
                // NWConnection resolves this service endpoint, including its actual interface/port.
                let endpoint = LanEndpoint(host: "", port: Int32(port), serviceName: name)
                hosts.append(DiscoveredHost(serviceName: name, displayName: displayName, endpoint: endpoint))
                currentEndpoints[name] = result.endpoint
            }
            self.endpoints = currentEndpoints
            self.observer()?.onDiscoveryChanged(
                operationId: operationId,
                hosts: hosts.sorted { $0.serviceName < $1.serviceName }
            )
        }
        browser.start(queue: queue)
    }

    func endpoint(serviceName: String) -> NWEndpoint? { endpoints[serviceName] }

    func stop(operationId: String) {
        guard self.operationId == operationId else { return }
        close()
    }

    func close() {
        operationId = nil
        endpoints.removeAll()
        let previous = browser
        browser = nil
        previous?.stateUpdateHandler = nil
        previous?.browseResultsChangedHandler = nil
        previous?.cancel()
    }

    private func fail(_ operationId: String, code: TransportFailureCode, message: String) {
        guard self.operationId == operationId else { return }
        close()
        observer()?.onDiscoveryFailed(operationId: operationId, code: code, message: message)
    }

    static func hasControlCharacters(_ value: String) -> Bool {
        value.unicodeScalars.contains { CharacterSet.controlCharacters.contains($0) }
    }
}
