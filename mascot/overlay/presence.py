"""Whether anyone can see her: the displays on and the desktop unlocked.

With the screen dark (the displays turned off after a while, every one of
them) or the PC locked, she rests: the overlay draws nothing, as when
hidden, but keeps her art, so she is back the moment the screen is; her
call to the pointer waits too (magic.py). It never keeps the PC awake: she
asks Windows for nothing, she only listens.

The displays' state comes from Windows itself (`PowerSettingRegisterNotification`
on GUID_CONSOLE_DISPLAY_STATE, a callback on a thread of the system's: no
window needed), sent at once and at each change. Locked is the desktop
taking input not being ours (`OpenInputDesktop` fails while the lock screen
is up), asked at most every LOCK_CHECK_S.
"""

import ctypes
import ctypes.wintypes as wt
import time

# GUID_CONSOLE_DISPLAY_STATE: 0 off, 1 on, 2 dimmed (still seen).
DISPLAY_STATE = (0x6FE69556, 0x704A, 0x47A0, (0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47))
DISPLAY_OFF = 0
DEVICE_NOTIFY_CALLBACK = 2
PBT_POWERSETTINGCHANGE = 0x8013
DESKTOP_SWITCHDESKTOP = 0x0100
LOCK_CHECK_S = 1.0


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


def guid(parts):
    a, b, c, d = parts
    return GUID(a, b, c, (ctypes.c_ubyte * 8)(*d))


class SETTING(ctypes.Structure):
    """POWERBROADCAST_SETTING with its one DWORD of data."""
    _fields_ = [("PowerSetting", GUID), ("DataLength", wt.DWORD), ("Data", wt.DWORD)]


CALLBACK = ctypes.WINFUNCTYPE(wt.ULONG, ctypes.c_void_p, wt.ULONG, ctypes.c_void_p)


class SUBSCRIBE(ctypes.Structure):
    _fields_ = [("Callback", CALLBACK), ("Context", ctypes.c_void_p)]


def is_locked():
    """Whether the lock screen (or another desktop not ours, as the UAC
    prompt's) takes input now."""
    try:
        user32 = ctypes.windll.user32
        user32.OpenInputDesktop.restype = wt.HANDLE
        desk = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
        if not desk:
            return True
        user32.CloseDesktop(wt.HANDLE(desk))
        return False
    except (AttributeError, OSError):
        return False


class Presence:
    """Follows the displays' state from the start; `dark()` asks."""

    def __init__(self, register=True):
        self.display_off = False
        self.locked = False
        self.checked = None  # when locked was last asked (monotonic s)
        self._callback = CALLBACK(self._changed)  # kept: Windows calls it as long as we live
        self._params = SUBSCRIBE(self._callback, None)
        self._guid = guid(DISPLAY_STATE)
        self._handle = ctypes.c_void_p()
        if register:
            try:
                ctypes.windll.powrprof.PowerSettingRegisterNotification(
                    ctypes.byref(self._guid), DEVICE_NOTIFY_CALLBACK, ctypes.byref(self._params),
                    ctypes.byref(self._handle))
            except (AttributeError, OSError):
                pass  # never told: taken as on

    def _changed(self, _context, kind, setting):
        if kind == PBT_POWERSETTINGCHANGE and setting:
            got = SETTING.from_address(setting)
            if bytes(got.PowerSetting) == bytes(self._guid) and got.DataLength >= 1:
                self.display_off = (got.Data & 0xFF) == DISPLAY_OFF
        return 0

    def dark(self, now=None):
        """Whether nobody can see her now: every display off, or locked."""
        now = time.monotonic() if now is None else now
        if self.checked is None or now - self.checked >= LOCK_CHECK_S:
            self.checked, self.locked = now, is_locked()
        return self.display_off or self.locked
