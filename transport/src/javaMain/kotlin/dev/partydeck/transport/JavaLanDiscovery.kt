package dev.partydeck.transport

internal interface JavaLanDiscovery {
    fun attach(observer: NativeLanObserver)
    fun advertise(hostId: String, displayName: String, serviceName: String, port: Int, completed: (String) -> Unit)
    fun stopAdvertising(hostId: String)
    fun start(operationId: String)
    fun stop(operationId: String)
    fun lookup(serviceName: String): LanEndpoint?
    fun close()
}

/** The optional desktop launcher uses direct invitations without another mDNS dependency. */
internal class ManualJavaDiscovery : JavaLanDiscovery {
    private lateinit var observer: NativeLanObserver
    override fun attach(observer: NativeLanObserver) { this.observer = observer }
    override fun advertise(hostId: String, displayName: String, serviceName: String, port: Int, completed: (String) -> Unit) {
        completed(serviceName)
    }
    override fun stopAdvertising(hostId: String) = Unit
    override fun start(operationId: String) {
        observer.onDiscoveryFailed(operationId, TransportFailureCode.UNAVAILABLE, "Use a shared invitation to join on this device")
    }
    override fun stop(operationId: String) = Unit
    override fun lookup(serviceName: String): LanEndpoint? = null
    override fun close() = Unit
}
