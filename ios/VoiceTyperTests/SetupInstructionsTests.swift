import XCTest
@testable import VoiceTyper

final class SetupInstructionsTests: XCTestCase {
    func test_defaultSteps_matchTheKeyboardEnableFlow() {
        XCTAssertEqual(
            SetupInstructions.defaultSteps,
            [
                "Open Settings > General > Keyboard > Keyboards > Add New Keyboard > select \"VoiceTyper\"",
                "Tap VoiceTyper > enable \"Allow Full Access\" (required for network access and shared settings)"
            ]
        )
    }
}
