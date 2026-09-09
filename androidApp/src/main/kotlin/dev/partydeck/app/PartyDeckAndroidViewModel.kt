package dev.partydeck.app

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.app.platform.AndroidPlatformServices
import dev.partydeck.transport.AndroidLanTransportFactory

/** The session survives Activity recreation; process death intentionally starts a fresh session. */
class PartyDeckAndroidViewModel(application: Application) : AndroidViewModel(application) {
    val services = AndroidPlatformServices(application)
    val controller = PartyDeckController(
        services = services,
        transportFactory = AndroidLanTransportFactory(application),
        parentScope = viewModelScope,
    )

    override fun onCleared() {
        controller.close()
        services.close()
        super.onCleared()
    }
}
