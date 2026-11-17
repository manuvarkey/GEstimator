"""Font family names available to the desktop application."""

import ctypes
import subprocess
import sys


def _windows_families():
    from ctypes import wintypes

    class LogFont(ctypes.Structure):
        _fields_ = [(name, wintypes.LONG) for name in (
            "height", "width", "escapement", "orientation", "weight",
        )] + [(name, wintypes.BYTE) for name in (
            "italic", "underline", "strikeout", "charset", "out_precision",
            "clip_precision", "quality", "pitch_and_family",
        )] + [("family", wintypes.WCHAR * 32)]

    families = set()
    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.POINTER(LogFont), ctypes.c_void_p,
        wintypes.DWORD, wintypes.LPARAM,
    )

    @callback_type
    def collect(font, _metrics, _font_type, _context):
        families.add(font.contents.family)
        return 1

    gdi = ctypes.WinDLL("gdi32")
    user = ctypes.WinDLL("user32")
    user.GetDC.argtypes = [wintypes.HWND]
    user.GetDC.restype = wintypes.HDC
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi.EnumFontFamiliesExW.argtypes = [
        wintypes.HDC, ctypes.POINTER(LogFont), callback_type,
        wintypes.LPARAM, wintypes.DWORD,
    ]
    context = user.GetDC(None)
    if context:
        try:
            font = LogFont(charset=1)  # DEFAULT_CHARSET includes all writing systems.
            gdi.EnumFontFamiliesExW(context, ctypes.byref(font), collect, 0, 0)
        finally:
            user.ReleaseDC(None, context)
    return families


def _mac_families():
    coretext = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    foundation = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    pointer, index = ctypes.c_void_p, ctypes.c_long
    coretext.CTFontManagerCopyAvailableFontFamilyNames.restype = pointer
    foundation.CFArrayGetCount.argtypes = [pointer]
    foundation.CFArrayGetCount.restype = index
    foundation.CFArrayGetValueAtIndex.argtypes = [pointer, index]
    foundation.CFArrayGetValueAtIndex.restype = pointer
    foundation.CFStringGetCString.argtypes = [pointer, ctypes.c_char_p, index, ctypes.c_uint32]
    foundation.CFStringGetCString.restype = ctypes.c_bool
    foundation.CFRelease.argtypes = [pointer]
    foundation.CFRelease.restype = None
    families = []
    array = coretext.CTFontManagerCopyAvailableFontFamilyNames()
    if array:
        try:
            buffer = ctypes.create_string_buffer(1024)
            for i in range(foundation.CFArrayGetCount(array)):
                name = foundation.CFArrayGetValueAtIndex(array, i)
                if foundation.CFStringGetCString(name, buffer, len(buffer), 0x08000100):  # UTF-8
                    families.append(buffer.value.decode("utf-8"))
        finally:
            foundation.CFRelease(array)
    return families


def installed_families():
    if sys.platform == "win32":
        families = _windows_families()
    elif sys.platform == "darwin":
        families = _mac_families()
    else:
        result = subprocess.run(
            ["fc-list", "--format=%{family}\n"], capture_output=True,
            encoding="utf-8", check=True, timeout=5,
        )
        families = result.stdout.replace(",", "\n").splitlines()
    unique = {}
    for family in families:
        name = family.strip()
        if name and not name.startswith("@"):
            unique.setdefault(name.casefold(), name)
    return [unique[key] for key in sorted(unique)]
