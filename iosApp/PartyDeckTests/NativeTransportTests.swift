import Foundation
import PartyDeckKit
import XCTest
@testable import PartyDeck

/// Real Network.framework TLS between two independent native drivers on the simulator loopback.
final class NativeTransportTests: XCTestCase {
    func testPinnedTLSExchangesOrderedFramesAndClosesBothPeers() async throws {
        let first = framed(Data("first move".utf8))
        let second = framed(Data((0..<20_000).map { UInt8($0 % 251) }))
        let reply = framed(Data("accepted".utf8))
        let expected = first + second
        let hostProbe = NativeProbe(expectedBytes: expected.count, expectedWrites: 1)
        let clientProbe = NativeProbe(expectedBytes: reply.count, expectedWrites: 2)
        let host = IosLanDriver()
        let client = IosLanDriver()
        host.attach(observer: hostProbe)
        client.attach(observer: clientProbe)
        defer {
            client.close()
            host.close()
        }

        host.startHost(operationId: "ordered-host", displayName: "Native TLS test")
        await fulfillment(of: [hostProbe.hostReady], timeout: 20)
        let info = try XCTUnwrap(hostProbe.snapshot.hostInfo)
        let port = try XCTUnwrap(info.endpoints.first?.port)
        let endpoint = LanEndpoint(host: "127.0.0.1", port: port, serviceName: nil)

        client.connect(operationId: "ordered-client", endpoint: endpoint, certificateSha256: info.certificateSha256)
        await fulfillment(of: [clientProbe.connected, hostProbe.incoming], timeout: 20)
        let clientID = try XCTUnwrap(clientProbe.snapshot.outgoingID)
        let hostID = try XCTUnwrap(hostProbe.snapshot.incomingID)

        client.send(connectionId: clientID, operationId: "first-frame", bytes: kotlinBytes(first))
        client.send(connectionId: clientID, operationId: "second-frame", bytes: kotlinBytes(second))
        await fulfillment(of: [hostProbe.bytesReceived, clientProbe.writesCompleted], timeout: 10)
        XCTAssertEqual(hostProbe.snapshot.received[hostID], expected, "TLS chunks must preserve complete frame order and content.")
        XCTAssertTrue(clientProbe.snapshot.writeFailures.isEmpty)

        host.send(connectionId: hostID, operationId: "reply-frame", bytes: kotlinBytes(reply))
        await fulfillment(of: [clientProbe.bytesReceived, hostProbe.writesCompleted], timeout: 10)
        XCTAssertEqual(clientProbe.snapshot.received[clientID], reply)
        XCTAssertTrue(hostProbe.snapshot.writeFailures.isEmpty)

        client.closeConnection(connectionId: clientID)
        await fulfillment(of: [clientProbe.connectionClosed, hostProbe.connectionClosed], timeout: 10)
        // Terminal and repeated close calls are intentionally harmless.
        client.closeConnection(connectionId: clientID)
        host.stopHost(hostId: "ordered-host")
        host.stopHost(hostId: "ordered-host")
    }

    func testWrongCertificatePinFailsBeforeOutgoingConnectionIsAnnounced() async throws {
        let hostProbe = NativeProbe()
        let clientProbe = NativeProbe()
        clientProbe.connected.isInverted = true
        let host = IosLanDriver()
        let client = IosLanDriver()
        host.attach(observer: hostProbe)
        client.attach(observer: clientProbe)
        defer {
            client.close()
            host.close()
        }

        host.startHost(operationId: "pin-host", displayName: "Native pin test")
        await fulfillment(of: [hostProbe.hostReady], timeout: 20)
        let info = try XCTUnwrap(hostProbe.snapshot.hostInfo)
        let port = try XCTUnwrap(info.endpoints.first?.port)
        var incorrectPin = info.certificateSha256
        incorrectPin.replaceSubrange(incorrectPin.startIndex...incorrectPin.startIndex, with: incorrectPin.first == "0" ? "1" : "0")

        client.connect(
            operationId: "wrong-pin-client",
            endpoint: LanEndpoint(host: "127.0.0.1", port: port, serviceName: nil),
            certificateSha256: incorrectPin
        )
        await fulfillment(of: [clientProbe.connectFailed], timeout: 20)
        await fulfillment(of: [clientProbe.connected], timeout: 0.5)
        XCTAssertEqual(clientProbe.snapshot.connectFailure?.name, "AUTHENTICATION_FAILED")
        XCTAssertNil(clientProbe.snapshot.outgoingID)
        XCTAssertTrue(clientProbe.snapshot.received.isEmpty, "An untrusted host cannot deliver application bytes.")
    }

