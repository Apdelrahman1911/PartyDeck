import CryptoKit
import Dispatch
import Foundation
import Network
import Security
import X509

/// An in-memory room identity. A new hosted room receives a new key and certificate.
///
/// Certificate APIs were checked against apple/swift-certificates 1.20.0:
/// https://github.com/apple/swift-certificates/blob/1.20.0/Sources/X509/Certificate.swift
/// https://github.com/apple/swift-certificates/blob/1.20.0/Sources/X509/CertificatePrivateKey.swift
/// Native identity and trust APIs were checked against Apple's Security documentation:
/// https://developer.apple.com/documentation/security/secidentitycreate(_:_:_:)
/// https://developer.apple.com/documentation/security/sectrustsetanchorcertificates(_:_:)
@available(iOS 15.0, macOS 12.0, *)
struct IosTlsIdentity {
    let identity: sec_identity_t
    let certificateSha256: String

    // Matches JavaTlsIdentity: tolerate a host clock one day ahead, expire after two days.
    // The room is process-local; once expired, the host must create a new room/invitation.
    private static let certificateBackdate: TimeInterval = 86_400
    private static let certificateLifetime: TimeInterval = 172_800
    private static let fingerprintByteCount = 32

    static func generate() throws -> IosTlsIdentity {
        let attributes: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeySizeInBits as String: 256,
            kSecPrivateKeyAttrs as String: [kSecAttrIsPermanent as String: false],
        ]
        var keyError: Unmanaged<CFError>?
        guard let nativeKey = SecKeyCreateRandomKey(attributes as CFDictionary, &keyError) else {
            if let keyError {
                throw keyError.takeRetainedValue() as Error
            }
            throw IdentityError.keyGenerationFailed
        }

