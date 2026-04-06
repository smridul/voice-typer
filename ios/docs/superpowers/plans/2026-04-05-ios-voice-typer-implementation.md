# VoiceTyper iOS Keyboard Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the iOS host app and custom keyboard extension that records audio, sends it to Groq Whisper, previews the transcript, and inserts the text into the active text field.

**Architecture:** Use `XcodeGen` to create a two-target iOS project from a checked-in `project.yml`, with the keyboard extension implemented as a thin `UIInputViewController` hosting a SwiftUI view. Keep testable logic out of UIKit and AVFoundation wrappers by isolating state management, WAV encoding, request construction, and transcript insertion into focused Swift files with XCTest coverage.

**Tech Stack:** Swift 5, SwiftUI, UIKit keyboard extensions, AVFoundation, URLSession, XCTest, XcodeGen

---

## Prerequisites

- Full Xcode must be installed and selected before any `xcodebuild` command works:

```bash
sudo xcode-select -s /Applications/Xcode.app
```

- `xcodegen` is already available at `/opt/homebrew/bin/xcodegen`; use it instead of hand-editing `project.pbxproj`.
- The only runtime-specific input is the personal Groq API key required by the spec. Paste the real key into `Shared/Config.swift` before device-level transcription tests.

## File Map

- `project.yml`
  Declares the app target, keyboard extension target, and test bundles; generates `VoiceTyper.xcodeproj`.
- `.gitignore`
  Ignores Xcode user data and DerivedData noise.
- `Shared/Config.swift`
  Holds the Groq API host, model name, language, and hardcoded API key constant consumed by both targets.
- `VoiceTyper/VoiceTyperApp.swift`
  App entry point that shows the setup instructions screen.
- `VoiceTyper/SetupInstructions.swift`
  Centralizes the onboarding copy so it can be unit-tested.
- `VoiceTyper/SetupView.swift`
  Renders the setup instructions and “Allow Full Access” explanation.
- `VoiceTyper/Info.plist`
  App metadata and microphone usage string.
- `VoiceTyper/Assets.xcassets/...`
  Minimal app icon and accent color catalog scaffolding.
- `VoiceTyperKeyboard/KeyboardViewController.swift`
  Hosts the SwiftUI keyboard view and bridges `textDocumentProxy` / `needsInputModeSwitchKey`.
- `VoiceTyperKeyboard/KeyboardStore.swift`
  `ObservableObject` state machine for idle, recording, transcribing, result, and error states.
- `VoiceTyperKeyboard/KeyboardView.swift`
  SwiftUI keyboard UI bound to `KeyboardStore`.
- `VoiceTyperKeyboard/AudioRecorder.swift`
  Thin AVAudioEngine wrapper that records mono PCM audio.
- `VoiceTyperKeyboard/WAVEncoder.swift`
  Converts raw PCM bytes into WAV data for Groq Whisper.
- `VoiceTyperKeyboard/WhisperService.swift`
  Builds the multipart request, sends it with `URLSession`, and parses the transcription response.
- `VoiceTyperKeyboard/TextInsertionCoordinator.swift`
  Small adapter that inserts transcript text and resets state after insertion.
- `VoiceTyperKeyboard/Info.plist`
  Keyboard extension metadata, full-access requirements, and microphone usage string.
- `VoiceTyperTests/SetupInstructionsTests.swift`
  Verifies the setup copy matches the spec.
- `VoiceTyperKeyboardTests/KeyboardStoreTests.swift`
  Verifies state transitions and error mapping.
- `VoiceTyperKeyboardTests/WAVEncoderTests.swift`
  Verifies WAV header fields and payload sizing.
- `VoiceTyperKeyboardTests/WhisperServiceTests.swift`
  Verifies request construction and response parsing.
- `VoiceTyperKeyboardTests/TextInsertionCoordinatorTests.swift`
  Verifies transcript insertion and reset behavior without touching UIKit.

### Task 1: Bootstrap the Xcode Project Shell

