import Darwin
import Foundation
import Network
import PartyDeckKit

/// Native TLS sockets and Bonjour. Its serial queue owns every Network.framework handle.
final class IosLanDriver: NSObject, NativeLanDriver {
    private let queue = DispatchQueue(label: "dev.partydeck.transport.io", qos: .utility)
    private var observer: (any NativeLanObserver)?
    private var closed = false
    private var host: HostHandle?
    private var connections: [String: ConnectionHandle] = [:]
    private lazy var discovery = IosBonjourDiscovery(queue: queue) { [weak self] in self?.observer }

    private static let maximumConnections = 8
    private static let readChunkBytes = 16_384
    private static let maximumWireBytes = 65_540
    private static let handshakeTimeout: TimeInterval = 10

    func attach(observer: any NativeLanObserver) {
        queue.sync {
            precondition(self.observer == nil, "The LAN driver is already attached")
            self.observer = observer
        }
    }

    func startHost(operationId: String, displayName: String) {
        queue.async {
            guard !self.closed, self.host == nil else {
                self.observer?.onHostFailed(operationId: operationId, code: .busy, message: "The host listener is unavailable")
                return
            }
            let handle = HostHandle(id: operationId, displayName: displayName)
            self.host = handle
            do {
                let identity = try IosTlsIdentity.generate()
                handle.identity = identity
                let listener = try NWListener(using: Self.parameters(tls: identity.serverOptions()))
                handle.listener = listener
                listener.newConnectionHandler = { [weak self, weak handle] connection in
                    guard let self, let handle, self.host === handle, handle.ready, !self.closed,
                          self.connections.count < Self.maximumConnections
                    else { connection.cancel(); return }
                    let incoming = ConnectionHandle(connection: connection, operationId: nil, hostId: handle.id)
                    self.connections[incoming.id] = incoming
                    self.start(incoming)
                }
                listener.stateUpdateHandler = { [weak self, weak handle] state in
                    guard let self, let handle, self.host === handle, !self.closed else { return }
                    switch state {
                    case .ready:
                        self.hostReady(handle)
                    case .waiting(let error):
                        if Self.isPermissionFailure(error) {
                            self.failHost(handle, code: .permissionDenied, message: "Allow local network access to host a game")
                        }
                    case .failed(let error):
                        self.failHost(handle, code: Self.failureCode(error), message: "The game could not start on this network")
                    case .cancelled:
                        self.failHost(handle, code: .closed, message: "The host listener stopped")
                    default:
                        break
                    }
                }
                let timeout = DispatchWorkItem { [weak self, weak handle] in
                    guard let self, let handle, self.host === handle, !handle.ready else { return }
                    self.failHost(handle, code: .timedOut, message: "The host listener did not become ready")
                }
                handle.timeout = timeout
                self.queue.asyncAfter(deadline: .now() + Self.handshakeTimeout, execute: timeout)
                listener.start(queue: self.queue)
            } catch {
                self.failHost(handle, code: .unavailable, message: "A secure host identity could not be created")
            }
        }
    }

    private func hostReady(_ handle: HostHandle) {
        guard !handle.ready, let listener = handle.listener, let port = listener.port,
              let identity = handle.identity
        else { return }
        let addresses = Self.localEndpoints(port: port.rawValue, serviceName: handle.serviceName)
        guard !addresses.isEmpty else {
            failHost(handle, code: .unavailable, message: "Connect to a local Wi-Fi network before hosting")
            return
        }
        handle.ready = true
        handle.timeout?.cancel()
        listener.service = NWListener.Service(
            name: handle.serviceName,
            type: IosBonjourDiscovery.serviceType,
            txtRecord: NWTXTRecord([
                "v": "1", "name": handle.displayName, "port": String(port.rawValue),
            ])
        )
        observer?.onHostReady(
            operationId: handle.id,
            info: HostInfo(
                displayName: handle.displayName,
                serviceName: handle.serviceName,
                endpoints: addresses,
                certificateSha256: identity.certificateSha256
            )
        )
    }

    func stopHost(hostId: String) {
        queue.async { self.stopHostOnQueue(hostId: hostId) }
    }

    private func stopHostOnQueue(hostId: String) {
        if let handle = host, handle.id == hostId {
            host = nil
            handle.timeout?.cancel()
            handle.listener?.stateUpdateHandler = nil
            handle.listener?.newConnectionHandler = nil
            handle.listener?.cancel()
            handle.listener = nil
            handle.identity = nil
        }
        for connection in Array(connections.values) where connection.hostId == hostId {
            finish(connection, code: nil, message: nil)
        }
    }

