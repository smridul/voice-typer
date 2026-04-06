import XCTest
@testable import VoiceTyperCore

final class LanguageConverterTests: XCTestCase {
    func test_sameLanguage_passthroughReturnsTranscript() throws {
        let converter = LanguageConverter()

        let result = try converter.convert(
            transcript: "I need to go tomorrow",
            contextLanguage: .english,
            outputLanguage: .english
        )

        XCTAssertEqual(result, .final("I need to go tomorrow"))
    }

    func test_hindiSameLanguage_passthroughReturnsTranscript() throws {
        let converter = LanguageConverter()

        let result = try converter.convert(
            transcript: "मुझे कल जाना है",
            contextLanguage: .hindi,
            outputLanguage: .hindi
        )

        XCTAssertEqual(result, .final("मुझे कल जाना है"))
    }

    func test_hindiToEnglish_returnsRomanizedHindi() throws {
        let converter = LanguageConverter()

        let result = try converter.convert(
            transcript: "मुझे कल जाना है",
            contextLanguage: .hindi,
            outputLanguage: .english
        )

        XCTAssertEqual(result, .final("mujhe kal jana hai"))
    }

    func test_englishToHindi_returnsChatRequest() throws {
        let converter = LanguageConverter()

        let result = try converter.convert(
            transcript: "I need to go tomorrow",
            contextLanguage: .english,
            outputLanguage: .hindi
        )

        guard case .requiresModel(let request) = result else {
            return XCTFail("Expected model request")
        }

        XCTAssertEqual(request.model, "llama-3.1-8b-instant")
        XCTAssertTrue(request.messages[0].content.contains("Devanagari"))
        XCTAssertEqual(request.messages[1].content, "I need to go tomorrow")
    }

    func test_emptyTranscript_returnsEmptyFinal() throws {
        let converter = LanguageConverter()

        let result = try converter.convert(
            transcript: "  ",
            contextLanguage: .english,
            outputLanguage: .hindi
        )

        XCTAssertEqual(result, .final(""))
    }

    func test_finalizeHindiConversion_acceptsDevanagari() throws {
        let converter = LanguageConverter()

        let result = try converter.finalizeHindiModelOutput("मुझे कल जाना है")
        XCTAssertEqual(result, "मुझे कल जाना है")
    }

    func test_finalizeHindiConversion_rejectsLatinCharacters() {
        let converter = LanguageConverter()

        XCTAssertThrowsError(
            try converter.finalizeHindiModelOutput("mujhe kal jana hai")
        )
    }

    func test_finalizeHindiConversion_rejectsEmptyString() {
        let converter = LanguageConverter()

        XCTAssertThrowsError(
            try converter.finalizeHindiModelOutput("  ")
        )
    }
}
