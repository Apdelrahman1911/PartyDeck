package dev.partydeck.transport

import android.content.Context

class AndroidLanTransportFactory(context: Context) : LanTransportFactory {
    private val applicationContext = context.applicationContext

    override fun create(): LanTransport = CallbackLanTransport(
        JavaLanDriver(AndroidNsdDiscovery(applicationContext), allowLoopbackFallback = false),
    )
}
