import Combine
import Foundation

public protocol AudioRecording {
    func start() async throws
    func stop() async throws -> Data
}

public protocol TranscriptionClient {
    func transcribe(audioData: Data, language: LanguageCode) async throws -> String
}

public protocol TextConversionClient {
    func convert(_ request: ConversionRequest) async throws -> String
}

public protocol LanguageSettingsStore {
    func load() -> LanguageSettings
    func save(_ settings: LanguageSettings) throws
}

@MainActor
public final class KeyboardStore: ObservableObject {
    public enum Phase: Equatable {
        case idle
        case recording
        case transcribing
        case result
        case error(message: String)
    }

    @Published public var phase: Phase = .idle
    @Published public var previewText = "Tap mic to start..."
    @Published public var languageSettings: LanguageSettings

    private let audioRecorder: AudioRecording
    private let transcriptionClient: TranscriptionClient
    private let textConversionClient: TextConversionClient
    private let settingsStore: LanguageSettingsStore

    public init(
        audioRecorder: AudioRecording,
        transcriptionClient: TranscriptionClient,
        textConversionClient: TextConversionClient,
        settingsStore: LanguageSettingsStore
    ) {
        self.audioRecorder = audioRecorder
        self.transcriptionClient = transcriptionClient
        self.textConversionClient = textConversionClient
        self.settingsStore = settingsStore
        self.languageSettings = settingsStore.load()
    }

    public func toggleRecording() async {
        switch phase {
        case .idle, .result, .error:
            do {
                try await audioRecorder.start()
                phase = .recording
                previewText = "Listening..."
            } catch {
                let nsErr = error as NSError
                let msg = error.localizedDescription
                print("VoiceTyper mic error: \(nsErr)")
                print("VoiceTyper mic error userInfo: \(nsErr.userInfo)")
                phase = .error(message: msg)
                previewText = msg
            }
        case .recording:
            phase = .transcribing
            previewText = "Transcribing..."

            do {
                let audioData = try await audioRecorder.stop()
                let transcript = try await transcriptionClient.transcribe(
                    audioData: audioData,
                    language: languageSettings.contextLanguage
                )
                let converter = LanguageConverter()
                let conversion = try converter.convert(
                    transcript: transcript,
                    contextLanguage: languageSettings.contextLanguage,
                    outputLanguage: languageSettings.outputLanguage
                )

                switch conversion {
                case .final(let text):
                    if text.isEmpty {
                        phase = .error(message: "No speech detected")
                        previewText = "No speech detected"
                    } else {
                        phase = .result
                        previewText = text
                    }
                case .requiresModel(let request):
                    let converted = try await textConversionClient.convert(request)
                    let finalText = try converter.finalizeModelOutput(converted, outputLanguage: languageSettings.outputLanguage)
                    phase = .result
                    previewText = finalText
                }
            } catch {
                phase = .error(message: "No connection")
                previewText = "No connection"
            }
        case .transcribing:
            return
        }
    }

    public func updateContextLanguage(_ language: LanguageCode) throws {
        languageSettings.contextLanguage = language
        try settingsStore.save(languageSettings)
    }

    public func updateOutputLanguage(_ language: LanguageCode) throws {
        languageSettings.outputLanguage = language
        try settingsStore.save(languageSettings)
    }

    public func clear() {
        phase = .idle
        previewText = "Tap mic to start..."
    }
}
