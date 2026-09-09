package dev.partydeck.app

/** Explicit callback objects keep the Swift boundary synchronous and avoid exporting coroutines. */
interface IosScanResult {
    fun complete(value: String?)
}

interface IosNativeFeedback {
    fun prepare(key: String, resourceUri: String)
    fun play(key: String, soundEnabled: Boolean, hapticsEnabled: Boolean)
    fun setForeground(value: Boolean)
    fun close()
}

/** User-initiated UIKit presentation and feedback supplied by the native scene owner. */
interface IosNativeActions {
    val feedback: IosNativeFeedback
    val canScanInvitation: Boolean
    fun copyText(value: String): Boolean
    fun shareText(value: String): Boolean
    fun scanInvitation(result: IosScanResult): Boolean
}
