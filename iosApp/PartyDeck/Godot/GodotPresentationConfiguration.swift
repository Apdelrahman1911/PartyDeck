import Foundation

enum GodotPresentationMode: String, Hashable {
    case twoD = "2d"
    case threeD = "3d"
}

/// Native verifies the pinned pack digest again before acquiring its retained engine.
struct GodotPresentationConfiguration {
    let projectURL: URL?
    let packURL: URL?
    let qualifiedModes: Set<GodotPresentationMode>

    static func bundled(in bundle: Bundle = .main) -> GodotPresentationConfiguration {
        let modes = (bundle.object(forInfoDictionaryKey: "PartyDeckQualifiedGodotPresentations") as? [String] ?? [])
            .compactMap(GodotPresentationMode.init(rawValue:))
        let project = bundle.resourceURL
        let pack = project?.appendingPathComponent("ProbeResources", isDirectory: true)
            .appendingPathComponent("partydeck-last-light.pck", isDirectory: false)
        let installed = pack.map { FileManager.default.isReadableFile(atPath: $0.path) } == true
        return GodotPresentationConfiguration(
            projectURL: installed ? project : nil,
            packURL: installed ? pack : nil,
            qualifiedModes: installed ? Set(modes) : []
        )
    }
}
