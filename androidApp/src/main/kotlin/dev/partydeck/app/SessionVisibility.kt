package dev.partydeck.app

/**
 * Visibility belongs to both real windows; input belongs only to the selected one.
 *
 * Activity's START/STOP lifetime describes visibility, while RESUME and window focus are separate
 * facts. ProcessLifecycleOwner cannot observe :godot (its documented scope is one process).
 * This retained, main-thread owner therefore consumes lifetime-tagged native observations.
 * The host's bounded startup lease and short transition grace preserve a session across an
 * unobserved handoff, never grant input, and are cancelled by an actual stopped child or an
 * explicit user departure. Neither assumption replaces the actual window observations.
 */
internal class SessionVisibility(
    private val transitionGraceMillis: Long = 1_000,
    private val retiringVisibilityMillis: Long = 3_000,
) {
    init {
        require(transitionGraceMillis > 0 && retiringVisibilityMillis > 0)
    }

    internal data class Snapshot(
        val foreground: Boolean,
        val backgrounded: Boolean,
        val shellSelected: Boolean,
        val nextDeadlineMillis: Long?,
    )

    private data class Window(val started: Boolean = false, val resumed: Boolean = false, val focused: Boolean = false) {
        val interactive: Boolean get() = started && resumed && focused
    }

    private data class Renderer(
        val id: String,
        val openingDeadline: Long,
        val generation: Long = -1,
        val window: Window = Window(),
        val closingDeadline: Long? = null,
        val assumedClosingVisibility: Boolean = false,
    )

    private var lastShellAttachment = 0L
    private var shellAttachment: Long? = null
    private var shell = Window()
    private var selectedRenderer: String? = null
    private var renderer: Renderer? = null
    private var graceDeadline: Long? = null
    private var openingFromVisibleShell = false
    private var userLeaving = false

    fun attachShell(nowMillis: Long): Long {
        check(lastShellAttachment < Long.MAX_VALUE) { "Shell attachment identity exhausted" }
        if (shell.started) beginGrace(nowMillis)
        shell = Window()
        lastShellAttachment += 1
        shellAttachment = lastShellAttachment
        return lastShellAttachment
    }

    fun updateShell(attachment: Long, started: Boolean, resumed: Boolean, focused: Boolean): Boolean {
        if (attachment != shellAttachment) return false
        val wasStarted = shell.started
        val wasInteractive = shell.interactive
        shell = Window(started, resumed, focused)
        if (started) graceDeadline = null
        if (started && !wasStarted) renderer = renderer?.copy(assumedClosingVisibility = false)
        if (selectedRenderer == null && !wasInteractive && shell.interactive) userLeaving = false
        return true
    }

    fun shellCanLaunch(attachment: Long): Boolean =
        attachment == shellAttachment && shell.interactive && !userLeaving

    fun stopShell(attachment: Long, changingConfigurations: Boolean, nowMillis: Long): Boolean {
        if (attachment != shellAttachment) return false
        val wasStarted = shell.started
        shell = Window()
        if (wasStarted && changingConfigurations) {
            beginGrace(nowMillis)
        }
        return true
    }

    fun detachShell(attachment: Long): Boolean {
        if (attachment != shellAttachment) return false
        shellAttachment = null
        shell = Window()
        return true
    }

    fun userLeavingShell(attachment: Long): Boolean {
        if (attachment != shellAttachment) return false
        userLeaving = true
        openingFromVisibleShell = false
        renderer = renderer?.copy(assumedClosingVisibility = false)
        graceDeadline = null
        return true
    }

    fun selectPresentation(presentationId: String?) {
        selectedRenderer = presentationId
    }

    fun rendererOpening(presentationId: String, deadlineMillis: Long): Boolean {
        if (renderer != null) return false
        require(deadlineMillis >= 0)
        renderer = Renderer(presentationId, openingDeadline = deadlineMillis)
        openingFromVisibleShell = shell.started && !userLeaving
        return true
    }

    fun updateRenderer(
        presentationId: String,
        generation: Long,
        started: Boolean,
        resumed: Boolean,
        focused: Boolean,
    ): Boolean {
        val current = renderer ?: return false
        if (current.id != presentationId || generation <= current.generation || generation < 0) return false
        val window = Window(started, resumed, focused)
        renderer = current.copy(generation = generation, window = window, assumedClosingVisibility = false)
        openingFromVisibleShell = false
        // A real stopped snapshot takes precedence over a handoff assumption.
        graceDeadline = null
        if (current.id == selectedRenderer && current.closingDeadline == null &&
            !current.window.interactive && window.interactive
        ) userLeaving = false
        return true
    }

    fun rendererClosing(presentationId: String, nowMillis: Long): Boolean {
        val current = renderer ?: return false
        if (current.id != presentationId || current.closingDeadline != null) return false
        // An early Back/Leave can reach the broker before LAUNCH and before any lifecycle
        // DATA. Preserve only bounded return visibility, without inventing a started window.
        val returningFromOpening = openingFromVisibleShell && current.generation < 0 &&
            !userLeaving && nowMillis < current.openingDeadline
        renderer = current.copy(
            closingDeadline = deadline(nowMillis, retiringVisibilityMillis),
            assumedClosingVisibility = returningFromOpening,
        )
        openingFromVisibleShell = false
        return true
    }

    fun rendererClosed(presentationId: String, nowMillis: Long): Boolean {
        val current = renderer ?: return false
        if (current.id != presentationId) return false
        val visibilityWasCurrent = current.closingDeadline?.let { nowMillis < it } != false
        val returningVisible = current.window.started || current.assumedClosingVisibility
        if (returningVisible && visibilityWasCurrent && !shell.started) beginGrace(nowMillis)
        renderer = null
        openingFromVisibleShell = false
        return true
    }

    fun snapshot(nowMillis: Long): Snapshot {
        val current = renderer
        val retiringDeadline = current?.closingDeadline
        val rendererVisible = current?.window?.started == true &&
            (retiringDeadline == null || nowMillis < retiringDeadline)
        val closingAssumption = current?.assumedClosingVisibility == true && !userLeaving &&
            retiringDeadline != null && nowMillis < retiringDeadline
        val opening = current?.openingDeadline?.takeIf {
            openingFromVisibleShell && current.generation < 0 && retiringDeadline == null &&
                !userLeaving && nowMillis < it
        }
        val grace = graceDeadline?.takeIf { nowMillis < it }
        val interactive = if (selectedRenderer == null) {
            shell.interactive
        } else {
            current?.id == selectedRenderer && current?.closingDeadline == null && current?.window?.interactive == true
        }
        return Snapshot(
            foreground = interactive && !userLeaving,
            backgrounded = !shell.started && !rendererVisible && !closingAssumption && opening == null && grace == null,
            shellSelected = selectedRenderer == null,
            nextDeadlineMillis = listOfNotNull(opening, grace, retiringDeadline?.takeIf { nowMillis < it }).minOrNull(),
        )
    }

    private fun beginGrace(nowMillis: Long) {
        if (!userLeaving && graceDeadline?.let { nowMillis < it } != true) {
            graceDeadline = deadline(nowMillis, transitionGraceMillis)
        }
    }

    private fun deadline(nowMillis: Long, duration: Long): Long {
        require(nowMillis >= 0)
        return if (nowMillis > Long.MAX_VALUE - duration) Long.MAX_VALUE else nowMillis + duration
    }
}