        // Never export the private key or insert it into the user's Keychain.
        let signingKey = try Certificate.PrivateKey(nativeKey)
        let name = try DistinguishedName {
            CommonName("PartyDeck ephemeral host")
        }
        let extensions = try Certificate.Extensions {
            Critical(BasicConstraints.notCertificateAuthority)
            Critical(KeyUsage(digitalSignature: true))
            try ExtendedKeyUsage([.serverAuth])
        }
        let now = Date()
        let certificate = try Certificate(
            version: .v3,
            serialNumber: randomSerialNumber(),
            publicKey: signingKey.publicKey,
            notValidBefore: now.addingTimeInterval(-certificateBackdate),
            notValidAfter: now.addingTimeInterval(certificateLifetime),
            issuer: name,
            subject: name,
            signatureAlgorithm: .ecdsaWithSHA256,
            extensions: extensions,
            issuerPrivateKey: signingKey
        )
        guard try isValidHostCertificate(certificate, at: now) else {
            throw IdentityError.invalidCertificate
        }
        let nativeCertificate = try SecCertificate.makeWithCertificate(certificate)
        guard
            let nativeIdentity = SecIdentityCreate(nil, nativeCertificate, nativeKey),
            let protocolIdentity = sec_identity_create(nativeIdentity)
        else {
            throw IdentityError.identityCreationFailed
        }
        return IosTlsIdentity(
            identity: protocolIdentity,
            certificateSha256: fingerprint(SecCertificateCopyData(nativeCertificate) as Data)
        )
    }

    func serverOptions() -> NWProtocolTLS.Options {
        let options = Self.makeOptions()
        sec_protocol_options_set_local_identity(options.securityProtocolOptions, identity)
        // Session admission authenticates players after TLS; no client certificate is requested.
        sec_protocol_options_set_peer_authentication_required(options.securityProtocolOptions, false)
        return options
    }

    static func clientOptions(
        certificateSha256: String,
        queue: DispatchQueue
    ) throws -> NWProtocolTLS.Options {
        // The only trust input is the complete, canonical pin from the out-of-band invitation.
        let expectedFingerprint = try parseFingerprint(certificateSha256)
        let options = makeOptions()
        sec_protocol_options_set_peer_authentication_required(options.securityProtocolOptions, true)
        sec_protocol_options_set_verify_block(
            options.securityProtocolOptions,
            { _, trust, complete in
                let nativeTrust = sec_trust_copy_ref(trust).takeRetainedValue()
                complete(verifyHost(nativeTrust, expectedFingerprint: expectedFingerprint))
            },
            queue
        )
        return options
    }

    private static func makeOptions() -> NWProtocolTLS.Options {
        let options = NWProtocolTLS.Options()
        let security = options.securityProtocolOptions
        sec_protocol_options_set_min_tls_protocol_version(security, .TLSv12)
        // Offer the same AEAD suites as the Android/JVM transport.
        let suites: [tls_ciphersuite_t] = [
            .AES_128_GCM_SHA256,
            .AES_256_GCM_SHA384,
            .CHACHA20_POLY1305_SHA256,
            .ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
            .ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
            .ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256,
        ]
        for suite in suites {
            sec_protocol_options_append_tls_ciphersuite(security, suite)
        }
        // Every connection must complete a fresh authenticated handshake before application data.
        sec_protocol_options_set_tls_resumption_enabled(security, false)
        sec_protocol_options_set_tls_tickets_enabled(security, false)
        sec_protocol_options_set_tls_false_start_enabled(security, false)
        return options
    }

    private static func verifyHost(_ trust: SecTrust, expectedFingerprint: [UInt8]) -> Bool {
        // Network-fetch permission is stored in the policy, so install the SSL policy first.
        // Disable fetching before even asking Security to construct a chain; do not replace
        // this policy afterward or the no-network option would be lost.
        guard
            SecTrustSetPolicies(trust, SecPolicyCreateSSL(true, nil)) == errSecSuccess,
            SecTrustSetNetworkFetchAllowed(trust, false) == errSecSuccess
        else {
            return false
        }
        guard
            let certificates = SecTrustCopyCertificateChain(trust) as? [SecCertificate],
            let leaf = certificates.first
        else {
            return false
        }
        let actualFingerprint = Array(SHA256.hash(data: SecCertificateCopyData(leaf) as Data))
        guard actualFingerprint.count == expectedFingerprint.count else {
            return false
        }
        var difference: UInt8 = 0
        for index in actualFingerprint.indices {
            difference |= actualFingerprint[index] ^ expectedFingerprint[index]
        }
        guard difference == 0 else {
            return false
        }

        // The pinned certificate is the leaf, never an arbitrary member of the chain.
        // Check leaf constraints explicitly as well as asking Security to evaluate TLS server trust.
        do {
            guard try isValidHostCertificate(Certificate(leaf), at: Date()) else {
                return false
            }
        } catch {
            // Malformed certificate/extension input is an authentication failure, not a fallback.
            return false
        }
        guard
            SecTrustSetAnchorCertificates(trust, [leaf] as CFArray) == errSecSuccess,
            SecTrustSetAnchorCertificatesOnly(trust, true) == errSecSuccess
        else {
            return false
        }
        // A nil hostname is deliberate: the exact invitation pin identifies the host, not DNS.
        // These anchors belong only to this trust object; no system trust settings are changed.
        return SecTrustEvaluateWithError(trust, nil)
    }

    private static func isValidHostCertificate(_ certificate: Certificate, at date: Date) throws -> Bool {
        guard
            certificate.notValidBefore <= date,
            date <= certificate.notValidAfter,
            certificate.subject == certificate.issuer,
            certificate.signatureAlgorithm == .ecdsaWithSHA256,
            P256.Signing.PublicKey(certificate.publicKey) != nil,
            try certificate.extensions.basicConstraints == .notCertificateAuthority,
            try certificate.extensions.keyUsage?.digitalSignature == true,
            try certificate.extensions.extendedKeyUsage?.contains(.serverAuth) == true
        else {
            return false
        }
        return certificate.publicKey.isValidSignature(certificate.signature, for: certificate)
    }

    private static func randomSerialNumber() throws -> Certificate.SerialNumber {
        var bytes = [UInt8](repeating: 0, count: 20)
        let status = bytes.withUnsafeMutableBytes { buffer -> OSStatus in
            guard let address = buffer.baseAddress else {
                return errSecParam
            }
            return SecRandomCopyBytes(kSecRandomDefault, buffer.count, address)
        }
        guard status == errSecSuccess else {
            throw IdentityError.randomnessUnavailable(status)
        }
        bytes[0] &= 0x7f
        bytes[bytes.count - 1] |= 1
        return Certificate.SerialNumber(bytes: bytes)
    }

    private static func fingerprint(_ certificateData: Data) -> String {
        let digits = Array("0123456789abcdef".utf8)
        let characters = SHA256.hash(data: certificateData).flatMap { byte in
            [digits[Int(byte >> 4)], digits[Int(byte & 0x0f)]]
        }
        return String(decoding: characters, as: UTF8.self)
    }

    private static func parseFingerprint(_ value: String) throws -> [UInt8] {
        let characters = Array(value.utf8)
        guard characters.count == fingerprintByteCount * 2 else {
            throw IdentityError.invalidFingerprint
        }
        var bytes = [UInt8]()
        bytes.reserveCapacity(fingerprintByteCount)
        for offset in stride(from: 0, to: characters.count, by: 2) {
            guard
                let high = hexadecimalNibble(characters[offset]),
                let low = hexadecimalNibble(characters[offset + 1])
            else {
                throw IdentityError.invalidFingerprint
            }
            bytes.append((high << 4) | low)
        }
        return bytes
    }

    private static func hexadecimalNibble(_ character: UInt8) -> UInt8? {
        switch character {
        case 48...57: return character - 48
        case 97...102: return character - 97 + 10
        default: return nil
        }
    }

    private enum IdentityError: Error {
        case keyGenerationFailed
        case invalidCertificate
        case identityCreationFailed
        case invalidFingerprint
        case randomnessUnavailable(OSStatus)
    }
}
