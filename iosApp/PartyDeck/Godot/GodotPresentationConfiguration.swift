import Foundation

enum GodotPresentationMode: String, Hashable {
    case twoD = "2d"
    case threeD = "3d"
}

enum GodotActivationProfile: String {
    case shipping
    case qualification
}

/// Native verifies the pinned pack digest again before acquiring its retained engine.
struct GodotPresentationConfiguration {
    let projectURL: URL?
    let packURL: URL?
    /// A malformed packaged configuration has no profile and enables no modes.
    let activationProfile: GodotActivationProfile?
    let enabledModes: Set<GodotPresentationMode>

    static func bundled(in bundle: Bundle = .main) -> GodotPresentationConfiguration {
        let activation = resolveActivation(bundle.infoDictionary ?? [:])
        let project = bundle.resourceURL
        let pack = project?.appendingPathComponent("ProbeResources", isDirectory: true)
            .appendingPathComponent("partydeck-last-light.pck", isDirectory: false)
        let installed = pack.map { FileManager.default.isReadableFile(atPath: $0.path) } == true
        return GodotPresentationConfiguration(
            projectURL: installed ? project : nil,
            packURL: installed ? pack : nil,
            activationProfile: activation?.profile,
            enabledModes: installed ? (activation?.modes ?? []) : []
        )
    }

    private static func resolveActivation(
        _ info: [String: Any]
    ) -> (profile: GodotActivationProfile, modes: Set<GodotPresentationMode>)? {
        // Missing legacy fields are shipping/empty. Present malformed fields fail
        // the whole configuration, including fields outside the selected profile.
        guard let rawProfile = (info["PartyDeckGodotActivationProfile"] ?? "shipping") as? String,
              let profile = GodotActivationProfile(rawValue: rawProfile),
              let accepted = parseModes(info["PartyDeckQualifiedGodotPresentations"]),
              let requested = parseModes(info["PartyDeckQualificationGodotPresentations"]) else {
            return nil
        }
        switch profile {
        case .shipping:
            guard requested.isEmpty else { return nil }
            return (profile, accepted)
        case .qualification:
            guard !requested.isEmpty else { return nil }
            return (profile, requested)
        }
    }

    private static func parseModes(_ value: Any?) -> Set<GodotPresentationMode>? {
        guard let value = value else { return [] }
        guard let tokens = value as? [String] else { return nil }
        var modes = Set<GodotPresentationMode>()
        for token in tokens {
            guard let mode = GodotPresentationMode(rawValue: token),
                  modes.insert(mode).inserted else { return nil }
        }
        return modes
    }
}