**Files:**
- Create: `project.yml`
- Create: `.gitignore`
- Create: `VoiceTyper/Info.plist`
- Create: `VoiceTyperKeyboard/Info.plist`
- Create: `VoiceTyper/Assets.xcassets/Contents.json`
- Create: `VoiceTyper/Assets.xcassets/AccentColor.colorset/Contents.json`
- Create: `VoiceTyper/Assets.xcassets/AppIcon.appiconset/Contents.json`
- Create: `VoiceTyperKeyboard/Resources/`
- Generate: `VoiceTyper.xcodeproj`

- [ ] **Step 1: Create the project generator file and repo scaffolding**

Project generation is the one explicit TDD exception in this plan because the test bundles cannot compile until the targets exist.

```yaml
name: VoiceTyper
options:
  deploymentTarget:
    iOS: "17.0"
settings:
  base:
    SWIFT_VERSION: 5.0
    DEVELOPMENT_TEAM: ""
targets:
  VoiceTyper:
    type: application
    platform: iOS
    sources:
      - path: VoiceTyper
      - path: Shared
    info:
      path: VoiceTyper/Info.plist
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.mridul.voice-typer
        PRODUCT_NAME: VoiceTyper
        ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon
        CODE_SIGN_ENTITLEMENTS: ""
    dependencies: []
  VoiceTyperKeyboard:
    type: app-extension
    platform: iOS
    sources:
      - path: VoiceTyperKeyboard
      - path: Shared
    info:
      path: VoiceTyperKeyboard/Info.plist
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.mridul.voice-typer.keyboard
        PRODUCT_NAME: VoiceTyperKeyboard
  VoiceTyperTests:
    type: bundle.unit-test
    platform: iOS
    sources:
      - path: VoiceTyperTests
    dependencies:
      - target: VoiceTyper
  VoiceTyperKeyboardTests:
    type: bundle.unit-test
    platform: iOS
    sources:
      - path: VoiceTyperKeyboardTests
    dependencies:
      - target: VoiceTyperKeyboard
```

- [ ] **Step 2: Add the minimal plist and asset catalog files expected by both targets**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>$(DEVELOPMENT_LANGUAGE)</string>
  <key>CFBundleExecutable</key>
  <string>$(EXECUTABLE_NAME)</string>
  <key>CFBundleIdentifier</key>
  <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
  <key>CFBundleName</key>
  <string>$(PRODUCT_NAME)</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSRequiresIPhoneOS</key>
  <true/>
  <key>NSMicrophoneUsageDescription</key>
  <string>VoiceTyper needs microphone access so you can dictate text.</string>
  <key>UIApplicationSceneManifest</key>
  <dict/>
</dict>
</plist>
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>$(DEVELOPMENT_LANGUAGE)</string>
  <key>CFBundleExecutable</key>
  <string>$(EXECUTABLE_NAME)</string>
  <key>CFBundleIdentifier</key>
  <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
  <key>CFBundleName</key>
  <string>$(PRODUCT_NAME)</string>
  <key>CFBundlePackageType</key>
  <string>XPC!</string>
  <key>NSExtension</key>
  <dict>
    <key>NSExtensionAttributes</key>
    <dict>
      <key>RequestsOpenAccess</key>
      <true/>
      <key>PrimaryLanguage</key>
      <string>en</string>
    </dict>
    <key>NSExtensionPointIdentifier</key>
    <string>com.apple.keyboard-service</string>
    <key>NSExtensionPrincipalClass</key>
    <string>$(PRODUCT_MODULE_NAME).KeyboardViewController</string>
  </dict>
  <key>NSMicrophoneUsageDescription</key>
  <string>VoiceTyper needs microphone access so you can dictate text.</string>
