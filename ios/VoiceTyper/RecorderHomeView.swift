import SwiftUI
import UIKit
import VoiceTyperCore

struct RecorderHomeView: View {
    @StateObject private var store: KeyboardStore
    private let transcriptStore: LatestTranscriptStore

    init() {
        let settingsStore = UserDefaultsLanguageSettingsStore(suiteName: Config.appGroupIdentifier)
        _store = StateObject(wrappedValue: KeyboardStore(
            audioRecorder: AppAudioRecorder(),
            transcriptionClient: WhisperTranscriptionClient(),
            textConversionClient: GroqTextConversionClient(),
            settingsStore: settingsStore
        ))
        transcriptStore = LatestTranscriptStore(suiteName: Config.appGroupIdentifier)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("VoiceTyper")
                    .font(.largeTitle.bold())

                Text("Record here, then switch back to the keyboard and tap Insert Last.")
                    .font(.body)

                languagePickers

                ScrollView {
                    Text(store.previewText)
                        .font(.body)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(maxWidth: .infinity, minHeight: 120)
                .padding(12)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 16))

                Button {
                    Task { await store.toggleRecording() }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: store.phase == .recording ? "stop.fill" : "mic.fill")
                        Text(buttonTitle)
                    }
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                }
                .buttonStyle(.borderedProminent)
                .tint(store.phase == .recording ? .red : .accentColor)
                .disabled(store.phase == .transcribing)
            }
            .padding(.horizontal)
            .padding(.bottom)
            .padding(.top, -12)
        }
        .onChange(of: store.phase) { phase in
            guard phase == .result else {
                return
            }

            transcriptStore.save(store.previewText)
            UIPasteboard.general.string = store.previewText
        }
    }

    private var buttonTitle: String {
        switch store.phase {
        case .recording:
            return "Stop Recording"
        case .transcribing:
            return "Transcribing..."
        default:
            return "Start Recording"
        }
    }

    private var languagePickers: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Context")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Picker("Context", selection: Binding(
                    get: { store.languageSettings.contextLanguage },
                    set: { try? store.updateContextLanguage($0) }
                )) {
                    ForEach(LanguageCode.allCases, id: \.self) { language in
                        Text(language.label).tag(language)
                    }
                }
                .pickerStyle(.segmented)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Output")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Picker("Output", selection: Binding(
                    get: { store.languageSettings.outputLanguage },
                    set: { try? store.updateOutputLanguage($0) }
                )) {
                    ForEach(LanguageCode.allCases, id: \.self) { language in
                        Text(language.label).tag(language)
                    }
                }
                .pickerStyle(.segmented)
            }
        }
    }
}
