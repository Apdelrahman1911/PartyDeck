package dev.partydeck.app.controller

import dev.partydeck.session.ClientIntent
import dev.partydeck.session.CommandReceipt
import dev.partydeck.session.SessionError
import dev.partydeck.session.SessionView
import dev.partydeck.transport.TransportException
import dev.partydeck.transport.TransportFailureCode
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal data class RuntimeIssue(
    val occurrence: Long,
    val code: UiProblemCode,
    val recovery: RecoveryAction,
)

internal data class RuntimeSnapshot(
    val mode: SessionMode,
    val connection: ConnectionStatus,
    val view: SessionView? = null,
    val invitation: HostInvitation? = null,
    val retryAttempt: Int = 0,
    val issue: RuntimeIssue? = null,
)

internal interface SessionRuntime {
    val state: StateFlow<RuntimeSnapshot>
    fun start()
    /** Submit against the session revision captured with the view that authorized this action. */
    suspend fun send(intent: ClientIntent, expectedRevision: Long): CommandReceipt
    suspend fun leave()
    fun setForeground(value: Boolean)
    fun retry()
    fun close()
    suspend fun awaitClosed()
}

internal class RuntimeFailure(
    val code: UiProblemCode,
    val recovery: RecoveryAction = RecoveryAction.DISMISS,
) : Exception(code.name)

/** Cleanup is registered before resources can be acquired, including during a cancelled start. */
internal abstract class OwnedSessionRuntime(
    parentScope: CoroutineScope,
    initial: RuntimeSnapshot,
) : SessionRuntime {
    protected val job = SupervisorJob(parentScope.coroutineContext[Job])
    protected val scope = CoroutineScope(parentScope.coroutineContext + job)
    protected val mutableState = MutableStateFlow(initial)
    final override val state: StateFlow<RuntimeSnapshot> = mutableState.asStateFlow()
    protected var foregroundActive = true
    protected var closed = false
    private var issueCounter = 0L

    protected fun registerCleanup(cleanup: suspend () -> Unit) {
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                awaitCancellation()
            } finally {
                withContext(NonCancellable) { cleanup() }
            }
        }
    }

    protected fun report(
        code: UiProblemCode,
        recovery: RecoveryAction = RecoveryAction.DISMISS,
    ) {
        val issue = RuntimeIssue(++issueCounter, code, recovery)
        mutableState.update { it.copy(issue = issue) }
    }

    override fun close() {
        if (closed) return
        closed = true
        mutableState.update {
            it.copy(connection = ConnectionStatus.DISCONNECTED, view = null, invitation = null)
        }
        scope.cancel()
    }

    final override suspend fun awaitClosed() = job.join()
}

internal fun SessionError.toUiProblem(): UiProblemCode = when (this) {
    SessionError.UNSUPPORTED_VERSION -> UiProblemCode.VERSION_MISMATCH
    SessionError.INVALID_NAME -> UiProblemCode.INVALID_NAME
    SessionError.LOBBY_FULL -> UiProblemCode.SESSION_FULL
    SessionError.SESSION_CLOSED -> UiProblemCode.SESSION_ENDED
    SessionError.STALE_REVISION -> UiProblemCode.STALE_ACTION
    SessionError.WRONG_SESSION, SessionError.INVALID_CREDENTIALS,
    SessionError.NOT_ADMITTED, SessionError.ALREADY_ADMITTED -> UiProblemCode.JOIN_REJECTED
    else -> UiProblemCode.ACTION_REJECTED
}

internal fun Throwable.toRuntimeFailure(): RuntimeFailure {
    if (this is CancellationException) throw this
    if (this is RuntimeFailure) return this
    return when (this) {
        is TransportException -> when (failure.code) {
            TransportFailureCode.AUTHENTICATION_FAILED ->
                RuntimeFailure(UiProblemCode.JOIN_REJECTED, RecoveryAction.EDIT_INVITE)
            TransportFailureCode.PERMISSION_DENIED ->
                RuntimeFailure(UiProblemCode.LOCAL_NETWORK_PERMISSION_DENIED, RecoveryAction.RETRY_CONNECTION)
            else -> RuntimeFailure(UiProblemCode.CONNECTION_FAILED, RecoveryAction.RETRY_CONNECTION)
        }
        else -> RuntimeFailure(UiProblemCode.CONNECTION_FAILED, RecoveryAction.RETRY_CONNECTION)
    }
}