</dict>
</plist>
```

```json
{
  "info": {
    "author": "xcode",
    "version": 1
  }
}
```

- [ ] **Step 3: Generate the Xcode project**

Run: `xcodegen generate`

Expected: `Generated project at /Users/mridulshrivastava/code/voice-typer/ios/VoiceTyper.xcodeproj`

- [ ] **Step 4: Verify the project and schemes exist**

Run: `xcodebuild -list -project VoiceTyper.xcodeproj`

Expected: `Targets:` includes `VoiceTyper`, `VoiceTyperKeyboard`, `VoiceTyperTests`, and `VoiceTyperKeyboardTests`

- [ ] **Step 5: Commit the scaffold**

```bash
git add .gitignore project.yml VoiceTyper VoiceTyperKeyboard VoiceTyper.xcodeproj
git commit -m "chore: scaffold voice typer ios targets"
```

### Task 2: Build the Host App Setup Screen and Shared Config

**Files:**
- Create: `Shared/Config.swift`
- Create: `VoiceTyper/SetupInstructions.swift`
- Create: `VoiceTyper/VoiceTyperApp.swift`
- Create: `VoiceTyper/SetupView.swift`
- Create: `VoiceTyperTests/SetupInstructionsTests.swift`
- Modify: `project.yml`

- [ ] **Step 1: Write the failing setup-copy test**

```swift
import XCTest
@testable import VoiceTyper

final class SetupInstructionsTests: XCTestCase {
    func test_defaultSteps_matchTheKeyboardEnableFlow() {
        XCTAssertEqual(
            SetupInstructions.defaultSteps,
            [
                "Open Settings > General > Keyboard > Keyboards > Add New Keyboard > select \"VoiceTyper\"",
                "Tap VoiceTyper > enable \"Allow Full Access\" (required for microphone + network access)"
            ]
        )
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: FAIL with `Cannot find 'SetupInstructions' in scope`

- [ ] **Step 3: Add the minimal shared config and setup instructions**

```swift
enum Config {
    static let groqAPIKey = ""
    static let groqHost = "https://api.groq.com/openai/v1/audio/transcriptions"
    static let whisperModel = "whisper-large-v3"
    static let language = "en"
}

enum SetupInstructions {
    static let defaultSteps = [
        "Open Settings > General > Keyboard > Keyboards > Add New Keyboard > select \"VoiceTyper\"",
        "Tap VoiceTyper > enable \"Allow Full Access\" (required for microphone + network access)"
    ]
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: PASS for `SetupInstructionsTests`

- [ ] **Step 5: Render the setup screen in SwiftUI**

```swift
import SwiftUI

@main
struct VoiceTyperApp: App {
    var body: some Scene {
        WindowGroup {
            SetupView()
        }
    }
}
```

```swift
import SwiftUI

struct SetupView: View {
    var body: some View {
        NavigationStack {
            List {
                Section("Enable the keyboard") {
                    ForEach(Array(SetupInstructions.defaultSteps.enumerated()), id: \.offset) { index, step in
                        Label {
                            Text(step)
                        } icon: {
                            Text("\(index + 1).")
                        }
                    }
                }

                Section("Why full access is required") {
                    Text("VoiceTyper uses the microphone and sends audio to Groq Whisper to transcribe your speech.")
                        .font(.body)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("VoiceTyper")
        }
    }
}
```

- [ ] **Step 6: Re-run the host app tests after wiring the UI**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: PASS with no new warnings

- [ ] **Step 7: Commit the host app**

```bash
git add Shared/Config.swift VoiceTyper VoiceTyperTests project.yml
git commit -m "feat: add ios setup screen"
```

### Task 3: Add the Keyboard State Machine and SwiftUI Keyboard UI

**Files:**
- Create: `VoiceTyperKeyboard/KeyboardStore.swift`
- Create: `VoiceTyperKeyboard/KeyboardView.swift`
- Create: `VoiceTyperKeyboardTests/KeyboardStoreTests.swift`
- Modify: `project.yml`

- [ ] **Step 1: Write the failing state-transition tests**

```swift
import XCTest
@testable import VoiceTyperKeyboard

final class KeyboardStoreTests: XCTestCase {
    @MainActor
    func test_stopRecording_transitionsToTranscribing() async {
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(),
            whisperService: FakeWhisperService(transcript: "hello world")
        )

        await store.toggleRecording()
        await store.toggleRecording()

        XCTAssertEqual(store.phase, .transcribing)
        XCTAssertEqual(store.previewText, "Transcribing...")
    }

    @MainActor
    func test_clear_resetsThePreview() {
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(),
            whisperService: FakeWhisperService(transcript: "hello world")
        )
        store.previewText = "hello world"
        store.phase = .result

        store.clear()

        XCTAssertEqual(store.phase, .idle)
        XCTAssertEqual(store.previewText, "Tap mic to start...")
    }
}
```

- [ ] **Step 2: Run the keyboard tests to verify they fail**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: FAIL with `Cannot find 'KeyboardStore' in scope`

- [ ] **Step 3: Implement the minimal state container and dependency protocols**

```swift
import Combine
import Foundation

protocol AudioRecording {
    func start() async throws
    func stop() async throws -> Data
}

protocol WhisperServicing {
    func transcribe(audioData: Data) async throws -> String
}

@MainActor
final class KeyboardStore: ObservableObject {
    enum Phase: Equatable {
        case idle
        case recording
        case transcribing
        case result
        case error(message: String)
    }

    @Published var phase: Phase = .idle
    @Published var previewText = "Tap mic to start..."

    private let audioRecorder: AudioRecording
    private let whisperService: WhisperServicing

    init(audioRecorder: AudioRecording, whisperService: WhisperServicing) {
        self.audioRecorder = audioRecorder
        self.whisperService = whisperService
    }

    func toggleRecording() async {
        switch phase {
        case .idle, .result, .error:
            do {
                try await audioRecorder.start()
                phase = .recording
                previewText = "Listening..."
            } catch {
                phase = .error(message: "Enable Full Access in Settings")
                previewText = "Enable Full Access in Settings"
            }
        case .recording:
            phase = .transcribing
            previewText = "Transcribing..."
        case .transcribing:
            return
        }
    }

    func clear() {
        phase = .idle
        previewText = "Tap mic to start..."
    }
}
```

- [ ] **Step 4: Run the keyboard tests to verify they pass**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: PASS for `KeyboardStoreTests`

- [ ] **Step 5: Render the keyboard UI against the store state**

```swift
import SwiftUI

struct KeyboardView: View {
    @ObservedObject var store: KeyboardStore
    let showsGlobeKey: Bool
    let onGlobeTap: () -> Void
    let onReturnTap: () -> Void
    let onInsertTap: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Text(store.previewText)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))

