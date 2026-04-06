# Language Mode Design

## Goal

Add explicit language controls to the menubar app so the user can choose:

- the language context they are speaking in
- the language form they want typed at the cursor

The app must support these four combinations:

- English context -> English output
- English context -> Hindi output
- Hindi context -> English output
- Hindi context -> Hindi output

## Current State

The app currently sends recorded audio to Groq Whisper with `language="en"` hard-coded in `main.py`. That forces speech recognition toward English and prevents Hindi-aware handling.

The current flow is:

1. Record audio from the microphone.
2. Send audio for transcription.
3. Take the returned text.
4. Paste it via clipboard at the current cursor.

## Product Behavior

Two persistent settings are added to the menubar app:

- `Context Language`: `English` or `Hindi`
- `Output Language`: `English` or `Hindi`

These settings stay active across recordings and across app relaunches until the user changes them.

### Output rules

- `English context -> English output`
  - Output normal English text.
  - Example: `I need to go tomorrow`
- `English context -> Hindi output`
  - Output Hindi script translated from the spoken English meaning.
  - Example: `मुझे कल जाना है`
- `Hindi context -> English output`
  - Output romanized Hindi in English letters.
  - This is transliteration, not translation to English meaning.
  - Example: `mujhe kal jana hai`
- `Hindi context -> Hindi output`
  - Output Hindi script.
  - Example: `मुझे कल जाना है`

## Recommended Architecture

Use a two-step text pipeline:

1. Transcribe audio using the selected `Context Language`.
2. Convert the transcript to the selected `Output Language` form when needed.

This is preferred over trying to force the speech model to directly emit every final form, because:

- it keeps speech recognition focused on the spoken language
- it cleanly separates recognition from conversion
- it is more reliable for Hindi speech -> romanized Hindi output
- it allows the menu settings to map to explicit logic

## Runtime Flow

On each hotkey recording cycle:

1. Record audio as today.
2. Read the active `Context Language` and `Output Language`.
3. Send audio to transcription with the selected context:
   - `English` context -> `language="en"`
   - `Hindi` context -> `language="hi"`
4. Receive an intermediate transcript.
5. If the intermediate transcript is empty, stop without typing.
6. If output form already matches the transcript form, use it directly.
7. Otherwise, run a text conversion step.
8. Paste the final text at the cursor.

## Conversion Logic

Conversion is based on the pair of settings.

### No conversion needed

- `English context -> English output`
  - Use transcript directly.
- `Hindi context -> Hindi output`
  - Use transcript directly.

### Conversion needed

- `English context -> Hindi output`
  - Convert the English transcript into Hindi script.
  - This is translation into Hindi.
- `Hindi context -> English output`
  - Convert the Hindi transcript into romanized Hindi using English letters only.
  - This is transliteration, not translation to English meaning.

## UI Design

Extend the existing menubar menu to include two option groups:

- `Context Language`
  - `English`
  - `Hindi`
- `Output Language`
  - `English`
  - `Hindi`

Requirements:

- the active option in each group is visibly indicated
- changing a menu item updates in-memory state immediately
- settings are persisted after each change
- the existing status item and quit action remain intact

The hotkey and recording interaction do not change.

## Persistence

Persist both settings locally so they survive relaunches.

Preferred options in this codebase:

- lightweight JSON settings file alongside app config, or
- macOS defaults through a small wrapper if it stays simple

Recommendation:

Use a lightweight local settings file because it is easy to inspect, easy to test, and fits the current single-file app structure.

Persisted fields:

- `context_language`
- `output_language`

Default values:

- `context_language = "en"`
- `output_language = "en"`

These defaults preserve current user expectations for English-first use.

## Error Handling

- If recording yields no frames, reset status and do nothing.
- If transcription fails, show the existing notification and type nothing.
- If conversion fails, show the existing notification and type nothing.
- Always clean up the temporary audio file and reset menu status.

Failure should never result in partially typed output.

## Testing Plan

Manual verification is sufficient for the current scope.

Test cases:

1. English context + English output types English text.
2. English context + Hindi output types Hindi script.
3. Hindi context + English output types romanized Hindi.
4. Hindi context + Hindi output types Hindi script.
5. Changing either menu setting affects the next recording immediately.
6. Relaunching the app preserves both settings.
7. Transcription failure shows an error and types nothing.
8. Conversion failure shows an error and types nothing.

Suggested manual phrases:

- English speech: `I need to go tomorrow`
- Hindi speech: `मुझे कल जाना है`

## Implementation Notes

The existing `main.py` can absorb this feature without a large refactor. The expected code changes are:

- add menu items and selection handlers
- add settings load/save helpers
- replace hard-coded transcription language selection
- add a small conversion function that calls the LLM only when required
- keep clipboard paste behavior unchanged

No change is required to:

- audio capture format
- global hotkey behavior
- paste mechanism

## Open Questions Resolved

- All four context/output combinations are supported.
- `Hindi context -> English output` means romanized Hindi, not English translation.
- `English context -> Hindi output` is allowed and should produce Hindi script.
- The language controls are persistent menubar settings, not per-recording prompts.

## Scope Boundary

This design does not include:

- automatic language detection
- mixed-language sentence handling within one utterance
- user-defined custom transliteration styles
- additional languages beyond English and Hindi

Those can be added later, but they are intentionally out of scope for this change.
