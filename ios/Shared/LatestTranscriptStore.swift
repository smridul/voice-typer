import Foundation

struct LatestTranscriptStore {
    private enum Keys {
        static let latestTranscript = "latest_transcript"
    }

    private let defaults: UserDefaults

    init(defaults: UserDefaults) {
        self.defaults = defaults
    }

    init(suiteName: String) {
        self.init(defaults: UserDefaults(suiteName: suiteName) ?? .standard)
    }

    func load() -> String {
        defaults.string(forKey: Keys.latestTranscript)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    func save(_ text: String) {
        defaults.set(
            text.trimmingCharacters(in: .whitespacesAndNewlines),
            forKey: Keys.latestTranscript
        )
    }

    func clear() {
        defaults.removeObject(forKey: Keys.latestTranscript)
    }
}