            Button {
                Task { await store.toggleRecording() }
            } label: {
                Image(systemName: store.phase == .recording ? "stop.fill" : "mic.fill")
                    .font(.system(size: 28, weight: .semibold))
                    .frame(width: 72, height: 72)
            }
            .buttonStyle(.borderedProminent)
            .tint(store.phase == .recording ? .red : .accentColor)
            .disabled(store.phase == .transcribing)

            HStack {
                if showsGlobeKey {
                    Button(action: onGlobeTap) {
                        Image(systemName: "globe")
                    }
                }

                Spacer()

                if store.phase == .result {
                    Button("Insert", action: onInsertTap)
                    Button("Clear", action: store.clear)
                } else {
                    Button("Return", action: onReturnTap)
                }
            }
        }
        .padding()
        .frame(height: 260)
        .background(Color(uiColor: .systemBackground))
    }
}
```

- [ ] **Step 6: Re-run the keyboard tests after the UI is attached**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: PASS with no UI-driven regressions

- [ ] **Step 7: Commit the keyboard state/UI layer**

```bash
git add VoiceTyperKeyboard VoiceTyperKeyboardTests project.yml
git commit -m "feat: add keyboard state and ui"
```

### Task 4: Add Audio Capture and WAV Encoding

**Files:**
- Create: `VoiceTyperKeyboard/AudioRecorder.swift`
- Create: `VoiceTyperKeyboard/WAVEncoder.swift`
- Create: `VoiceTyperKeyboardTests/WAVEncoderTests.swift`

- [ ] **Step 1: Write the failing WAV encoder tests**

```swift
import XCTest
@testable import VoiceTyperKeyboard

