import SwiftUI

struct KeyboardView: View {
    let latestTranscript: String
    let showsGlobeKey: Bool
    let onGlobeTap: () -> Void
    let onCharacterTap: (String) -> Void
    let onBackspaceTap: () -> Void
    let onSpaceTap: () -> Void
    let onReturnTap: () -> Void
    let onInsertTap: () -> Void

    @State private var isShiftEnabled = true
    @State private var isNumberModeEnabled = false

    private let topRow = ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"]
    private let middleRow = ["a", "s", "d", "f", "g", "h", "j", "k", "l"]
    private let bottomRow = ["z", "x", "c", "v", "b", "n", "m"]
    private let numberTopRow = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
    private let numberMiddleRow = ["-", "/", ":", ";", "(", ")", "$", "&", "@", "\""]
    private let numberBottomRow = [".", ",", "?", "!", "'"]

    var body: some View {
        VStack(spacing: 8) {
            voiceBar

            if isNumberModeEnabled {
                keyRow(numberTopRow)
                keyRow(numberMiddleRow)
                bottomNumberRow
            } else {
                keyRow(topRow)
                keyRow(middleRow, horizontalPadding: 14)
                bottomLetterRow
            }
            actionRow
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 8)
        .frame(height: 250)
        .background(Color(uiColor: .systemBackground))
    }

    private var voiceBar: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Latest Transcript")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text(previewText)
                    .font(.caption)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Button("Insert", action: onInsertTap)
                .buttonStyle(.borderedProminent)
                .disabled(latestTranscript.isEmpty)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 12))
    }

    private var bottomLetterRow: some View {
        HStack(spacing: 6) {
            modeKeyButton(title: "123") {
                isNumberModeEnabled = true
                isShiftEnabled = false
            }

            systemKeyButton(label: "shift", systemImage: isShiftEnabled ? "shift.fill" : "shift") {
                isShiftEnabled.toggle()
            }

            ForEach(bottomRow, id: \.self) { key in
                letterKeyButton(key)
            }

            systemKeyButton(label: "delete.left", systemImage: "delete.left") {
                onBackspaceTap()
            }
        }
    }

    private var bottomNumberRow: some View {
        HStack(spacing: 6) {
            modeKeyButton(title: "ABC") {
                isNumberModeEnabled = false
                isShiftEnabled = true
            }

            ForEach(numberBottomRow, id: \.self) { key in
                keyboardButton(title: key, fillWidth: true) {
                    onCharacterTap(key)
                }
            }

            systemKeyButton(label: "delete.left", systemImage: "delete.left") {
                onBackspaceTap()
            }
        }
    }

    private var actionRow: some View {
        HStack(spacing: 6) {
            if showsGlobeKey {
                systemKeyButton(label: "globe", systemImage: "globe") {
                    onGlobeTap()
                }
            }

            keyboardButton(title: ",", fillWidth: false) {
                onCharacterTap(",")
            }

            keyboardButton(title: "space", fillWidth: true) {
                onSpaceTap()
            }

            keyboardButton(title: ".", fillWidth: false) {
                onCharacterTap(".")
            }

            keyboardButton(title: "return", fillWidth: false) {
                onReturnTap()
            }
        }
    }

    private func keyRow(_ keys: [String], horizontalPadding: CGFloat = 0) -> some View {
        HStack(spacing: 6) {
            ForEach(keys, id: \.self) { key in
                letterKeyButton(key)
            }
        }
        .padding(.horizontal, horizontalPadding)
    }

    private func letterKeyButton(_ key: String) -> some View {
        keyboardButton(title: displayText(for: key), fillWidth: true) {
            onCharacterTap(displayText(for: key))
            if isShiftEnabled {
                isShiftEnabled = false
            }
        }
    }

    private func systemKeyButton(label: String, systemImage: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.system(size: 16, weight: .semibold))
                .frame(width: 42, height: 42)
                .background(Color(uiColor: .secondarySystemFill), in: RoundedRectangle(cornerRadius: 8))
                .foregroundStyle(.primary)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text(label))
    }

    private func keyboardButton(title: String, fillWidth: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 18, weight: .medium))
                .frame(maxWidth: fillWidth ? .infinity : nil)
                .frame(height: 42)
                .padding(.horizontal, fillWidth ? 0 : 12)
                .background(Color(uiColor: .secondarySystemBackground), in: RoundedRectangle(cornerRadius: 8))
                .foregroundStyle(.primary)
        }
        .buttonStyle(.plain)
    }

    private func modeKeyButton(title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 16, weight: .semibold))
                .frame(width: 50, height: 42)
                .background(Color(uiColor: .secondarySystemFill), in: RoundedRectangle(cornerRadius: 8))
                .foregroundStyle(.primary)
        }
        .buttonStyle(.plain)
    }

    private func displayText(for key: String) -> String {
        isShiftEnabled ? key.uppercased() : key.lowercased()
    }

    private var previewText: String {
        latestTranscript.isEmpty ? "No saved transcript yet." : latestTranscript
    }
}
