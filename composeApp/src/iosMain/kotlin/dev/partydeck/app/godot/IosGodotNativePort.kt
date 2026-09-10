package dev.partydeck.app.godot

/**
 * Synchronous Kotlin/Swift boundary supplied by the retained native scene owner. All methods and
 * callbacks run on the main thread. Swift implements these callback protocols, not Flow or suspend
 * functions. The native owner retains one engine; each presentationId names a disposable handle.
 * No authority, transport credential, or qualification facade crosses this boundary.
 */
interface IosGodotNativePort {
    /**
     * Install callbacks before bootstrapping the covered native presentation. The launch document
     * uses the existing Last Light codec and includes its mode/preferences. Report an initial
     * lifecycleChanged before completing successfully. Ready may precede this completion and must
     * be emitted while covered; it must not wait for common Ready confirmation.
     *
     * close remains valid after any prepare invocation, including cancellation or failed prepare.
     */
    fun prepare(
        presentationId: String,
        launchDocument: String,
        isForeground: Boolean,
        isBackgrounded: Boolean,
        callbacks: IosGodotNativeCallbacks,
        completion: IosGodotNativeCompletion,
    )

    /**
     * Apply host lifecycle facts synchronously: cover and advance the native lifecycle generation
     * before invoking lifecycleChanged and before returning true. Report the current generation
     * even when these facts did not change. A false return means the handle cannot accept updates.
     * Native window/audio interruptions must use the same callback and invalidation order.
     */
    fun updateLifecycle(presentationId: String, isForeground: Boolean, isBackgrounded: Boolean): Boolean

    /**
     * Preserve the captured lifecycleGeneration outside the unchanged Godot wire document. Reject
     * obsolete handles/generations before applying the command or consuming confirmReady. A true
     * completion means the command was applied to that generation; false means it was rejected.
     * Report an intervening lifecycle generation before completing a superseded delivery.
     *
     * confirmReady records common acceptance of the renderer's actual Ready. Latch it only for a
     * current handle/generation, separately from observed Ready and wire foreground projections.
     * The wire foreground flag is a separate common input grant: false remains valid while native
     * is interactive, and true must never override a native cover or interruption.
     */
    fun deliver(
        presentationId: String,
        commandDocument: String,
        lifecycleGeneration: Long,
        confirmReady: Boolean,
        completion: IosGodotNativeCompletion,
    )

    /**
     * Immediately invalidate input/callbacks, cover the view, and discard queued projections.
     * Complete true only after deferred native cleanup has observed a dormant reusable owner.
     * Complete false for quarantine/terminal failure. Returning from this method is not completion.
     * An obsolete handle must never close, resume, or deliver into its replacement.
     */
    fun close(presentationId: String, completion: IosGodotNativeCompletion)
}

/** Per-presentation callbacks. Native must clear them as soon as close begins. */
interface IosGodotNativeCallbacks {
    /** A bounded renderer event in the existing Last Light wire schema. */
    fun event(document: String)

    /**
     * Publish the native generation before any common/controller projection. These flags describe
     * external interactivity/background state, not the initial opaque Ready cover. The generation
     * is nonnegative, monotonic for this handle, and advances on native lifecycle invalidation.
     */
    fun lifecycleChanged(generation: Long, isForeground: Boolean, isBackgrounded: Boolean)

    /** Native Back requests the shell's existing leave confirmation, without a renderer sequence. */
    fun exitRequested()

    /** Native fallback closes only the presentation and keeps the existing session. */
    fun useCompose()

    /** Native renderer loss; this does not fabricate an EngineEvent sequence or authority result. */
    fun failed()
}

/** Exactly one main-thread completion per operation; obsolete/duplicate callbacks are ignored. */
interface IosGodotNativeCompletion {
    fun complete(success: Boolean)
}

/**
 * Returned by IosAppHandle.installGodotPort. Installation starts no engine and advertises no modes.
 * The native owner explicitly offers only installed, qualified modes it can open. Withdraw them
 * while unavailable/quarantined, and close this registration when detaching the native owner.
 */
class IosGodotRegistration internal constructor(
    private val publish: (Boolean, Boolean) -> Unit,
    private val detach: () -> Unit,
) {
    private var closed = false

    fun setAvailability(twoD: Boolean, threeD: Boolean) {
        requireIosGodotMainThread()
        if (!closed) publish(twoD, threeD)
    }

    fun close() {
        requireIosGodotMainThread()
        if (closed) return
        closed = true
        detach()
    }
}
