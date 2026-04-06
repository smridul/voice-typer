import SwiftUI

struct SetupView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("VoiceTyper Setup")
                .font(.largeTitle.bold())

            Text("Enable the keyboard and Full Access, then use the main app for recording. After transcription finishes, return to the keyboard and tap Insert Last.")
                .font(.body)

            VStack(alignment: .leading, spacing: 12) {
                ForEach(Array(SetupInstructions.defaultSteps.enumerated()), id: \.offset) { _, step in
                    Text(step)
                        .font(.body)
                }
            }

            Spacer()
        }
        .padding()
    }
}
