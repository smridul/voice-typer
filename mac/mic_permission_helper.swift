import AVFAudio
import Foundation

let permission = AVAudioApplication.shared.recordPermission

switch permission {
case .granted:
    exit(EXIT_SUCCESS)
case .denied:
    fputs("Microphone access denied.\n", stderr)
    exit(EXIT_FAILURE)
case .undetermined:
    let semaphore = DispatchSemaphore(value: 0)
    var granted = false

    AVAudioApplication.requestRecordPermission { allowed in
        granted = allowed
        semaphore.signal()
    }

    _ = semaphore.wait(timeout: .now() + 30)
    if granted {
        exit(EXIT_SUCCESS)
    }

    fputs("Microphone access not granted.\n", stderr)
    exit(EXIT_FAILURE)
@unknown default:
    fputs("Unknown microphone permission state.\n", stderr)
    exit(EXIT_FAILURE)
}
