import Foundation

public enum HindiRomanizer {
    private static let vowels: [UInt32: String] = [
        0x0905: "a",  // अ
        0x0906: "a",  // आ
        0x0907: "i",  // इ
        0x0908: "i",  // ई
        0x0909: "u",  // उ
        0x090A: "u",  // ऊ
        0x090F: "e",  // ए
        0x0910: "ai", // ऐ
        0x0913: "o",  // ओ
        0x0914: "au", // औ
        0x090B: "ri", // ऋ
    ]

    private static let matras: [UInt32: String] = [
        0x093E: "a",  // ा
        0x093F: "i",  // ि
        0x0940: "i",  // ी
        0x0941: "u",  // ु
        0x0942: "u",  // ू
        0x0947: "e",  // े
        0x0948: "ai", // ै
        0x094B: "o",  // ो
        0x094C: "au", // ौ
        0x0943: "ri", // ृ
    ]

    private static let consonants: [UInt32: String] = [
        0x0915: "k",   // क
        0x0916: "kh",  // ख
        0x0917: "g",   // ग
        0x0918: "gh",  // घ
        0x0919: "ng",  // ङ
        0x091A: "ch",  // च
        0x091B: "chh", // छ
        0x091C: "j",   // ज
        0x091D: "jh",  // झ
        0x091E: "ny",  // ञ
        0x091F: "t",   // ट
        0x0920: "th",  // ठ
        0x0921: "d",   // ड
        0x0922: "dh",  // ढ
        0x0923: "n",   // ण
        0x0924: "t",   // त
        0x0925: "th",  // थ
        0x0926: "d",   // द
        0x0927: "dh",  // ध
        0x0928: "n",   // न
        0x092A: "p",   // प
        0x092B: "ph",  // फ
        0x092C: "b",   // ब
        0x092D: "bh",  // भ
        0x092E: "m",   // म
        0x092F: "y",   // य
        0x0930: "r",   // र
        0x0932: "l",   // ल
        0x0935: "v",   // व
        0x0936: "sh",  // श
        0x0937: "sh",  // ष
        0x0938: "s",   // स
        0x0939: "h",   // ह
    ]

    // Consonants with nukta — looked up as (base consonant value) when followed by nukta
    private static let nuktaConsonants: [UInt32: String] = [
        0x0921: "r",   // ड + ़ = ड़
        0x0922: "rh",  // ढ + ़ = ढ़
        0x0915: "q",   // क + ़ = क़
        0x0916: "kh",  // ख + ़ = ख़
        0x0917: "gh",  // ग + ़ = ग़
        0x091C: "z",   // ज + ़ = ज़
        0x092B: "f",   // फ + ़ = फ़
    ]

    private static let marks: [UInt32: String] = [
        0x0902: "n",  // ं (anusvara)
        0x0901: "n",  // ँ (chandrabindu)
        0x0903: "h",  // ः (visarga)
    ]

    private static let digits: [UInt32: String] = [
        0x0966: "0", 0x0967: "1", 0x0968: "2", 0x0969: "3", 0x096A: "4",
        0x096B: "5", 0x096C: "6", 0x096D: "7", 0x096E: "8", 0x096F: "9",
    ]

    private static let virama: UInt32 = 0x094D  // ्
    private static let nukta: UInt32 = 0x093C    // ़

    public static func romanize(_ text: String) -> String {
        var pieces: [String] = []
        var pendingConsonant: String?
        let scalars = Array(text.unicodeScalars)
        var i = 0

        func flushPending(addSchwa: Bool) {
            guard let consonant = pendingConsonant else { return }
            pieces.append(consonant + (addSchwa ? "a" : ""))
            pendingConsonant = nil
        }

        while i < scalars.count {
            let value = scalars[i].value

            // Check for nukta following a consonant
            if i + 1 < scalars.count && scalars[i + 1].value == nukta {
                if let latin = nuktaConsonants[value] {
                    flushPending(addSchwa: true)
                    pendingConsonant = latin
                    i += 2
                    continue
                }
            }

            // Consonant
            if let latin = consonants[value] {
                flushPending(addSchwa: true)
                pendingConsonant = latin
                i += 1
                continue
            }

            // Matra (vowel sign)
            if let latin = matras[value] {
                if pendingConsonant != nil {
                    pieces.append(pendingConsonant! + latin)
                    pendingConsonant = nil
                } else {
                    pieces.append(latin)
                }
                i += 1
                continue
            }

            // Virama (halant) — suppress the schwa
            if value == virama {
                flushPending(addSchwa: false)
                i += 1
                continue
            }

            // Standalone vowel
            if let latin = vowels[value] {
                flushPending(addSchwa: true)
                pieces.append(latin)
                i += 1
                continue
            }

            // Nasal/visarga marks
            if let latin = marks[value] {
                flushPending(addSchwa: true)
                pieces.append(latin)
                i += 1
                continue
            }

            // Devanagari digits
            if let latin = digits[value] {
                flushPending(addSchwa: false)
                pieces.append(latin)
                i += 1
                continue
            }

            // Anything else (space, punctuation, Latin chars)
            flushPending(addSchwa: false)
            pieces.append(String(scalars[i]))
            i += 1
        }

        flushPending(addSchwa: false)
        return pieces.joined()
    }
}
