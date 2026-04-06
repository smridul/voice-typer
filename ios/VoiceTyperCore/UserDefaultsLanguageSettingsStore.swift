import Foundation

public final class UserDefaultsLanguageSettingsStore: LanguageSettingsStore {
    private enum Keys {
        static let contextLanguage = "context_language"
        static let outputLanguage = "output_language"
    }

    private let defaults: UserDefaults

    public init(defaults: UserDefaults) {
        self.defaults = defaults
    }

    public convenience init(suiteName: String) {
        self.init(defaults: UserDefaults(suiteName: suiteName) ?? .standard)
    }

    public func load() -> LanguageSettings {
        let context = LanguageCode(rawValue: defaults.string(forKey: Keys.contextLanguage) ?? "")
        let output = LanguageCode(rawValue: defaults.string(forKey: Keys.outputLanguage) ?? "")

        return LanguageSettings(
            contextLanguage: context ?? .english,
            outputLanguage: output ?? .english
        )
    }

    public func save(_ settings: LanguageSettings) throws {
        defaults.set(settings.contextLanguage.rawValue, forKey: Keys.contextLanguage)
        defaults.set(settings.outputLanguage.rawValue, forKey: Keys.outputLanguage)
    }
}
