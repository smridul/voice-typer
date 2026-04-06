import Foundation
import VoiceTyperCore

final class KeyboardAudioRecorder: AudioRecording {
    func start() async throws {
        throw RecorderError.unsupportedInKeyboardExtension
    }

    func stop() async throws -> Data {
        throw RecorderError.noRecording
    }

    enum RecorderError: Error, LocalizedError {
        case unsupportedInKeyboardExtension
        case noRecording

        var errorDescription: String? {
            switch self {
            case .unsupportedInKeyboardExtension:
                return "iOS does not allow third-party keyboards to access the microphone directly. Use the containing app or system dictation for voice input."
            case .noRecording: return "No recording found"
            }
        }
    }
}