    /// The macOS test script owns the JVM process; the simulator only receives its public endpoint and pin.
    func testSwiftAndJavaTLSInteroperabilityInBothDirections() async throws {
        let environment = ProcessInfo.processInfo.environment
        guard let manifestJSON = environment["PARTYDECK_INTEROP_MANIFEST"], !manifestJSON.isEmpty else {
            if environment["PARTYDECK_INTEROP_REQUIRED"] == "1" {
                XCTFail("CI requires the Java TLS fixture manifest to reach the native test runner.")
                throw InteropFixtureError.missingManifest
            }
            throw XCTSkip("Run scripts/validate-ios-app.sh with its external Java TLS fixture.")
        }
        let manifest = try JSONDecoder().decode(InteropManifest.self, from: Data(manifestJSON.utf8))
        guard manifest.version == 1, manifest.port > 0, manifest.port <= 65_535,
              manifest.certificateSha256.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil else {
            XCTFail("The external TLS fixture manifest must contain a valid version, port, and certificate pin.")
            throw InteropFixtureError.invalidManifest
        }

        let forwardRequest = patternedBytes(count: 65_536, multiplier: 31, offset: 7)
        let forwardReply = patternedBytes(count: 20_000, multiplier: 19, offset: 5)
        let reverseRequest = patternedBytes(count: 20_000, multiplier: 17, offset: 3)
        let reverseReply = patternedBytes(count: 65_536, multiplier: 13, offset: 11)
        let reverseOK = Data("PARTYDECK-INTEROP-1-REVERSE-OK".utf8)
        let complete = Data("PARTYDECK-INTEROP-1-COMPLETE".utf8)
        let host = IosLanDriver()
        let client = IosLanDriver()
        let hostProbe = NativeProbe(expectedWrites: 1, expectedFrames: [reverseRequest, reverseOK]) { [weak host] connectionID in
            host?.send(connectionId: connectionID, operationId: "interop-heartbeat", bytes: KotlinByteArray(size: 4))
        }
        let clientProbe = NativeProbe(expectedWrites: 3, expectedFrames: [forwardReply, complete]) { [weak client] connectionID in
            client?.send(connectionId: connectionID, operationId: "interop-heartbeat", bytes: KotlinByteArray(size: 4))
        }
        host.attach(observer: hostProbe)
        client.attach(observer: clientProbe)
        defer {
            client.close()
            host.close()
        }

        host.startHost(operationId: "interop-swift-host", displayName: "Native interoperability test")
        await fulfillment(of: [hostProbe.hostReady], timeout: 20)
        let hostInfo = try XCTUnwrap(hostProbe.snapshot.hostInfo)
        let swiftPort = try XCTUnwrap(hostInfo.endpoints.first?.port)
        client.connect(
            operationId: "interop-java-client",
            endpoint: LanEndpoint(host: "127.0.0.1", port: manifest.port, serviceName: nil),
            certificateSha256: manifest.certificateSha256
        )
        await fulfillment(of: [clientProbe.connected], timeout: 20)
        let primaryID = try XCTUnwrap(clientProbe.snapshot.outgoingID)
        let control = Data("PARTYDECK-INTEROP-1\n\(swiftPort)\n\(hostInfo.certificateSha256)".utf8)
        client.send(connectionId: primaryID, operationId: "interop-control", bytes: kotlinBytes(framed(control)))
        client.send(connectionId: primaryID, operationId: "interop-forward", bytes: kotlinBytes(framed(forwardRequest)))

        await fulfillment(of: [hostProbe.incoming, hostProbe.frameReceived[0]], timeout: 30)
        let reverseID = try XCTUnwrap(hostProbe.snapshot.incomingID)
        host.send(connectionId: reverseID, operationId: "interop-reverse", bytes: kotlinBytes(framed(reverseReply)))
        await fulfillment(of: [hostProbe.frameReceived[1], hostProbe.writesCompleted], timeout: 30)
        host.closeConnection(connectionId: reverseID)
        await fulfillment(of: [hostProbe.connectionClosed], timeout: 10)

        await fulfillment(of: [clientProbe.frameReceived[0]], timeout: 30)
        client.send(
            connectionId: primaryID,
            operationId: "interop-acknowledge",
            bytes: kotlinBytes(framed(Data("PARTYDECK-INTEROP-1-OK".utf8)))
        )
        await fulfillment(of: [clientProbe.frameReceived[1], clientProbe.writesCompleted], timeout: 30)
        client.closeConnection(connectionId: primaryID)
        await fulfillment(of: [clientProbe.connectionClosed], timeout: 10)
        XCTAssertEqual(hostProbe.snapshot.receivedFrames, [reverseRequest, reverseOK])
        XCTAssertEqual(clientProbe.snapshot.receivedFrames, [forwardReply, complete])
        XCTAssertTrue(hostProbe.snapshot.writeFailures.isEmpty)
        XCTAssertTrue(clientProbe.snapshot.writeFailures.isEmpty)
        host.stopHost(hostId: "interop-swift-host")
    }

