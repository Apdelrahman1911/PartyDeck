package dev.partydeck.transport

class JvmLanTransportFactory : LanTransportFactory {
    override fun create(): LanTransport = CallbackLanTransport(
        JavaLanDriver(ManualJavaDiscovery(), allowLoopbackFallback = true),
    )
}
