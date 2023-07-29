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

import subprocess
from trzsz.libs import utils


class ZenityProgressBar(utils.TrzszCallback):

    def __init__(self, action):
        self.num = 0
        self.idx = 0
        self.name = ''
        self.size = 0
        self.proc = None
        self.action = action
        self.progress = None

    def __del__(self):
        if self.proc:
            self.proc.terminate()
            self.proc = None

    def on_num(self, num):
        self.num = num
        try:
            title = f'{self.action} file(s)'
            # pylint: disable-next=consider-using-with
            self.proc = subprocess.Popen(['/usr/local/bin/zenity', '--progress', '--title', title, '--text', ''],
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
        except EnvironmentError:
            pass

    def _update_progress(self, step):
        percentage = step * 100 // self.size if self.size else 0
        progress = f'{percentage}\n# {self.action} ( {self.idx} / {self.num} ) {percentage}% {self.name}\n'
        if progress == self.progress:
            return
        self.progress = progress
        self.proc.stdin.write(progress.encode('utf8'))
        self.proc.stdin.flush()

    def on_name(self, name):
        self.idx += 1
        self.size = 0
        self.name = name
        if not self.proc:
            return
        try:
            self._update_progress(0)
        except EnvironmentError:
            utils.stop_transferring()

    def on_size(self, size):
        self.size = size

    def on_step(self, step):
        if not self.proc:
            return
        try:
            self._update_progress(step)
        except EnvironmentError:
            if self.idx < self.num or step < self.size:
                utils.stop_transferring()

    def on_done(self):
        if not self.proc:
            return
        try:
            self._update_progress(self.size)
        except EnvironmentError:
            if self.idx < self.num:
                utils.stop_transferring()
        if self.idx == self.num:
            self.proc.terminate()
            self.proc = None
