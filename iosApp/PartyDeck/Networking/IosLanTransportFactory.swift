import Foundation
import PartyDeckKit

/// The application shell injects this factory; game/session rules remain in shared Kotlin.
final class IosLanTransportFactory: NSObject, LanTransportFactory {
    func create() -> any LanTransport {
        CallbackLanTransport(driver: IosLanDriver())
    }
}
