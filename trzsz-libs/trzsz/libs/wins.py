# MIT License
#
# Copyright (c) 2022 Lonny Wong
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import ctypes
from ctypes import wintypes
import msvcrt  # pylint: disable=import-error

# input flags
ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT      = 0x0002
ENABLE_ECHO_INPUT      = 0x0004
ENABLE_WINDOW_INPUT    = 0x0008
ENABLE_MOUSE_INPUT     = 0x0010
ENABLE_INSERT_MODE     = 0x0020
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS  = 0x0080

# output flags
ENABLE_PROCESSED_OUTPUT   = 0x0001
ENABLE_WRAP_AT_EOL_OUTPUT = 0x0002
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004  # VT100 (Win 10)

def check_zero(result, _func, args):
    if not result:
        err = ctypes.get_last_error()
        if err:
            raise ctypes.WinError(err)
    return args

if not hasattr(wintypes, 'LPDWORD'):  # PY2
    wintypes.LPDWORD = ctypes.POINTER(wintypes.DWORD)

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.GetConsoleMode.errcheck = check_zero
kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.LPDWORD)
kernel32.SetConsoleMode.errcheck = check_zero
kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)

def get_console_mode():
    with open(r'\\.\CONIN$', 'r') as con:
        mode = wintypes.DWORD(0)
        hCon = msvcrt.get_osfhandle(con.fileno())
        kernel32.GetConsoleMode(hCon, ctypes.byref(mode))
        return mode.value

def set_console_mode(mode):
    with open(r'\\.\CONIN$', 'r') as con:
        hCon = msvcrt.get_osfhandle(con.fileno())
        kernel32.SetConsoleMode(hCon, mode)

stdin_old_mode = None

def set_stdin_raw():
    global stdin_old_mode
    stdin_old_mode = get_console_mode()
    raw_mode = stdin_old_mode & (~(ENABLE_ECHO_INPUT | ENABLE_PROCESSED_INPUT | ENABLE_LINE_INPUT))
    set_console_mode(raw_mode)

def reset_stdin_tty():
    global stdin_old_mode
    if stdin_old_mode:
        set_console_mode(stdin_old_mode)
        stdin_old_mode = None