final class WAVEncoderTests: XCTestCase {
    func test_encode_wrapsPCMAs16BitMono16kHzWAV() throws {
        let pcm = Data([0x00, 0x00, 0xFF, 0x7F])

        let wav = try WAVEncoder.encode(
            pcmData: pcm,
            sampleRate: 16_000,
            channels: 1,
            bitsPerSample: 16
        )

        XCTAssertEqual(String(decoding: wav.prefix(4), as: UTF8.self), "RIFF")
        XCTAssertEqual(String(decoding: wav.dropFirst(8).prefix(4), as: UTF8.self), "WAVE")
        XCTAssertEqual(wav.count, pcm.count + 44)
    }
}
```

- [ ] **Step 2: Run the encoder tests to verify they fail**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: FAIL with `Cannot find 'WAVEncoder' in scope`

- [ ] **Step 3: Implement the WAV encoder and AVAudioEngine wrapper**

```swift
import Foundation

enum WAVEncoder {
    static func encode(
        pcmData: Data,
        sampleRate: Int,
        channels: Int,
        bitsPerSample: Int
    ) throws -> Data {
        let byteRate = sampleRate * channels * bitsPerSample / 8
        let blockAlign = channels * bitsPerSample / 8

        var data = Data()
        data.append("RIFF".data(using: .ascii)!)
        data.append(UInt32(pcmData.count + 36).littleEndianData)
        data.append("WAVEfmt ".data(using: .ascii)!)
        data.append(UInt32(16).littleEndianData)
        data.append(UInt16(1).littleEndianData)
        data.append(UInt16(channels).littleEndianData)
        data.append(UInt32(sampleRate).littleEndianData)
        data.append(UInt32(byteRate).littleEndianData)
        data.append(UInt16(blockAlign).littleEndianData)
        data.append(UInt16(bitsPerSample).littleEndianData)
        data.append("data".data(using: .ascii)!)
        data.append(UInt32(pcmData.count).littleEndianData)
        data.append(pcmData)
        return data
    }
}

private extension FixedWidthInteger {
    var littleEndianData: Data {
        withUnsafeBytes(of: self.littleEndian) { Data($0) }
    }
}
```

```swift
import AVFoundation

final class AudioRecorder: AudioRecording {
    private let engine = AVAudioEngine()
    private var capturedData = Data()
    private let maxBytes = 3_800_000

    func start() async throws {
        capturedData.removeAll(keepingCapacity: true)
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)

        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            guard let self else { return }
            guard let channel = buffer.int16ChannelData?.pointee else { return }

            let frameCount = Int(buffer.frameLength)
            let chunk = Data(bytes: channel, count: frameCount * MemoryLayout<Int16>.size)
            if self.capturedData.count + chunk.count <= self.maxBytes {
                self.capturedData.append(chunk)
            }
        }

        engine.prepare()
        try engine.start()
    }

    func stop() async throws -> Data {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        return capturedData
    }
}
```

- [ ] **Step 4: Run the encoder tests to verify they pass**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: PASS for `WAVEncoderTests`

- [ ] **Step 5: Manually verify recording starts and stops without crashing**

Run the `VoiceTyper` app on a physical iPhone, enable the keyboard in Settings, open the keyboard in Notes, tap the mic once to start and once to stop.

Expected: preview changes from `Tap mic to start...` to `Listening...` to `Transcribing...`

- [ ] **Step 6: Commit the recording layer**

```bash
git add VoiceTyperKeyboard/AudioRecorder.swift VoiceTyperKeyboard/WAVEncoder.swift VoiceTyperKeyboardTests/WAVEncoderTests.swift
git commit -m "feat: add audio recording and wav encoding"
```

### Task 5: Add Whisper Networking and Response Parsing

**Files:**
- Create: `VoiceTyperKeyboard/WhisperService.swift`
- Create: `VoiceTyperKeyboardTests/WhisperServiceTests.swift`

- [ ] **Step 1: Write the failing request-construction and parsing tests**

```swift
import XCTest
@testable import VoiceTyperKeyboard

final class WhisperServiceTests: XCTestCase {
    func test_makeRequest_setsAuthHeaderAndMultipartBody() throws {
        let request = try WhisperService.makeRequest(
            audioData: Data([0x00, 0x01]),
            apiKey: "test-key"
        )

        XCTAssertEqual(request.url?.absoluteString, Config.groqHost)
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer test-key")
        XCTAssertTrue(String(decoding: request.httpBody ?? Data(), as: UTF8.self).contains("whisper-large-v3"))
        XCTAssertTrue(String(decoding: request.httpBody ?? Data(), as: UTF8.self).contains("audio.wav"))
    }

