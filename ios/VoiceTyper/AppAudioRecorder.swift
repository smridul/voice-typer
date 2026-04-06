import AVFoundation
import Foundation
import VoiceTyperCore

final class AppAudioRecorder: AudioRecording {
    private var recorder: AVAudioRecorder?
    private var fileURL: URL?

    func start() async throws {
        if !(await requestPermissionIfNeeded()) {
            throw RecorderError.permissionDenied
        }

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
        try session.setActive(true)

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("voice_\(UUID().uuidString).wav")

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16_000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsFloatKey: false,
        ]

        let recorder = try AVAudioRecorder(url: url, settings: settings)
        recorder.prepareToRecord()

        guard recorder.record() else {
            throw RecorderError.failedToStart
        }

        self.recorder = recorder
        self.fileURL = url
    }

    func stop() async throws -> Data {
        guard let recorder, let fileURL else {
            throw RecorderError.noRecording
        }

        recorder.stop()
        self.recorder = nil
        self.fileURL = nil

        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)

        let data = try Data(contentsOf: fileURL)
        try? FileManager.default.removeItem(at: fileURL)
        return data
    }

    private func requestPermissionIfNeeded() async -> Bool {
        let session = AVAudioSession.sharedInstance()

        switch session.recordPermission {
        case .granted:
            return true
        case .denied:
            return false
        case .undetermined:
            return await withCheckedContinuation { continuation in
                session.requestRecordPermission { granted in
                    continuation.resume(returning: granted)
                }
            }
        @unknown default:
            return false
        }
    }

    enum RecorderError: Error, LocalizedError {
        case permissionDenied
        case failedToStart
        case noRecording

        var errorDescription: String? {
            switch self {
            case .permissionDenied:
                return "Microphone permission is required in the VoiceTyper app."
            case .failedToStart:
                return "Recording could not start."
            case .noRecording:
                return "No recording found."
            }
        }
    }
}