    private func failHost(_ handle: HostHandle, code: TransportFailureCode, message: String) {
        guard host === handle else { return }
        observer?.onHostFailed(operationId: handle.id, code: code, message: message)
        stopHostOnQueue(hostId: handle.id)
    }

    func connect(operationId: String, endpoint: LanEndpoint, certificateSha256: String) {
        queue.async {
            guard !self.closed, self.connections.count < Self.maximumConnections else {
                self.observer?.onConnectFailed(operationId: operationId, code: .busy, message: "Too many connections")
                return
            }
            do {
                let serviceDestination: NWEndpoint? = endpoint.serviceName.map { service in
                    self.discovery.endpoint(serviceName: service) ?? .service(
                        name: service, type: IosBonjourDiscovery.serviceType, domain: "local.", interface: nil
                    )
                }
                let destination: NWEndpoint
                if endpoint.host.isEmpty, let serviceDestination {
                    destination = serviceDestination
                } else {
                    guard let port = NWEndpoint.Port(rawValue: UInt16(endpoint.port)) else {
                        self.observer?.onConnectFailed(operationId: operationId, code: .unavailable, message: "Invalid host endpoint")
                        return
                    }
                    destination = .hostPort(host: NWEndpoint.Host(endpoint.host), port: port)
                }
                let tls = try IosTlsIdentity.clientOptions(certificateSha256: certificateSha256, queue: self.queue)
                let connection = NWConnection(to: destination, using: Self.parameters(tls: tls))
                let handle = ConnectionHandle(connection: connection, operationId: operationId, hostId: nil)
                handle.certificateSha256 = certificateSha256
                if !endpoint.host.isEmpty { handle.fallbackDestination = serviceDestination }
                self.connections[handle.id] = handle
                self.start(handle)
            } catch {
                self.observer?.onConnectFailed(operationId: operationId, code: .authenticationFailed, message: "A complete host certificate fingerprint is required")
            }
        }
    }

    private func start(_ handle: ConnectionHandle) {
        let connection = handle.connection
        connection.stateUpdateHandler = { [weak self, weak handle, weak connection] state in
            guard let self, let handle, let connection, self.connections[handle.id] === handle,
                  handle.connection === connection
            else { return }
            switch state {
            case .ready:
                guard !handle.ready else { return }
                handle.ready = true
                handle.timeout?.cancel()
                handle.fallbackTimeout?.cancel()
                handle.fallbackDestination = nil
                if let operationId = handle.operationId {
                    self.observer?.onConnected(operationId: operationId, connectionId: handle.id)
                } else if let hostId = handle.hostId {
                    self.observer?.onIncomingConnection(hostId: hostId, connectionId: handle.id)
                }
                self.receive(handle)
            case .waiting(let error):
                if Self.isPermissionFailure(error) {
                    self.finish(handle, code: .permissionDenied, message: "Allow local network access to join a game")
                } else if Self.failureCode(error) == .authenticationFailed {
                    self.finish(handle, code: .authenticationFailed, message: "The host identity did not match the invitation")
                } else {
                    self.retryService(handle)
                }
            case .failed(let error):
                let code = Self.failureCode(error)
                if code != .authenticationFailed, code != .permissionDenied, self.retryService(handle) { return }
                let message = code == .authenticationFailed
                    ? "The host identity did not match the invitation"
                    : "The secure connection was interrupted"
                self.finish(handle, code: code, message: message)
            case .cancelled:
                self.finish(handle, code: nil, message: nil)
            default:
                break
            }
        }
        if handle.timeout == nil {
            let timeout = DispatchWorkItem { [weak self, weak handle] in
                guard let self, let handle, self.connections[handle.id] === handle, !handle.ready else { return }
                self.finish(handle, code: .timedOut, message: "The secure connection did not become ready")
            }
            handle.timeout = timeout
            queue.asyncAfter(deadline: .now() + Self.handshakeTimeout, execute: timeout)
        }
        if handle.fallbackDestination != nil {
            // A stale IP may stay in TCP preparation for a long time. Leave time to resolve
            // its Bonjour identity, without extending the original handshake deadline.
            let fallback = DispatchWorkItem { [weak self, weak handle, weak connection] in
                guard let self, let handle, let connection, self.connections[handle.id] === handle,
                      handle.connection === connection
                else { return }
                self.retryService(handle)
            }
            handle.fallbackTimeout = fallback
            queue.asyncAfter(deadline: .now() + 4, execute: fallback)
        }
        connection.start(queue: queue)
    }