    func test_parseResponse_returnsTranscriptText() throws {
        let data = #"{"text":"hello world"}"#.data(using: .utf8)!
        XCTAssertEqual(try WhisperService.parseResponse(data), "hello world")
    }

    @MainActor
    func test_stopRecording_transcribesAndShowsResult() async {
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(data: Data([0x00, 0x00, 0xFF, 0x7F])),
            whisperService: FakeWhisperService(transcript: "hello world")
        )

        await store.toggleRecording()
        await store.toggleRecording()

        XCTAssertEqual(store.phase, .result)
        XCTAssertEqual(store.previewText, "hello world")
    }
}
```

- [ ] **Step 2: Run the keyboard tests to verify they fail**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: FAIL with `Type 'WhisperService' has no member 'makeRequest'`

- [ ] **Step 3: Implement the request builder and live transcription client**

```swift
import Foundation

struct WhisperService: WhisperServicing {
    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func transcribe(audioData: Data) async throws -> String {
        let request = try Self.makeRequest(audioData: audioData, apiKey: Config.groqAPIKey)
        let (data, _) = try await session.data(for: request)
        return try Self.parseResponse(data)
    }

    static func makeRequest(audioData: Data, apiKey: String) throws -> URLRequest {
        let boundary = UUID().uuidString
        var request = URLRequest(url: URL(string: Config.groqHost)!)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = multipartBody(audioData: audioData, boundary: boundary)
        return request
    }

    static func parseResponse(_ data: Data) throws -> String {
        let response = try JSONDecoder().decode(Response.self, from: data)
        return response.text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func multipartBody(audioData: Data, boundary: String) -> Data {
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"model\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(Config.whisperModel)\r\n".data(using: .utf8)!)
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"language\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(Config.language)\r\n".data(using: .utf8)!)
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/wav\r\n\r\n".data(using: .utf8)!)
        body.append(audioData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        return body
    }

    private struct Response: Decodable {
        let text: String
    }
}
```

- [ ] **Step 4: Run the keyboard tests to verify they pass**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: PASS for `WhisperServiceTests`

- [ ] **Step 5: Add error mapping for network and empty-transcript cases inside `KeyboardStore`**

```swift
case .recording:
    do {
        let pcmData = try await audioRecorder.stop()
        let wavData = try WAVEncoder.encode(
            pcmData: pcmData,
            sampleRate: 16_000,
            channels: 1,
            bitsPerSample: 16
        )
        let transcript = try await whisperService.transcribe(audioData: wavData)

        if transcript.isEmpty {
            phase = .error(message: "No speech detected")
            previewText = "No speech detected"
        } else {
            phase = .result
            previewText = transcript
        }
    } catch let error as URLError where error.code == .notConnectedToInternet {
        phase = .error(message: "No connection")
        previewText = "No connection"
    } catch {
        phase = .error(message: "Enable Full Access in Settings")
        previewText = "Enable Full Access in Settings"
    }
}
```

- [ ] **Step 6: Commit the networking layer**

```bash
git add VoiceTyperKeyboard/WhisperService.swift VoiceTyperKeyboard/KeyboardStore.swift VoiceTyperKeyboardTests/WhisperServiceTests.swift
git commit -m "feat: add groq whisper transcription"
```

### Task 6: Wire Text Insertion, the Keyboard Controller, and End-to-End Errors

**Files:**
- Create: `VoiceTyperKeyboard/TextInsertionCoordinator.swift`
- Create: `VoiceTyperKeyboard/KeyboardViewController.swift`
- Create: `VoiceTyperKeyboardTests/TextInsertionCoordinatorTests.swift`
- Modify: `VoiceTyperKeyboard/KeyboardView.swift`
- Modify: `VoiceTyperKeyboard/KeyboardStore.swift`

- [ ] **Step 1: Write the failing insertion test**

```swift
import XCTest
@testable import VoiceTyperKeyboard

