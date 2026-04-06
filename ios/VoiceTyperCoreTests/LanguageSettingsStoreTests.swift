import XCTest
@testable import VoiceTyperCore

final class LanguageSettingsStoreTests: XCTestCase {
    func test_load_returnsDefaultsWhenStorageIsEmpty() {
        let defaults = UserDefaults(suiteName: "VoiceTyperTests.Empty")!
        defaults.removePersistentDomain(forName: "VoiceTyperTests.Empty")
        let store = UserDefaultsLanguageSettingsStore(defaults: defaults)

        XCTAssertEqual(store.load(), .default)
    }

    func test_save_roundTripsContextAndOutputLanguage() throws {
        let defaults = UserDefaults(suiteName: "VoiceTyperTests.RoundTrip")!
        defaults.removePersistentDomain(forName: "VoiceTyperTests.RoundTrip")
        let store = UserDefaultsLanguageSettingsStore(defaults: defaults)
        let expected = LanguageSettings(contextLanguage: .hindi, outputLanguage: .english)

        try store.save(expected)

        XCTAssertEqual(store.load(), expected)
    }
}