    @discardableResult
    private func retryService(_ handle: ConnectionHandle) -> Bool {
        guard connections[handle.id] === handle, !handle.ready, !closed,
              let destination = handle.fallbackDestination, let pin = handle.certificateSha256
        else { return false }
        handle.fallbackDestination = nil
        handle.fallbackTimeout?.cancel()
        handle.fallbackTimeout = nil
        handle.connection.stateUpdateHandler = nil
        handle.connection.cancel()
        do {
            // Discovery is only a candidate address; it cannot replace the invitation's pin.
            let tls = try IosTlsIdentity.clientOptions(certificateSha256: pin, queue: queue)
            handle.connection = NWConnection(to: destination, using: Self.parameters(tls: tls))
            start(handle)
        } catch {
            finish(handle, code: .authenticationFailed, message: "The host identity did not match the invitation")
        }
        return true
    }

    private func receive(_ handle: ConnectionHandle) {
        handle.connection.receive(minimumIncompleteLength: 1, maximumLength: Self.readChunkBytes) { [weak self, weak handle] data, _, complete, error in
            guard let self, let handle, self.connections[handle.id] === handle else { return }
            if let data, !data.isEmpty {
                let accepted = self.observer?.onConnectionBytes(connectionId: handle.id, bytes: Self.kotlinBytes(data)) ?? false
                if !accepted {
                    self.finish(handle, code: .ioError, message: "The receive queue is full")
                    return
                }
            }
            if let error {
                self.finish(handle, code: Self.failureCode(error), message: "The connection was interrupted")
            } else if complete {
                self.finish(handle, code: nil, message: nil)
            } else {
                self.receive(handle)
            }
        }
    }

    func send(connectionId: String, operationId: String, bytes: KotlinByteArray) {
        queue.async {
            guard let handle = self.connections[connectionId], handle.ready, !self.closed else {
                self.observer?.onSendComplete(operationId: operationId, code: .closed, message: "The connection is closed")
                return
            }
            guard bytes.size > 0, Int(bytes.size) <= Self.maximumWireBytes else {
                self.observer?.onSendComplete(operationId: operationId, code: .messageTooLarge, message: "Message exceeds the transport limit")
                return
            }
            let data = Self.data(bytes)
            handle.connection.send(content: data, completion: .contentProcessed { [weak self, weak handle] error in
                guard let self else { return }
                if let error {
                    let code = Self.failureCode(error)
                    self.observer?.onSendComplete(operationId: operationId, code: code, message: "The message could not be sent")
                    if let handle { self.finish(handle, code: code, message: "The connection was interrupted") }
                } else {
                    self.observer?.onSendComplete(operationId: operationId, code: nil, message: nil)
                }
            })
        }
    }

    func cancelConnect(operationId: String) {
        queue.async {
            if let handle = self.connections.values.first(where: { $0.operationId == operationId }) {
                self.finish(handle, code: nil, message: nil)
            }
        }
    }

    func closeConnection(connectionId: String) {
        queue.async {
            if let handle = self.connections[connectionId] { self.finish(handle, code: nil, message: nil) }
        }
    }

    private func finish(_ handle: ConnectionHandle, code: TransportFailureCode?, message: String?) {
        guard connections[handle.id] === handle else { return }
        connections.removeValue(forKey: handle.id)
        handle.timeout?.cancel()
        handle.fallbackTimeout?.cancel()
        handle.connection.stateUpdateHandler = nil
        handle.connection.cancel()
        if handle.ready {
            observer?.onConnectionClosed(connectionId: handle.id, code: code, message: message)
        } else if let operationId = handle.operationId {
            observer?.onConnectFailed(operationId: operationId, code: code ?? .closed, message: message ?? "Connection cancelled")
        }
    }

    func startDiscovery(operationId: String) {
        queue.async {
            guard !self.closed else { return }
            self.discovery.start(operationId: operationId)
        }
    }

    func stopDiscovery(operationId: String) {
        queue.async { self.discovery.stop(operationId: operationId) }
    }

    func close() {
        queue.async {
            guard !self.closed else { return }
            self.closed = true
            if let host = self.host { self.stopHostOnQueue(hostId: host.id) }
            for handle in Array(self.connections.values) { self.finish(handle, code: nil, message: nil) }
            self.discovery.close()
            // Break the Swift driver -> Kotlin observer -> driver ownership cycle explicitly.
            self.observer = nil
        }
    }