final class TextInsertionCoordinatorTests: XCTestCase {
    func test_insert_transcriptWritesTextAndResetsStore() {
        let proxy = FakeTextDocumentProxy()
        let store = KeyboardStore(
            audioRecorder: FakeAudioRecorder(),
            whisperService: FakeWhisperService(transcript: "hello world")
        )
        store.previewText = "hello world"
        store.phase = .result

        let coordinator = TextInsertionCoordinator(insertText: proxy.insertText(_:))
        coordinator.insertCurrentTranscript(from: store)

        XCTAssertEqual(proxy.insertedTexts, ["hello world"])
        XCTAssertEqual(store.phase, .idle)
        XCTAssertEqual(store.previewText, "Tap mic to start...")
    }
}
```

- [ ] **Step 2: Run the keyboard tests to verify they fail**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: FAIL with `Cannot find 'TextInsertionCoordinator' in scope`

- [ ] **Step 3: Implement the insertion coordinator**

```swift
import Foundation

struct TextInsertionCoordinator {
    let insertText: (String) -> Void

    func insertCurrentTranscript(from store: KeyboardStore) {
        guard store.phase == .result else { return }
        let transcript = store.previewText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !transcript.isEmpty else { return }
        insertText(transcript)
        store.clear()
    }
}
```

- [ ] **Step 4: Host the SwiftUI keyboard inside `UIInputViewController`**

```swift
import SwiftUI
import UIKit

final class KeyboardViewController: UIInputViewController {
    private lazy var store = KeyboardStore(
        audioRecorder: AudioRecorder(),
        whisperService: WhisperService()
    )

    override func viewDidLoad() {
        super.viewDidLoad()

        let rootView = KeyboardView(
            store: store,
            showsGlobeKey: needsInputModeSwitchKey,
            onGlobeTap: { [weak self] in self?.advanceToNextInputMode() },
            onReturnTap: { [weak self] in self?.textDocumentProxy.insertText("\n") },
            onInsertTap: { [weak self] in
                guard let self else { return }
                TextInsertionCoordinator(insertText: self.textDocumentProxy.insertText(_:))
                    .insertCurrentTranscript(from: self.store)
            }
        )

        let hostingController = UIHostingController(rootView: rootView)
        addChild(hostingController)
        hostingController.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(hostingController.view)
        NSLayoutConstraint.activate([
            hostingController.view.topAnchor.constraint(equalTo: view.topAnchor),
            hostingController.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            hostingController.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            hostingController.view.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
        hostingController.didMove(toParent: self)
    }
}
```

- [ ] **Step 5: Verify the keyboard tests pass after integration**

Run: `xcodebuild test -project VoiceTyper.xcodeproj -scheme VoiceTyperKeyboardTests -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: PASS for `KeyboardStoreTests`, `WAVEncoderTests`, `WhisperServiceTests`, and `TextInsertionCoordinatorTests`

- [ ] **Step 6: Manually verify the spec error cases on device**

Use the keyboard inside Notes and verify:

- Full access disabled: preview shows `Enable Full Access in Settings`
- Microphone denied: preview shows `Enable Full Access in Settings`
- Airplane mode enabled: preview shows `No connection`
- Silent recording: preview shows `No speech detected`
- Successful transcription: preview shows transcript and `Insert` writes text at the cursor

- [ ] **Step 7: Commit the integrated keyboard extension**

```bash
git add VoiceTyperKeyboard VoiceTyperKeyboardTests
git commit -m "feat: integrate voice typer keyboard extension"
```

## Self-Review

- Spec coverage:
  The plan covers the host app instructions, keyboard idle/recording/transcribing/result states, Groq Whisper integration, WAV conversion, insertion at the cursor, full-access/microphone/network/silence error handling, and the extension/app plist requirements. The only intentionally external prerequisite is selecting full Xcode and pasting the personal Groq API key before live transcription tests.
- Placeholder scan:
  There are no `TODO` or `TBD` markers. The only empty string is the API key literal in `Shared/Config.swift`, which must be replaced with the user’s actual personal key to satisfy the spec’s hardcoded-key requirement.
- Type consistency:
  The plan uses `KeyboardStore`, `AudioRecording`, `WhisperServicing`, `WAVEncoder`, `WhisperService`, and `TextInsertionCoordinator` consistently across tasks.
