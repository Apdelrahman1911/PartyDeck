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

private final class NativeProbe: NSObject, NativeLanObserver {
    struct Snapshot {
        var hostInfo: HostInfo?
        var incomingID: String?
        var outgoingID: String?
        var connectFailure: TransportFailureCode?
        var received: [String: Data] = [:]
        var writeFailures: [String] = []
    }

    let hostReady = XCTestExpectation(description: "Native host ready")
    let incoming = XCTestExpectation(description: "Native incoming TLS ready")
    let connected = XCTestExpectation(description: "Native outgoing TLS ready")
    let connectFailed = XCTestExpectation(description: "Native outgoing TLS rejected")
    let bytesReceived = XCTestExpectation(description: "All expected TLS bytes received")
    let writesCompleted = XCTestExpectation(description: "Native writes completed")
    let connectionClosed = XCTestExpectation(description: "Native connection closed")
    private let lock = NSLock()
    private let expectedBytes: Int
    private var state = Snapshot()
    private var receivedEnough = false
    private var closedIDs: Set<String> = []

    init(expectedBytes: Int = 0, expectedWrites: Int = 1) {
        self.expectedBytes = expectedBytes
        super.init()
        writesCompleted.expectedFulfillmentCount = expectedWrites
        writesCompleted.assertForOverFulfill = true
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
        lock.lock()
        state.received[connectionId, default: Data()].append(data)
        let ready = expectedBytes > 0 && !receivedEnough && (state.received[connectionId]?.count ?? 0) >= expectedBytes
        if ready { receivedEnough = true }
        lock.unlock()
        if ready { bytesReceived.fulfill() }
        return true
    }

    func onConnectionClosed(connectionId: String, code: TransportFailureCode?, message: String?) {
        lock.lock()
        let firstClose = closedIDs.insert(connectionId).inserted
        lock.unlock()
        if firstClose { connectionClosed.fulfill() }
    }

    func onSendComplete(operationId: String, code: TransportFailureCode?, message: String?) {
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
