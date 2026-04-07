# VoiceTyper App Bundle Design

## Goal

Package VoiceTyper as a real macOS app bundle so login startup, menu bar behavior, and macOS permissions attach to a stable `VoiceTyper.app` identity instead of a repo-local Python interpreter.

## Current Problem

The current login startup flow launches a wrapper script from the repo, which then executes a Python interpreter from a virtual environment.

That creates two problems:

- macOS privacy permissions for global keyboard monitoring attach to the actual launched process path, which is currently the interpreter rather than a stable app identity
- the runtime depends on repo-local files and a local virtual environment, which is fragile for startup and updates

The observed failure is that VoiceTyper works when started from Terminal but does not receive `Ctrl+Space` when launched in the background by `launchd`.

## Chosen Approach

Build and install a self-contained `VoiceTyper.app` using PyInstaller, store the API key in macOS Keychain, and store non-secret runtime settings in `~/Library/Application Support/VoiceTyper/`.

This makes the launched executable, permission target, and login item all point to the same app identity.

## Why PyInstaller

PyInstaller is preferred in this codebase because:

- it can produce a normal `.app` bundle from the existing Python app
- it embeds the interpreter and Python dependencies inside the bundle
- it requires less app-structure hand assembly than rolling a bundle manually
- it keeps the repo runnable from source for development

`py2app` could also work, but it does not offer a clear advantage for the current app size and structure.

## Product Behavior

### App identity

The packaged app is named `VoiceTyper.app`.

The bundle should have:

- bundle identifier `com.voicetyper.app`
- `LSUIElement = 1` so it behaves as a menu bar app without a Dock icon
- an executable named `VoiceTyper`

### Startup behavior

The installed login item launches the app bundle executable from:

- `/Applications/VoiceTyper.app/Contents/MacOS/VoiceTyper`

The login item no longer launches:

- repo-local shell wrappers
- repo-local `python3`
- virtual environment interpreters

### Runtime config behavior

VoiceTyper should run correctly after the repo is moved or deleted, as long as the installed app remains in `/Applications`.

Runtime files move out of the repo and out of the app bundle.

Non-secret settings are stored at:

- `~/Library/Application Support/VoiceTyper/settings.json`

The API key is stored in macOS Keychain instead of `config.py`.

## Secret Storage Design

### Keychain

Store the Groq API key in the user's login Keychain under a stable service/account pair owned by VoiceTyper.

Use:

- service `com.voicetyper.app`
- account `groq_api_key`

These names must remain stable across app updates so replacing the app bundle does not invalidate the saved key.

### First-run behavior

If the API key is missing:

- the app must still launch
- the menu bar icon must remain visible
- the status item should explain that setup is required
- recording should not start

The app should not crash on missing credentials.

### API key entry paths

Two supported setup paths are required.

#### In-app setup

Add a menu item such as `Set API Key…` that:

- prompts for a key
- validates only enough to reject empty input
- stores the key in Keychain
- updates in-memory client setup immediately
- changes status back to ready when setup succeeds

Add a complementary menu action to replace the key later. Reusing the same `Set API Key…` action for updates is sufficient.

#### CLI setup

Keep a development-friendly terminal path in `setup.sh` that can:

- prompt for the API key without echoing it
- write the same Keychain entry the app uses
- avoid printing the secret back to the terminal

This path exists for development and recovery, not as the primary end-user workflow.

## Settings Storage Design

Keep user preferences such as language settings in Application Support instead of in the repo or in the bundle.

Requirements:

- create `~/Library/Application Support/VoiceTyper/` if it does not exist
- store `settings.json` there
- preserve settings across app upgrades
- allow both source-run and bundled app execution to use the same settings location

This replaces the current settings path that lives next to `main.py`.

## Source Run Compatibility

The repo should remain runnable during development with `python3 main.py`.

Source-run behavior should mirror the bundled app where practical:

- read API key from Keychain
- read and write settings from Application Support
- show the same setup-required behavior when the key is missing

This avoids maintaining separate runtime models for development and production.

## Build And Install Flow

### Build

Add a build script that creates `dist/VoiceTyper.app` from the current repo.

The build must:

- install or use the packaging dependency needed for PyInstaller
- include Python dependencies required by the app
- produce an `.app` bundle with the expected executable and metadata
- set `LSUIElement = 1`

### Install

Add an install script or extend the existing flow so the built app is copied into:

- `/Applications/VoiceTyper.app`

The install flow should replace an existing app bundle in place.

### Login item install

Update login startup installation so the generated LaunchAgent plist targets the installed app bundle executable in `/Applications`.

The login item should fail clearly if the app bundle is not installed yet.

## Update Behavior

Replacing `/Applications/VoiceTyper.app` with a newly built version should preserve:

- the saved Keychain API key
- the saved Application Support settings
- the login item target path

This is the main operational reason for moving secrets and settings out of the repo and out of the bundle.

## Error Handling

- Missing Keychain API key should leave the app running in a setup-required state
- Keychain write failures should show an error notification and keep the previous state unchanged
- Keychain read failures should show an error notification and disable recording
- Missing or invalid settings file should fall back to defaults as today
- Missing installed app during login-item installation should produce a clear install error

Failure should not result in a partially configured recording path.

## Testing Plan

Automated coverage should focus on packaging metadata and new runtime behaviors.

Test cases:

1. bundled or installed path helpers resolve Application Support locations instead of repo-local files
2. missing Keychain secret leaves the app in a setup-required state
3. saving an API key through the app path updates the runtime client state
4. CLI setup writes the same secret target used by the app
5. generated LaunchAgent plist points to `/Applications/VoiceTyper.app/Contents/MacOS/VoiceTyper`
6. generated app metadata includes `LSUIElement`
7. existing language settings continue to round-trip from the new settings location

Manual verification should cover:

1. build `VoiceTyper.app`
2. copy it to `/Applications`
3. launch the app and set the API key from the menu
4. grant `Accessibility`, `Input Monitoring`, and `Microphone` to `VoiceTyper`
5. confirm `Ctrl+Space` works after login-item startup
6. replace the app bundle with a rebuilt version and confirm the key and settings are retained

## Migration

Migration from the current repo-local setup should be minimal.

### Secrets

Existing `config.py` is no longer part of the packaged runtime. The new source of truth is Keychain.

No automatic migration from `config.py` is required for the first pass. The user can set the key once through either supported setup path.

### Settings

If a repo-local `settings.json` exists, migrate it once into Application Support on the first run that uses the new storage path.

If both locations exist, Application Support is the source of truth and the repo-local file is ignored.

## Scope Boundary

This design includes:

- PyInstaller-based `.app` bundling
- Keychain-backed API key storage
- Application Support settings storage
- in-app API key setup
- CLI API key setup
- login-item startup targeting the installed app bundle

This design does not include:

- code signing
- notarization
- automatic updates
- cloud sync of settings or secrets

Those can be added later without changing the runtime storage model.

## Success Criteria

- VoiceTyper can be launched as `/Applications/VoiceTyper.app`
- macOS permissions can be granted to `VoiceTyper.app` rather than Terminal or repo Python
- login startup launches the installed app bundle executable
- the API key persists across app bundle replacements because it lives in Keychain
- language settings persist across app bundle replacements because they live in Application Support
- the repo remains runnable from source for development
