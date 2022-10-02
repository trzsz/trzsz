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

import sys
import atexit
import struct
from ctypes import wintypes, windll, create_string_buffer, byref

# standard device
STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12

# input flags
ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
ENABLE_WINDOW_INPUT = 0x0008
ENABLE_MOUSE_INPUT = 0x0010
ENABLE_INSERT_MODE = 0x0020
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080
ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

# output flags
ENABLE_PROCESSED_OUTPUT = 0x0001
ENABLE_WRAP_AT_EOL_OUTPUT = 0x0002
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
DISABLE_NEWLINE_AUTO_RETURN = 0x0008
ENABLE_LVB_GRID_WORLDWIDE = 0x0010

def get_console_mode(handle):
    mode = wintypes.DWORD(0)
    h = windll.kernel32.GetStdHandle(handle)
    windll.kernel32.GetConsoleMode(h, byref(mode))
    return mode.value

def set_console_mode(handle, mode):
    h = windll.kernel32.GetStdHandle(handle)
    windll.kernel32.SetConsoleMode(h, mode)

def get_console_size():
    csbi = create_string_buffer(22)
    h = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    if windll.kernel32.GetConsoleScreenBufferInfo(h, csbi):
        (bufx, bufy, curx, cury, wattr, left, top, right, bottom, maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
        return right - left + 1, bottom - top + 1
    return 0, 0

stdin_old_mode = None
stdout_old_mode = None

def set_stdin_raw():
    global stdin_old_mode
    stdin_old_mode = get_console_mode(STD_INPUT_HANDLE)
    raw_mode = stdin_old_mode & (~(ENABLE_ECHO_INPUT | ENABLE_PROCESSED_INPUT | ENABLE_LINE_INPUT))
    set_console_mode(STD_INPUT_HANDLE, raw_mode)

def reset_stdin_tty():
    global stdin_old_mode
    if stdin_old_mode:
        set_console_mode(STD_INPUT_HANDLE, stdin_old_mode)
        stdin_old_mode = None

def reset_virtual_terminal():
    global stdout_old_mode
    if stdout_old_mode:
        set_console_mode(STD_OUTPUT_HANDLE, stdout_old_mode)
        stdout_old_mode = None

def enable_virtual_terminal():
    global stdout_old_mode
    stdout_old_mode = get_console_mode(STD_OUTPUT_HANDLE)
    atexit.register(reset_virtual_terminal)
    new_mode = stdout_old_mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING | DISABLE_NEWLINE_AUTO_RETURN
    set_console_mode(STD_OUTPUT_HANDLE, new_mode)

def setup_console_output():
    sys.stdout.write('\x1b[?1049h\x1b[H\x1b[2J')
    logo = [
        "ooooooooooooo      ooooooooo.         oooooooooooo       .oooooo..o       oooooooooooo",
        "8'   888   '8      `888   `Y88.      d'''''''d888'      d8P'    `Y8      d'''''''d888'",
        "     888            888   .d88'            .888P        Y88bo.                 .888P  ",
        "     888            888ooo88P'            d888'          `'Y8888o.            d888'   ",
        "     888            888`88b.            .888P                `'Y88b         .888P     ",
        "     888            888  `88b.         d888'    .P      oo     .d8P        d888'    .P",
        "    o888o          o888o  o888o      .888d888d88P       d888d88P'        .888d888d88P ",
    ]
    (width, height) = get_console_size()
    if width <= len(logo[0]) or height <= len(logo) + 2:
        return
    pad = (width - len(logo[0])) // 2
    for s in logo:
        sys.stdout.write(' ' * pad + s + '\r\n')
