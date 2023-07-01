# MIT License
#
# Copyright (c) 2023 Lonny Wong <lonnywong@qq.com>
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

import unittest
from .trzsz.libs import utils


class TestUtilsFunction(unittest.TestCase):

    def test_strip_tmux_status_line(self):
        P = '\x1bP=1s\x1b\\\x1b[?25l\x1b[?12l\x1b[?25h\x1b[5 q\x1bP=2s\x1b\\'  # pylint: disable=invalid-name
        self.assertEqual('', utils.strip_tmux_status_line(''))
        self.assertEqual('ABC123', utils.strip_tmux_status_line('ABC' + '123'))
        self.assertEqual('ABC123', utils.strip_tmux_status_line('ABC' + P + '123'))
        self.assertEqual('ABC123XYZ', utils.strip_tmux_status_line('ABC' + P + '123' + P + 'XYZ'))
        self.assertEqual('ABC123XYZ', utils.strip_tmux_status_line('ABC' + P + '123' + P * 3 + 'XYZ'))
        for i in range(len(P) - 2):
            self.assertEqual('ABC123', utils.strip_tmux_status_line('ABC' + P + '123' + P[:len(P) - i]))


if __name__ == '__main__':
    unittest.main()
