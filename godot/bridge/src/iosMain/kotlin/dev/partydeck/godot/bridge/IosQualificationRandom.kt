@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.partydeck.godot.bridge

import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.usePinned
import platform.Security.SecRandomCopyBytes
import platform.Security.errSecSuccess
import platform.Security.kSecRandomDefault
import kotlin.random.Random

/** All arguments are explicit so Swift never needs Kotlin default-argument overloads. */
object IosQualificationFactory {
    @Throws(Exception::class)
    fun create(
        presentationId: String,
        mode: PresentationMode,
        randomness: IosQualificationRandomness,
        reduceMotion: Boolean,
        soundEnabled: Boolean,
        textScale: Double,
    ): IosQualificationAuthority = IosQualificationAuthority(
        random = when (randomness) {
            IosQualificationRandomness.REFERENCE_SEED_2 -> Random(IOS_QUALIFICATION_REFERENCE_SEED)
            IosQualificationRandomness.SECURE -> IosQualificationSecureRandom()
        },
        presentationId = presentationId,
        mode = mode,
        preferences = PresentationPreferences(reduceMotion, soundEnabled, textScale),
        randomness = randomness,
    )
}

/** Same verified Security.framework pattern as the shipping iOS platform service. */
private class IosQualificationSecureRandom : Random() {
    override fun nextBits(bitCount: Int): Int {
        require(bitCount in 0..32)
        if (bitCount == 0) return 0
        val bytes = ByteArray(4)
        return try {
            val status = bytes.usePinned { pinned ->
                SecRandomCopyBytes(kSecRandomDefault, bytes.size.convert(), pinned.addressOf(0))
            }
            check(status == errSecSuccess) { "Secure random generation is unavailable" }
            val word = ((bytes[0].toInt() and 0xff) shl 24) or
                ((bytes[1].toInt() and 0xff) shl 16) or
                ((bytes[2].toInt() and 0xff) shl 8) or
                (bytes[3].toInt() and 0xff)
            if (bitCount == 32) word else word ushr (32 - bitCount)
        } finally {
            bytes.fill(0)
        }
    }
}
