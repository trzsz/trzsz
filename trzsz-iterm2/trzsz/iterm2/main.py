# MIT License
#
# Copyright (c) 2021 Lonny Wong
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
import argparse
import traceback
import subprocess
from trzsz.libs.utils import *
from trzsz.iterm2.__version__ import __version__

class ProgressCallback(Callback):
    def __init__(self, action):
        self.num = 0
        self.idx = 0
        self.name = ''
        self.size = 0
        self.proc = None
        self.action = action
        self.progress = None

    def on_num(self, num):
        self.num = num
        try:
            title = '%s file(s)' % self.action
            self.proc = subprocess.Popen(['/usr/local/bin/zenity', '--progress', '--title', title, '--text', ''],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except EnvironmentError:
            pass

    def _update_progress(self, step):
        percentage = step * 100 // self.size if self.size else 0
        progress = '%d\n# %sing %s %d%% ( %d / %d ) ...\n' % (percentage, self.action, self.name, percentage, self.idx, self.num)
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
        except IOError:
            send_exit(False, 'Stopped')

    def on_size(self, size):
        self.size = size

    def on_step(self, step):
        if not self.proc:
            return
        try:
            self._update_progress(step)
        except IOError:
            if self.idx < self.num or step < self.size:
                send_exit(False, 'Stopped')

    def on_done(self, name):
        if not self.proc:
            return
        try:
            self.proc.stdin.write(('# %s %s finished.\n' % (self.action, name)).encode('utf8'))
            self.proc.stdin.flush()
        except IOError:
            if self.idx < self.num:
                send_exit(False, 'Stopped')
        if self.idx == self.num:
            self.proc.terminate()

def run_osascript(script):
    try:
        out = subprocess.check_output(['osascript', '-l', 'JavaScript', '-e', script], stderr=subprocess.STDOUT)
        return out.decode('utf8').strip()
    except subprocess.CalledProcessError as e:
        if b"Application can't be found." in e.output:
            sys.stderr.write(e.output + '\n')
            raise Exception('Only supports iTerm2')
        raise

def download_files():
    dest_path = run_osascript('''(function () {
        const app = Application("iTerm2");
        app.includeStandardAdditions = true;
        app.activate();
        try {
            var dest_path = app.chooseFolder({
                withPrompt: "Choose a folder to save file(s)",
            });
            return dest_path.toString();
        } catch (e) {
            return "";
        }
    })();''')

    if not dest_path:
        send_line('CMD', 'CANCELLED')
        return

    check_path(dest_path)

    send_line('CMD', 'CONFIRMED#%s' % __version__)

    local_list = recv_files(dest_path, ProgressCallback('Download'))

    send_exit(True, 'Saved %s to %s' % (', '.join(local_list), dest_path))

def upload_files():
    file_list = run_osascript('''(function () {
        const app = Application("iTerm2");
        app.includeStandardAdditions = true;
        app.activate();
        try {
            var files = app.chooseFile({
                withPrompt: "Choose some files to send",
                multipleSelectionsAllowed: true,
            });
            var file_list = "";
            for (var i = 0; i < files.length; i++) {
                file_list += files[i].toString() + "\\n";
            }
            return file_list;
        } catch (e) {
            return "";
        }
    })();''')

    file_list = [f for f in file_list.split('\n') if f]

    if not file_list:
        send_line('CMD', 'CANCELLED')
        return

    check_files(file_list)

    send_line('CMD', 'CONFIRMED#%s' % __version__)

    remote_list = send_files(file_list, ProgressCallback('Upload'))

    send_exit(True, 'Received %s' % ', '.join(remote_list))

def main():
    try:
        parser = argparse.ArgumentParser(description='iTerm2 coprocess of trzsz which similar to rz/sz ' \
                                                     'but compatible with tmux (control mode).')
        parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) ' + __version__)
        parser.add_argument('mode', help='iTerm2 trigger parameter. (generally should be \\1)')
        args = parser.parse_args()

        if args.mode.startswith(':TRZSZ:TRANSFER:S:'):
            download_files()
        elif args.mode.startswith(':TRZSZ:TRANSFER:R:'):
            upload_files()
        else:
            raise Exception('Unknown transfer mode: %s' % args.mode)
    except Exception as e:
        traceback.print_exc()
        send_exit(False, str(e))

if __name__ == '__main__':
    main()
