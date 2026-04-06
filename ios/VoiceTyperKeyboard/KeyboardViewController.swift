import SwiftUI
import UIKit

final class KeyboardViewController: UIInputViewController {
    private let transcriptStore = LatestTranscriptStore(suiteName: Config.appGroupIdentifier)

    private lazy var hostingController = UIHostingController(rootView: makeKeyboardView())

    override func viewDidLoad() {
        super.viewDidLoad()

        let hostingController = hostingController
        addChild(hostingController)
        hostingController.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(hostingController.view)
        NSLayoutConstraint.activate([
            hostingController.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            hostingController.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            hostingController.view.topAnchor.constraint(equalTo: view.topAnchor),
            hostingController.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
        hostingController.didMove(toParent: self)
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        refreshKeyboardView()
    }

    override func textDidChange(_ textInput: UITextInput?) {
        super.textDidChange(textInput)
        refreshKeyboardView()
    }

    private func makeKeyboardView() -> KeyboardView {
        let latestTranscript = transcriptStore.load()

        return KeyboardView(
            latestTranscript: latestTranscript,
            showsGlobeKey: needsInputModeSwitchKey,
            onGlobeTap: { [weak self] in
                self?.advanceToNextInputMode()
            },
            onCharacterTap: { [weak self] character in
                self?.textDocumentProxy.insertText(character)
            },
            onBackspaceTap: { [weak self] in
                self?.textDocumentProxy.deleteBackward()
            },
            onSpaceTap: { [weak self] in
                self?.textDocumentProxy.insertText(" ")
            },
            onReturnTap: { [weak self] in
                self?.textDocumentProxy.insertText("\n")
            },
            onInsertTap: { [weak self] in
                self?.insertTranscript(latestTranscript)
            }
        )
    }

    private func refreshKeyboardView() {
        hostingController.rootView = makeKeyboardView()
    }

    private func insertTranscript(_ transcript: String) {
        guard !transcript.isEmpty else {
            return
        }

        textDocumentProxy.insertText(transcript)
    }
}
