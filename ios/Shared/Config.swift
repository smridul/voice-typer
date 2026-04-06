import Foundation

enum Config {
    static let groqAPIKey = Bundle.main.object(forInfoDictionaryKey: "GROQ_API_KEY") as? String ?? ""
    static let whisperHost = "https://api.groq.com/openai/v1/audio/transcriptions"
    static let chatHost = "https://api.groq.com/openai/v1/chat/completions"
    static let whisperModel = "whisper-large-v3"
    static let textModel = "llama-3.1-8b-instant"
    static let appGroupIdentifier = "group.com.mridul.voice-typer"
}
