"""Floating Start/Stop Recording button.

Fallback control for when the menu bar icon is unavailable (macOS 26 Control
Center sometimes refuses to host third-party status items). The panel is a
non-activating NSPanel: clicking its button never makes VoiceTyper the
frontmost app, so the transcript is still pasted into whatever app the user
was typing in.
"""

import objc
from AppKit import (
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSFloatingWindowLevel,
    NSObject,
    NSPanel,
    NSScreen,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialPopover,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSMakeRect
from PyObjCTools import AppHelper

PANEL_FRAME_AUTOSAVE_NAME = "VoiceTyperRecordButton"
PANEL_WIDTH = 168.0
PANEL_HEIGHT = 52.0
# Margin around the button that stays free for dragging the panel.
BUTTON_INSET = 8.0
SCREEN_MARGIN = 24.0
CORNER_RADIUS = 12.0


class _RecordButtonTarget(NSObject):
    """Objective-C target for the button; forwards clicks to a Python callable."""

    def initWithCallback_(self, callback):
        self = objc.super(_RecordButtonTarget, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def toggle_(self, _sender):
        self._callback()


class RecordButtonPanel:
    def __init__(self, on_toggle):
        self._target = _RecordButtonTarget.alloc().initWithCallback_(on_toggle)
        self._panel = self._build_panel()
        self._button = self._build_button(self._panel)

    # ── Construction ──────────────────────────────────────────────────────────
    def _build_panel(self):
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            self._default_frame(),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        panel.setHidesOnDeactivate_(False)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setMovableByWindowBackground_(True)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)

        # Frosted, rounded background; the panel itself is transparent.
        content = NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT)
        )
        content.setMaterial_(NSVisualEffectMaterialPopover)
        content.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        content.setState_(NSVisualEffectStateActive)
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(CORNER_RADIUS)
        content.layer().setMasksToBounds_(True)
        panel.setContentView_(content)

        # Restores the last dragged position, if any; otherwise keeps the default.
        panel.setFrameAutosaveName_(PANEL_FRAME_AUTOSAVE_NAME)
        return panel

    def _build_button(self, panel):
        button = NSButton.alloc().initWithFrame_(
            NSMakeRect(
                BUTTON_INSET,
                BUTTON_INSET,
                PANEL_WIDTH - 2 * BUTTON_INSET,
                PANEL_HEIGHT - 2 * BUTTON_INSET,
            )
        )
        button.setBezelStyle_(NSBezelStyleRounded)
        button.setTarget_(self._target)
        button.setAction_("toggle:")
        panel.contentView().addSubview_(button)
        return button

    @staticmethod
    def _default_frame():
        # Bottom-right corner of the main screen, clear of the Dock.
        screen = NSScreen.mainScreen()
        if screen is None:
            return NSMakeRect(SCREEN_MARGIN, SCREEN_MARGIN, PANEL_WIDTH, PANEL_HEIGHT)
        visible = screen.visibleFrame()
        x = visible.origin.x + visible.size.width - PANEL_WIDTH - SCREEN_MARGIN
        y = visible.origin.y + SCREEN_MARGIN
        return NSMakeRect(x, y, PANEL_WIDTH, PANEL_HEIGHT)

    # ── Public API (safe to call from any thread) ─────────────────────────────
    def show(self):
        AppHelper.callAfter(self._panel.orderFrontRegardless)

    def hide(self):
        AppHelper.callAfter(self._panel.orderOut_, None)

    def set_state(self, title, enabled=True):
        AppHelper.callAfter(self._apply_state, title, enabled)

    def _apply_state(self, title, enabled):
        self._button.setTitle_(title)
        self._button.setEnabled_(enabled)
