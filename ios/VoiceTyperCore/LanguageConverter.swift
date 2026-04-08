import Foundation

public struct ChatMessage: Equatable {
    public let role: String
    public let content: String

    public init(role: String, content: String) {
        self.role = role
        self.content = content
    }
}

public struct ConversionRequest: Equatable {
    public let model: String
    public let messages: [ChatMessage]

    public init(model: String, messages: [ChatMessage]) {
        self.model = model
        self.messages = messages
    }
}

public enum ConversionResult: Equatable {
    case final(String)
    case requiresModel(ConversionRequest)
}

public struct LanguageConverter {
    private let textModel: String

    public init(textModel: String = "llama-3.1-8b-instant") {
        self.textModel = textModel
    }

    private static let translationPrompts: [String: String] = [
        "en→hi": "Translate the text into natural Hindi written in Devanagari script. Preserve the meaning, make the result sound natural, and respond only in Devanagari script.",
        "en→es": "Translate the text into natural Spanish. Preserve the meaning and make the result sound natural.",
        "en→zh": "Translate the text into natural Simplified Chinese. Preserve the meaning and make the result sound natural. Respond only in Chinese characters.",
        "es→en": "Translate the text from Spanish into natural English. Preserve the meaning and make the result sound natural.",
        "es→hi": "Translate the text from Spanish into natural Hindi written in Devanagari script. Preserve the meaning, make the result sound natural, and respond only in Devanagari script.",
        "es→zh": "Translate the text from Spanish into natural Simplified Chinese. Preserve the meaning and make the result sound natural. Respond only in Chinese characters.",
        "zh→en": "Translate the text from Chinese into natural English. Preserve the meaning and make the result sound natural.",
        "zh→hi": "Translate the text from Chinese into natural Hindi written in Devanagari script. Preserve the meaning, make the result sound natural, and respond only in Devanagari script.",
        "zh→es": "Translate the text from Chinese into natural Spanish. Preserve the meaning and make the result sound natural.",
        "hi→es": "Translate the text from Hindi into natural Spanish. Preserve the meaning and make the result sound natural.",
        "hi→zh": "Translate the text from Hindi into natural Simplified Chinese. Preserve the meaning and make the result sound natural. Respond only in Chinese characters.",
    ]

    public func convert(
        transcript: String,
        contextLanguage: LanguageCode,
        outputLanguage: LanguageCode
    ) throws -> ConversionResult {
        let trimmed = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return .final("") }

        if contextLanguage == outputLanguage {
            return .final(trimmed)
        }

        if contextLanguage == .hindi && outputLanguage == .english {
            return .final(HindiRomanizer.romanize(trimmed))
        }

        let key = "\(contextLanguage.rawValue)→\(outputLanguage.rawValue)"
        guard let prompt = Self.translationPrompts[key] else {
            return .final(trimmed)
        }

        return .requiresModel(
            ConversionRequest(
                model: textModel,
                messages: [
                    ChatMessage(role: "system", content: prompt),
                    ChatMessage(role: "user", content: trimmed),
                ]
            )
        )
    }

    public func finalizeModelOutput(_ text: String, outputLanguage: LanguageCode) throws -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw ConverterError.emptyOutput
        }

        switch outputLanguage {
        case .hindi:
            guard containsDevanagari(trimmed) else {
                throw ConverterError.missingExpectedScript
            }
            guard !containsLatin(trimmed) else {
                throw ConverterError.containsLatin
            }
        case .chinese:
            guard containsCJK(trimmed) else {
                throw ConverterError.missingExpectedScript
            }
            guard !containsLatin(trimmed) else {
                throw ConverterError.containsLatin
            }
        case .english, .spanish:
            break
        }

        return trimmed
    }

    @available(*, deprecated, renamed: "finalizeModelOutput(_:outputLanguage:)")
    public func finalizeHindiModelOutput(_ text: String) throws -> String {
        try finalizeModelOutput(text, outputLanguage: .hindi)
    }

    private func containsDevanagari(_ text: String) -> Bool {
        text.unicodeScalars.contains { 0x0900...0x097F ~= $0.value }
    }

    private func containsCJK(_ text: String) -> Bool {
        text.unicodeScalars.contains {
            (0x4E00...0x9FFF ~= $0.value) || (0x3400...0x4DBF ~= $0.value)
        }
    }

    private func containsLatin(_ text: String) -> Bool {
        text.unicodeScalars.contains {
            (0x0041...0x005A ~= $0.value) || (0x0061...0x007A ~= $0.value)
        }
    }
}

public enum ConverterError: Error {
    case emptyOutput
    case missingExpectedScript
    case containsLatin

    @available(*, deprecated, renamed: "missingExpectedScript")
    public static let missingDevanagari = missingExpectedScript
}
