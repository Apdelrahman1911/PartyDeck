package dev.partydeck.transport

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.os.Handler
import android.os.Looper
import java.net.Inet4Address
import java.util.concurrent.ConcurrentHashMap

/** System DNS-SD; all registration state is confined to the main looper, never Activity-owned. */
@Suppress("DEPRECATION") // resolveService is required on supported Android 26–33 devices.
internal class AndroidNsdDiscovery(context: Context) : JavaLanDiscovery {
    private val manager = context.getSystemService(NsdManager::class.java)
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var observer: NativeLanObserver
    private var closed = false
    private var discovery: DiscoveryRegistration? = null
    private val advertisements = mutableMapOf<String, Advertisement>()
    private val found = mutableMapOf<String, Long>()
    private val resolved = ConcurrentHashMap<String, DiscoveredHost>()
    private val resolveQueue = ArrayDeque<ResolveRequest>()
    private var resolving: ResolveRequest? = null
    private var generation = 0L

    override fun attach(observer: NativeLanObserver) { this.observer = observer }

    override fun advertise(hostId: String, displayName: String, serviceName: String, port: Int, completed: (String) -> Unit) {
        handler.post {
            if (closed) return@post
            lateinit var registration: Advertisement
            val listener = object : NsdManager.RegistrationListener {
                override fun onServiceRegistered(serviceInfo: NsdServiceInfo) {
                    handler.post {
                        registration.registered = true
                        if (closed || advertisements[hostId] !== registration) unregister(registration)
                        else if (!registration.completed) {
                            registration.completed = true
                            completed(serviceInfo.serviceName)
                        }
                    }
                }
                override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                    handler.post {
                        if (advertisements.remove(hostId, registration) && !registration.completed) {
                            registration.completed = true
                            completed(serviceName) // Direct TLS invitations remain usable without multicast.
                        }
                    }
                }
                override fun onServiceUnregistered(serviceInfo: NsdServiceInfo) = Unit
                override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                    handler.post {
                        observer.onHostFailed(hostId, TransportFailureCode.IO_ERROR, "The local advertisement could not be stopped")
                    }
                }
            }
            registration = Advertisement(hostId, listener)
            advertisements.put(hostId, registration)?.let(::unregister)
            val info = NsdServiceInfo().apply {
                this.serviceName = serviceName
                serviceType = BONJOUR_SERVICE_TYPE
                setPort(port)
                setAttribute("v", "1")
                setAttribute("name", displayName)
                setAttribute("port", port.toString())
            }
            try {
                manager.registerService(info, NsdManager.PROTOCOL_DNS_SD, listener)
            } catch (_: Exception) {
                advertisements.remove(hostId, registration)
                registration.completed = true
                completed(serviceName)
            }
        }
    }

    override fun stopAdvertising(hostId: String) {
        handler.post { advertisements.remove(hostId)?.let(::unregister) }
    }

    private fun unregister(registration: Advertisement) {
        if (!registration.registered || registration.unregisterRequested) return
        registration.unregisterRequested = true
        try {
            manager.unregisterService(registration.listener)
        } catch (_: IllegalArgumentException) {
            // NSD has already forgotten this listener after a registration failure/system restart.
        } catch (_: Exception) {
            observer.onHostFailed(registration.hostId, TransportFailureCode.IO_ERROR, "The local advertisement could not be stopped")
        }
    }

    override fun start(operationId: String) {
        handler.post {
            if (closed) {
                observer.onDiscoveryFailed(operationId, TransportFailureCode.CLOSED, "Discovery is closed")
                return@post
            }
            discovery?.let(::stopRegistration)
            found.clear()
            resolved.clear()
            resolveQueue.clear()
            lateinit var registration: DiscoveryRegistration
            val listener = object : NsdManager.DiscoveryListener {
                override fun onDiscoveryStarted(serviceType: String) {
                    handler.post {
                        if (discovery === registration) observer.onDiscoveryStarted(operationId)
                    }
                }
                override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                    handler.post {
                        if (discovery !== registration || serviceInfo.serviceType.trimEnd('.') != BONJOUR_SERVICE_TYPE) return@post
                        val name = serviceInfo.serviceName
                        if (name.isBlank() || name.encodeToByteArray().size > 63 || name.any { it.isISOControl() }) return@post
                        if (name !in found && found.size >= 64) return@post
                        val revision = ++generation
                        found[name] = revision
                        resolveQueue.removeAll { it.info.serviceName == name }
                        if (resolveQueue.size < 64) resolveQueue.addLast(ResolveRequest(operationId, serviceInfo, revision))
                        resolveNext()
                    }
                }
                override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                    handler.post {
                        if (discovery !== registration) return@post
                        found.remove(serviceInfo.serviceName)
                        resolved.remove(serviceInfo.serviceName)
                        resolveQueue.removeAll { it.info.serviceName == serviceInfo.serviceName }
                        emitHosts(operationId)
                    }
                }
                override fun onDiscoveryStopped(serviceType: String) {
                    handler.post {
                        if (discovery === registration) failDiscovery(registration, TransportFailureCode.UNAVAILABLE, "Local discovery stopped")
                    }
                }
                override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                    handler.post { failDiscovery(registration, TransportFailureCode.UNAVAILABLE, "Local discovery could not start; use an invitation") }
                }
                override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                    handler.post { observer.onDiscoveryFailed(operationId, TransportFailureCode.IO_ERROR, "Local discovery could not stop cleanly") }
                }
            }
            registration = DiscoveryRegistration(operationId, listener)
            discovery = registration
            try {
                manager.discoverServices(BONJOUR_SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
            } catch (_: SecurityException) {
                failDiscovery(registration, TransportFailureCode.PERMISSION_DENIED, "Allow local network access to find games")
            } catch (_: Exception) {
                failDiscovery(registration, TransportFailureCode.UNAVAILABLE, "Local discovery is unavailable; use an invitation")
            }
        }
    }

    private fun failDiscovery(registration: DiscoveryRegistration, code: TransportFailureCode, message: String) {
        if (discovery !== registration) return
        discovery = null
        stopRegistration(registration)
        resolveQueue.clear()
        found.clear()
        resolved.clear()
        observer.onDiscoveryFailed(registration.id, code, message)
    }

    private fun resolveNext() {
        if (closed || resolving != null || resolveQueue.isEmpty()) return
        val request = resolveQueue.removeFirst()
        if (discovery?.id != request.discoveryId || found[request.info.serviceName] != request.revision) {
            resolveNext()
            return
        }
        resolving = request
        val listener = object : NsdManager.ResolveListener {
            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                handler.post { finishResolution(request, null) }
            }
            override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                handler.post { finishResolution(request, serviceInfo) }
            }
        }
        try {
            val timeout = Runnable { finishResolution(request, null) }
            request.timeout = timeout
            manager.resolveService(request.info, listener)
            handler.postDelayed(timeout, 5_000)
        } catch (_: Exception) {
            finishResolution(request, null)
        }
    }

    private fun finishResolution(request: ResolveRequest, info: NsdServiceInfo?) {
        request.timeout?.let(handler::removeCallbacks)
        request.timeout = null
        if (resolving !== request) return
        resolving = null
        if (info != null && discovery?.id == request.discoveryId && found[info.serviceName] == request.revision) {
            val host = toHost(info)
            if (host != null) resolved[host.serviceName] = host
            emitHosts(request.discoveryId)
        }
        resolveNext()
    }

    private fun toHost(info: NsdServiceInfo): DiscoveredHost? {
        return try {
            if (info.port !in 1..65535 || info.attributes["v"]?.decodeToString() != "1") return null
            val addresses = if (Build.VERSION.SDK_INT >= 34) info.hostAddresses else listOfNotNull(info.host)
            val address = addresses.filter { !it.isAnyLocalAddress && !it.isMulticastAddress }
                .sortedBy { if (it is Inet4Address) 0 else 1 }.firstOrNull()?.hostAddress ?: return null
            val name = info.attributes["name"]?.decodeToString(throwOnInvalidSequence = true) ?: info.serviceName
            if (name.isBlank() || name.encodeToByteArray().size > 80 || name.any { it.isISOControl() }) return null
            DiscoveredHost(info.serviceName, name, LanEndpoint(address, info.port, info.serviceName))
        } catch (_: Exception) {
            null // Untrusted malformed DNS-SD metadata is not a usable candidate.
        }
    }

    private fun emitHosts(operationId: String) {
        observer.onDiscoveryChanged(operationId, resolved.values.sortedBy { it.serviceName }.take(64))
    }

    override fun lookup(serviceName: String): LanEndpoint? = resolved[serviceName]?.endpoint

    override fun stop(operationId: String) {
        handler.post {
            val registration = discovery?.takeIf { it.id == operationId } ?: return@post
            discovery = null
            stopRegistration(registration)
            found.clear()
            resolved.clear()
            resolveQueue.clear()
        }
    }

    private fun stopRegistration(registration: DiscoveryRegistration) {
        if (registration.stopRequested) return
        registration.stopRequested = true
        try {
            manager.stopServiceDiscovery(registration.listener)
        } catch (_: IllegalArgumentException) {
            // Already stopped or a start that NSD rejected before listener registration.
        } catch (_: Exception) {
            observer.onDiscoveryFailed(registration.id, TransportFailureCode.IO_ERROR, "Local discovery could not stop cleanly")
        }
    }

    override fun close() {
        handler.post {
            if (closed) return@post
            closed = true
            discovery?.let(::stopRegistration)
            discovery = null
            advertisements.values.toList().forEach(::unregister)
            advertisements.clear()
            resolving?.timeout?.let(handler::removeCallbacks)
            resolving = null
            resolveQueue.clear()
            resolved.clear()
            found.clear()
        }
    }

    private class Advertisement(val hostId: String, val listener: NsdManager.RegistrationListener) {
        var registered = false
        var unregisterRequested = false
        var completed = false
    }
    private class DiscoveryRegistration(val id: String, val listener: NsdManager.DiscoveryListener) { var stopRequested = false }
    private class ResolveRequest(val discoveryId: String, val info: NsdServiceInfo, val revision: Long) {
        var timeout: Runnable? = null
    }
}