    private func patternedBytes(count: Int, multiplier: Int, offset: Int) -> Data {
        Data((0..<count).map { UInt8(($0 * multiplier + offset) % 251) })
    }

    private func framed(_ payload: Data) -> Data {
        var length = UInt32(payload.count).bigEndian
        var result = Data()
        Swift.withUnsafeBytes(of: &length) { result.append(contentsOf: $0) }
        result.append(payload)
        return result
    }

    private func kotlinBytes(_ data: Data) -> KotlinByteArray {
        let result = KotlinByteArray(size: Int32(data.count))
        for (index, byte) in data.enumerated() {
            result.set(index: Int32(index), value: Int8(bitPattern: byte))
        }
        return result
    }
}

private struct InteropManifest: Decodable {
    let version: Int
    let port: Int32
    let certificateSha256: String
}

private enum InteropFixtureError: Error {
    case missingManifest
    case invalidManifest
}

private final class NativeProbe: NSObject, NativeLanObserver {
    struct Snapshot {
        var hostInfo: HostInfo?
        var incomingID: String?
        var outgoingID: String?
        var connectFailure: TransportFailureCode?
        var received: [String: Data] = [:]
        var receivedFrames: [Data] = []
        var writeFailures: [String] = []
    }

    let hostReady = XCTestExpectation(description: "Native host ready")
    let incoming = XCTestExpectation(description: "Native incoming TLS ready")
    let connected = XCTestExpectation(description: "Native outgoing TLS ready")
    let connectFailed = XCTestExpectation(description: "Native outgoing TLS rejected")
    let bytesReceived = XCTestExpectation(description: "All expected TLS bytes received")
    let writesCompleted = XCTestExpectation(description: "Native writes completed")
    let connectionClosed = XCTestExpectation(description: "Native connection closed")
    let frameReceived: [XCTestExpectation]
    private let lock = NSLock()
    private let expectedBytes: Int
    private let expectedFrames: [Data]
    private let heartbeatResponder: ((String) -> Void)?
    private var state = Snapshot()
    private var receivedEnough = false
    private var closedIDs: Set<String> = []
    private var frameBuffers: [String: Data] = [:]

    init(
        expectedBytes: Int = 0,
        expectedWrites: Int = 1,
        expectedFrames: [Data] = [],
        heartbeatResponder: ((String) -> Void)? = nil
    ) {
        self.expectedBytes = expectedBytes
        self.expectedFrames = expectedFrames
        self.heartbeatResponder = heartbeatResponder
        frameReceived = expectedFrames.indices.map { XCTestExpectation(description: "Native application frame \($0 + 1)") }
        super.init()
        writesCompleted.expectedFulfillmentCount = expectedWrites
        writesCompleted.assertForOverFulfill = true
        frameReceived.forEach { $0.assertForOverFulfill = true }
    }