    private static func parameters(tls: NWProtocolTLS.Options) -> NWParameters {
        let tcp = NWProtocolTCP.Options()
        tcp.enableKeepalive = true
        tcp.keepaliveIdle = 5
        tcp.keepaliveInterval = 5
        tcp.keepaliveCount = 3
        tcp.noDelay = true
        let parameters = NWParameters(tls: tls, tcp: tcp)
        parameters.includePeerToPeer = false
        parameters.prohibitedInterfaceTypes = [.cellular]
        return parameters
    }

    static func isPermissionFailure(_ error: NWError) -> Bool {
        switch error {
        case .posix(let code): return code == .EACCES || code == .EPERM
        case .dns(let code): return code == kDNSServiceErr_PolicyDenied
        default: return false
        }
    }

    private static func failureCode(_ error: NWError) -> TransportFailureCode {
        if isPermissionFailure(error) { return .permissionDenied }
        switch error {
        case .tls: return .authenticationFailed
        case .posix(let code) where code == .ETIMEDOUT: return .timedOut
        default: return .unavailable
        }
    }

    private static func kotlinBytes(_ data: Data) -> KotlinByteArray {
        let bytes = KotlinByteArray(size: Int32(data.count))
        for (index, value) in data.enumerated() {
            bytes.set(index: Int32(index), value: Int8(bitPattern: value))
        }
        return bytes
    }

    private static func data(_ bytes: KotlinByteArray) -> Data {
        var data = Data(count: Int(bytes.size))
        data.withUnsafeMutableBytes { (buffer: UnsafeMutableRawBufferPointer) in
            for index in 0..<Int(bytes.size) { buffer[index] = UInt8(bitPattern: bytes.get(index: Int32(index))) }
        }
        return data
    }

    /// Enumerate broadcast-capable LAN interfaces; never assume that Wi-Fi is named en0.
    private static func localEndpoints(port: UInt16, serviceName: String) -> [LanEndpoint] {
        var first: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&first) == 0, let initial = first else { return [] }
        defer { freeifaddrs(initial) }
        var cursor: UnsafeMutablePointer<ifaddrs>? = initial
        var addresses = Set<String>()
        while let item = cursor {
            defer { cursor = item.pointee.ifa_next }
            let flags = item.pointee.ifa_flags
            guard flags & UInt32(IFF_UP) != 0, flags & UInt32(IFF_BROADCAST) != 0,
                  flags & UInt32(IFF_LOOPBACK) == 0, let address = item.pointee.ifa_addr
            else { continue }
            let family = Int32(address.pointee.sa_family)
            guard family == AF_INET || family == AF_INET6 else { continue }
            var text = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            guard getnameinfo(address, socklen_t(address.pointee.sa_len), &text, socklen_t(text.count), nil, 0, NI_NUMERICHOST) == 0 else { continue }
            let host = String(cString: text)
            let lower = host.lowercased()
            if lower.hasPrefix("fe8") || lower.hasPrefix("fe9") || lower.hasPrefix("fea") || lower.hasPrefix("feb") || lower.hasPrefix("169.254.") { continue }
            addresses.insert(host)
        }
        #if targetEnvironment(simulator)
        if addresses.isEmpty { addresses.insert("127.0.0.1") }
        #endif
        return addresses.sorted { left, right in
            if left.contains(":") != right.contains(":") { return !left.contains(":") }
            return left < right
        }.map { LanEndpoint(host: $0, port: Int32(port), serviceName: serviceName) }
    }

    private final class HostHandle {
        let id: String
        let displayName: String
        let serviceName = "partydeck-" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(12).lowercased()
        var listener: NWListener?
        var identity: IosTlsIdentity?
        var ready = false
        var timeout: DispatchWorkItem?
        init(id: String, displayName: String) { self.id = id; self.displayName = displayName }
    }

    private final class ConnectionHandle {
        let id = UUID().uuidString.lowercased()
        var connection: NWConnection
        let operationId: String?
        let hostId: String?
        var ready = false
        var timeout: DispatchWorkItem?
        var fallbackTimeout: DispatchWorkItem?
        var fallbackDestination: NWEndpoint?
        var certificateSha256: String?
        init(connection: NWConnection, operationId: String?, hostId: String?) {
            self.connection = connection
            self.operationId = operationId
            self.hostId = hostId
        }
    }
}
