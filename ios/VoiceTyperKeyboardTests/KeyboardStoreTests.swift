import XCTest
@testable import VoiceTyperCore

final class KeyboardExtensionStoreTests: XCTestCase {
    @MainActor
    func test_stopRecording_completesFlow() async {
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(),
            transcriptionClient: FakeTranscriptionClient(result: "hello"),
            textConversionClient: FakeTextConversionClient(),
            settingsStore: InMemorySettingsStore()
        )

        await store.toggleRecording()
        await store.toggleRecording()

        XCTAssertEqual(store.phase, .result)
        XCTAssertEqual(store.previewText, "hello")
    }

    @MainActor
    func test_clear_resetsThePreview() {
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(),
            transcriptionClient: FakeTranscriptionClient(),
            textConversionClient: FakeTextConversionClient(),
            settingsStore: InMemorySettingsStore()
        )
        store.previewText = "hello world"
        store.phase = .result

        store.clear()

        XCTAssertEqual(store.phase, .idle)
        XCTAssertEqual(store.previewText, "Tap mic to start...")
    }
}

private struct FakeAudioRecorder: AudioRecording {
    func start() async throws {}
    func stop() async throws -> Data { Data() }
}

private final class FakeTranscriptionClient: TranscriptionClient {
    let result: String
    init(result: String = "") { self.result = result }
    func transcribe(audioData: Data, language: LanguageCode) async throws -> String { result }
}

private struct FakeTextConversionClient: TextConversionClient {
    func convert(_ request: ConversionRequest) async throws -> String { "" }
}

private final class InMemorySettingsStore: LanguageSettingsStore {
    func load() -> LanguageSettings { .default }
    func save(_ settings: LanguageSettings) throws {}
}
