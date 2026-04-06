import XCTest
@testable import VoiceTyperCore

final class KeyboardStoreTests: XCTestCase {
    @MainActor
    func test_defaultsStartInEnglishMode() {
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(),
            transcriptionClient: FakeTranscriptionClient(),
            textConversionClient: FakeTextConversionClient(),
            settingsStore: InMemoryLanguageSettingsStore()
        )

        XCTAssertEqual(store.languageSettings.contextLanguage, .english)
        XCTAssertEqual(store.languageSettings.outputLanguage, .english)
    }

    @MainActor
    func test_updateContextLanguage_persistsImmediately() throws {
        let settingsStore = InMemoryLanguageSettingsStore()
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(),
            transcriptionClient: FakeTranscriptionClient(),
            textConversionClient: FakeTextConversionClient(),
            settingsStore: settingsStore
        )

        try store.updateContextLanguage(.hindi)

        XCTAssertEqual(store.languageSettings.contextLanguage, .hindi)
        XCTAssertEqual(settingsStore.savedSettings?.contextLanguage, .hindi)
    }

    @MainActor
    func test_updateOutputLanguage_persistsImmediately() throws {
        let settingsStore = InMemoryLanguageSettingsStore()
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(),
            transcriptionClient: FakeTranscriptionClient(),
            textConversionClient: FakeTextConversionClient(),
            settingsStore: settingsStore
        )

        try store.updateOutputLanguage(.hindi)

        XCTAssertEqual(store.languageSettings.outputLanguage, .hindi)
        XCTAssertEqual(settingsStore.savedSettings?.outputLanguage, .hindi)
    }

    @MainActor
    func test_stopRecording_englishToEnglish_showsTranscriptDirectly() async {
        let client = FakeTranscriptionClient(result: "hello world")
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(data: Data([0x00])),
            transcriptionClient: client,
            textConversionClient: FakeTextConversionClient(),
            settingsStore: InMemoryLanguageSettingsStore()
        )

        await store.toggleRecording()
        await store.toggleRecording()

        XCTAssertEqual(client.lastLanguage, .english)
        XCTAssertEqual(store.phase, .result)
        XCTAssertEqual(store.previewText, "hello world")
    }

    @MainActor
    func test_stopRecording_hindiToEnglish_showsRomanizedHindi() async {
        let client = FakeTranscriptionClient(result: "मुझे कल जाना है")
        let settingsStore = InMemoryLanguageSettingsStore(
            initial: LanguageSettings(contextLanguage: .hindi, outputLanguage: .english)
        )
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(data: Data([0x00])),
            transcriptionClient: client,
            textConversionClient: FakeTextConversionClient(),
            settingsStore: settingsStore
        )

        await store.toggleRecording()
        await store.toggleRecording()

        XCTAssertEqual(client.lastLanguage, .hindi)
        XCTAssertEqual(store.phase, .result)
        XCTAssertEqual(store.previewText, "mujhe kal jana hai")
    }

    @MainActor
    func test_stopRecording_englishToHindi_showsConvertedHindi() async {
        let client = FakeTranscriptionClient(result: "I need to go tomorrow")
        let converter = FakeTextConversionClient(result: "मुझे कल जाना है")
        let settingsStore = InMemoryLanguageSettingsStore(
            initial: LanguageSettings(contextLanguage: .english, outputLanguage: .hindi)
        )
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(data: Data([0x00])),
            transcriptionClient: client,
            textConversionClient: converter,
            settingsStore: settingsStore
        )

        await store.toggleRecording()
        await store.toggleRecording()

        XCTAssertEqual(store.phase, .result)
        XCTAssertEqual(store.previewText, "मुझे कल जाना है")
    }

    @MainActor
    func test_stopRecording_emptyTranscript_showsNoSpeech() async {
        let client = FakeTranscriptionClient(result: "")
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(data: Data([0x00])),
            transcriptionClient: client,
            textConversionClient: FakeTextConversionClient(),
            settingsStore: InMemoryLanguageSettingsStore()
        )

        await store.toggleRecording()
        await store.toggleRecording()

        XCTAssertEqual(store.phase, .error(message: "No speech detected"))
        XCTAssertEqual(store.previewText, "No speech detected")
    }

    @MainActor
    func test_startRecording_whenRecorderReturnsLocalizedError_showsCleanMessage() async {
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(
                startError: FakeRecorderError(
                    message: "iOS does not allow third-party keyboards to access the microphone directly."
                )
            ),
            transcriptionClient: FakeTranscriptionClient(),
            textConversionClient: FakeTextConversionClient(),
            settingsStore: InMemoryLanguageSettingsStore()
        )

        await store.toggleRecording()

        XCTAssertEqual(
            store.phase,
            .error(message: "iOS does not allow third-party keyboards to access the microphone directly.")
        )
        XCTAssertEqual(
            store.previewText,
            "iOS does not allow third-party keyboards to access the microphone directly."
        )
    }
}

struct FakeAudioRecorder: AudioRecording {
    var data = Data()
    var startError: Error?
    var stopError: Error?

    func start() async throws {
        if let startError {
            throw startError
        }
    }

    func stop() async throws -> Data {
        if let stopError {
            throw stopError
        }
        data
    }
}

private struct FakeRecorderError: LocalizedError {
    let message: String

    var errorDescription: String? {
        message
    }
}

final class FakeTranscriptionClient: TranscriptionClient {
    var result = ""
    private(set) var lastLanguage: LanguageCode?

    init(result: String = "") {
        self.result = result
    }

    func transcribe(audioData: Data, language: LanguageCode) async throws -> String {
        lastLanguage = language
        return result
    }
}

struct FakeTextConversionClient: TextConversionClient {
    var result = ""

    init(result: String = "") {
        self.result = result
    }

    func convert(_ request: ConversionRequest) async throws -> String {
        result
    }
}

final class InMemoryLanguageSettingsStore: LanguageSettingsStore {
    private let initialSettings: LanguageSettings
    private(set) var savedSettings: LanguageSettings?

    init(initial: LanguageSettings = .default) {
        self.initialSettings = initial
    }

    func load() -> LanguageSettings {
        savedSettings ?? initialSettings
    }

    func save(_ settings: LanguageSettings) throws {
        savedSettings = settings
    }
}
