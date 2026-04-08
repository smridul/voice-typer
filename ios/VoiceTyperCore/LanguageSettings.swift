import Foundation

public enum LanguageCode: String, CaseIterable, Codable {
    case english = "en"
    case hindi = "hi"
    case spanish = "es"
    case chinese = "zh"

    public var label: String {
        switch self {
        case .english: return "English"
        case .hindi: return "Hindi"
        case .spanish: return "Spanish"
        case .chinese: return "Chinese"
        }
    }
}

public struct LanguageSettings: Equatable, Codable {
    public var contextLanguage: LanguageCode
    public var outputLanguage: LanguageCode

    public init(contextLanguage: LanguageCode, outputLanguage: LanguageCode) {
        self.contextLanguage = contextLanguage
        self.outputLanguage = outputLanguage
    }

    public static let `default` = LanguageSettings(
        contextLanguage: .english,
        outputLanguage: .english
    )
}
