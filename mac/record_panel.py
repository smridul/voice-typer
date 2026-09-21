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
CONTEXT_MENU_TOOLTIP = "Right-click for microphone, language and other options"


def clamp_origin(origin, size, visible_frame):
    """Return the origin that keeps a `size` rect fully inside `visible_frame`.

    Pure geometry so it can be unit-tested; all arguments are (x, y) /
    (width, height) / (x, y, width, height) tuples in AppKit coordinates.
    """
    x, y = origin
    width, height = size
    vx, vy, vwidth, vheight = visible_frame
    max_x = vx + vwidth - width
    max_y = vy + vheight - height
    return (min(max(x, vx), max(vx, max_x)), min(max(y, vy), max(vy, max_y)))


def _visible_frame_tuple(screen):
    visible = screen.visibleFrame()
    return (
        visible.origin.x,
        visible.origin.y,
        visible.size.width,
        visible.size.height,
    )


class _PanelDelegate(NSObject):
    """Keeps the panel fully on screen after the user drags it."""

    def windowDidMove_(self, notification):
        keep_panel_on_screen(notification.object())


def keep_panel_on_screen(panel):
    # panel.screen() is the screen the panel mostly overlaps; None when it is
    # entirely off screen, in which case the main screen is used.
    screen = panel.screen() or NSScreen.mainScreen()
    if screen is None:
        return
    frame = panel.frame()
    origin = clamp_origin(
        (frame.origin.x, frame.origin.y),
        (frame.size.width, frame.size.height),
        _visible_frame_tuple(screen),
    )
    if origin != (frame.origin.x, frame.origin.y):
        panel.setFrameOrigin_(origin)


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
        self._delegate = _PanelDelegate.alloc().init()
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
        # A saved position can be off screen (dragged to the edge, display
        # unplugged), which would leave the button unreachable.
        keep_panel_on_screen(panel)
        panel.setDelegate_(self._delegate)
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
        AppHelper.callAfter(self._show_on_main_thread)

    def _show_on_main_thread(self):
        keep_panel_on_screen(self._panel)
        self._panel.orderFrontRegardless()

    def hide(self):
        AppHelper.callAfter(self._panel.orderOut_, None)

    def set_state(self, title, enabled=True):
        AppHelper.callAfter(self._apply_state, title, enabled)

    def set_context_menu(self, nsmenu):
        """Pop `nsmenu` up on right-click / Control-click anywhere on the panel.

        NSView shows its `menu` for right-clicks by itself; setting it on both
        the frosted background and the button covers the whole panel. Popping
        up a menu does not activate the app, so pasting still targets the
        user's frontmost app.
        """
        AppHelper.callAfter(self._apply_context_menu, nsmenu)

    def _apply_context_menu(self, nsmenu):
        self._panel.contentView().setMenu_(nsmenu)
        self._button.setMenu_(nsmenu)
        self._button.setToolTip_(CONTEXT_MENU_TOOLTIP)

    def _apply_state(self, title, enabled):
        self._button.setTitle_(title)
        self._button.setEnabled_(enabled)