    var snapshot: Snapshot {
        lock.lock()
        defer { lock.unlock() }
        return state
    }

    func onHostReady(operationId: String, info: HostInfo) {
        lock.lock()
        state.hostInfo = info
        lock.unlock()
        hostReady.fulfill()
    }

    func onHostFailed(operationId: String, code: TransportFailureCode, message: String) {
        XCTFail("Native TLS host failed: \(code.name)")
        hostReady.fulfill()
    }

    func onIncomingConnection(hostId: String, connectionId: String) {
        lock.lock()
        state.incomingID = connectionId
        lock.unlock()
        incoming.fulfill()
    }

    func onConnected(operationId: String, connectionId: String) {
        lock.lock()
        state.outgoingID = connectionId
        lock.unlock()
        connected.fulfill()
    }

    func onConnectFailed(operationId: String, code: TransportFailureCode, message: String) {
        lock.lock()
        state.connectFailure = code
        lock.unlock()
        connectFailed.fulfill()
    }

    func onConnectionBytes(connectionId: String, bytes: KotlinByteArray) -> Bool {
        var data = Data(capacity: Int(bytes.size))
        for index in 0..<bytes.size { data.append(UInt8(bitPattern: bytes.get(index: index))) }
        var completedFrames: [XCTestExpectation] = []
        var frameFailure: String?
        var heartbeats = 0
        lock.lock()
        state.received[connectionId, default: Data()].append(data)
        let ready = expectedBytes > 0 && !receivedEnough && (state.received[connectionId]?.count ?? 0) >= expectedBytes
        if ready { receivedEnough = true }
        if !expectedFrames.isEmpty {
            var pending = frameBuffers[connectionId, default: Data()]
            pending.append(data)
            while pending.count >= 4 {
                let length = pending.prefix(4).reduce(0) { ($0 << 8) | Int($1) }
                guard length <= 65_536 else {
                    frameFailure = "The native peer sent a frame exceeding the 64 KiB limit."
                    break
                }
                guard pending.count >= length + 4 else { break }
                let payload = Data(pending.dropFirst(4).prefix(length))
                pending = Data(pending.dropFirst(length + 4))
                if length == 0 {
                    heartbeats += 1
                    continue
                }
                let index = state.receivedFrames.count
                guard index < expectedFrames.count else {
                    frameFailure = "The native peer sent an unexpected application frame."
                    break
                }
                state.receivedFrames.append(payload)
                completedFrames.append(frameReceived[index])
                guard payload == expectedFrames[index] else {
                    frameFailure = "Native application frame \(index + 1) differs from the interoperability contract."
                    break
                }
            }
            frameBuffers[connectionId] = pending
        }
        lock.unlock()
        // Java's transport sends zero records every five seconds. Echoing one keeps its
        // receive-idle deadline alive while the other TLS direction completes a stage.
        for _ in 0..<heartbeats { heartbeatResponder?(connectionId) }
        if let frameFailure { XCTFail(frameFailure) }
        completedFrames.forEach { $0.fulfill() }
        if ready { bytesReceived.fulfill() }
        return frameFailure == nil
    }

    func onConnectionClosed(connectionId: String, code: TransportFailureCode?, message: String?) {
        lock.lock()
        let firstClose = closedIDs.insert(connectionId).inserted
        lock.unlock()
        if firstClose { connectionClosed.fulfill() }
    }

    func onSendComplete(operationId: String, code: TransportFailureCode?, message: String?) {
        // Heartbeat writes are not application-frame completions and may race terminal close.
        if operationId == "interop-heartbeat" { return }
        lock.lock()
        if code != nil { state.writeFailures.append(operationId) }
        lock.unlock()
        writesCompleted.fulfill()
    }

    func onDiscoveryStarted(operationId: String) {}
    func onDiscoveryChanged(operationId: String, hosts: [DiscoveredHost]) {}
    func onDiscoveryFailed(operationId: String, code: TransportFailureCode, message: String) {
        XCTFail("Unexpected native discovery failure: \(code.name)")
    }
}
