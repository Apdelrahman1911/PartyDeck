package dev.partydeck.transport

import org.bouncycastle.asn1.x509.BasicConstraints
import org.bouncycastle.asn1.x509.ExtendedKeyUsage
import org.bouncycastle.asn1.x509.Extension
import org.bouncycastle.asn1.x509.KeyPurposeId
import org.bouncycastle.asn1.x509.KeyUsage
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder
import java.math.BigInteger
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.security.spec.ECGenParameterSpec
import java.util.Date
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocket
import javax.net.ssl.X509TrustManager
import javax.security.auth.x500.X500Principal

/** Certificate encoding uses BC; key generation/signatures and TLS use the default JCA/JSSE providers. */
internal data class JavaTlsIdentity(val context: SSLContext, val certificateSha256: String) {
    companion object {
        fun generate(): JavaTlsIdentity {
            val random = SecureRandom()
            val keys = KeyPairGenerator.getInstance("EC").apply {
                initialize(ECGenParameterSpec("secp256r1"), random)
            }.generateKeyPair()
            val name = X500Principal("CN=PartyDeck ephemeral host")
            val now = System.currentTimeMillis()
            val certificate = JcaX509v3CertificateBuilder(
                name,
                BigInteger(159, random).setBit(0),
                Date(now - 86_400_000L),
                Date(now + 172_800_000L),
                name,
                keys.public,
            ).apply {
                addExtension(Extension.basicConstraints, true, BasicConstraints(false))
                addExtension(Extension.keyUsage, true, KeyUsage(KeyUsage.digitalSignature))
                addExtension(Extension.extendedKeyUsage, false, ExtendedKeyUsage(KeyPurposeId.id_kp_serverAuth))
            }.build(JcaContentSignerBuilder("SHA256withECDSA").setSecureRandom(random).build(keys.private))
                .let { JcaX509CertificateConverter().getCertificate(it) }
            certificate.checkValidity()
            certificate.verify(keys.public)

            val password = ByteArray(32).also(random::nextBytes).toHex().toCharArray()
            try {
                val store = KeyStore.getInstance("PKCS12").apply {
                    load(null, password)
                    setKeyEntry("partydeck", keys.private, password, arrayOf(certificate))
                }
                val managers = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm()).apply {
                    init(store, password)
                }
                val context = SSLContext.getInstance("TLS").apply { init(managers.keyManagers, null, random) }
                return JavaTlsIdentity(context, MessageDigest.getInstance("SHA-256").digest(certificate.encoded).toHex())
            } finally {
                password.fill('\u0000')
            }
        }

        fun clientContext(certificateSha256: String): SSLContext {
            require(isSha256Hex(certificateSha256))
            return SSLContext.getInstance("TLS").apply {
                init(null, arrayOf(PinnedHostTrustManager(certificateSha256)), SecureRandom())
            }
        }
    }
}

/** The complete OOB pin, certificate validity and proof of the private key replace WebPKI hostname trust. */
internal class PinnedHostTrustManager(pin: String) : X509TrustManager {
    private val expected = pin.chunked(2).map { it.toInt(16).toByte() }.toByteArray()

    override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
        val certificate = chain?.firstOrNull() ?: throw CertificateException("The host did not supply a certificate")
        val actual = MessageDigest.getInstance("SHA-256").digest(certificate.encoded)
        if (!MessageDigest.isEqual(expected, actual)) throw CertificateException("Host certificate mismatch")
        certificate.checkValidity()
        if (certificate.publicKey.algorithm != "EC" || certificate.keyUsage?.getOrNull(0) != true ||
            certificate.extendedKeyUsage?.contains("1.3.6.1.5.5.7.3.1") != true) {
            throw CertificateException("Invalid PartyDeck host certificate")
        }
        certificate.verify(certificate.publicKey)
    }

    override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {
        throw CertificateException("Client certificates are not an admission credential")
    }

    override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
}

internal fun configureTlsSocket(socket: SSLSocket, client: Boolean) {
    socket.useClientMode = client
    socket.enabledProtocols = socket.supportedProtocols.filter { it == "TLSv1.3" || it == "TLSv1.2" }.toTypedArray()
    socket.enabledCipherSuites = socket.supportedCipherSuites.filter { it in ALLOWED_CIPHER_SUITES }.toTypedArray()
    check(socket.enabledProtocols.isNotEmpty() && socket.enabledCipherSuites.isNotEmpty()) { "Modern TLS is unavailable" }
    if (!client) socket.needClientAuth = false
    socket.tcpNoDelay = true
    socket.keepAlive = true
    socket.soTimeout = NATIVE_HANDSHAKE_TIMEOUT_MS
}

private val ALLOWED_CIPHER_SUITES = setOf(
    "TLS_AES_128_GCM_SHA256",
    "TLS_AES_256_GCM_SHA384",
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
)

internal fun ByteArray.toHex(): String = joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }
