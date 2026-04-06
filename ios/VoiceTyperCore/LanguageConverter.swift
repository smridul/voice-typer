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

        return .requiresModel(
            ConversionRequest(
                model: textModel,
                messages: [
                    ChatMessage(
                        role: "system",
                        content: "Translate the text into natural Hindi written in Devanagari script. Preserve the meaning, make the result sound natural, and respond only in Devanagari script."
                    ),
                    ChatMessage(role: "user", content: trimmed),
                ]
            )
        )
    }

    public func finalizeHindiModelOutput(_ text: String) throws -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw ConverterError.emptyOutput
        }
        guard containsDevanagari(trimmed) else {
            throw ConverterError.missingDevanagari
        }
        guard !containsLatin(trimmed) else {
            throw ConverterError.containsLatin
        }
        return trimmed
    }

    private func containsDevanagari(_ text: String) -> Bool {
        text.unicodeScalars.contains { 0x0900...0x097F ~= $0.value }
    }

    private func containsLatin(_ text: String) -> Bool {
        text.unicodeScalars.contains {
            (0x0041...0x005A ~= $0.value) || (0x0061...0x007A ~= $0.value)
        }
    }
}

public enum ConverterError: Error {
    case emptyOutput
    case missingDevanagari
    case containsLatin
}
