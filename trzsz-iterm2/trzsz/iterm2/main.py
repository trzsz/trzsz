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

import os
import re
import sys
import argparse
import tempfile
import subprocess
from trzsz.libs.utils import *
from trzsz.iterm2.__version__ import __version__

progress_subprocess = None

class ProgressCallback(TrzszCallback):
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
            global progress_subprocess
            progress_subprocess = self.proc
        except EnvironmentError:
            pass

    def _update_progress(self, step):
        percentage = step * 100 // self.size if self.size else 0
        progress = '%d\n# %sing %s %d%% ( %d / %d ) ...\n' \
                   % (percentage, self.action, self.name, percentage, self.idx, self.num)
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
            send_exit(False, 'Stopped')

    def on_size(self, size):
        self.size = size

    def on_step(self, step):
        if not self.proc:
            return
        try:
            self._update_progress(step)
        except EnvironmentError:
            if self.idx < self.num or step < self.size:
                send_exit(False, 'Stopped')

    def on_done(self, name):
        if not self.proc:
            return
        try:
            self.proc.stdin.write(('# %s %s finished.\n' % (self.action, name)).encode('utf8'))
            self.proc.stdin.flush()
        except EnvironmentError:
            if self.idx < self.num:
                send_exit(False, 'Stopped')
        if self.idx == self.num:
            self.proc.terminate()
            global progress_subprocess
            progress_subprocess = None

def run_osascript(script):
    try:
        out = subprocess.check_output(['osascript', '-l', 'JavaScript', '-e', script], stderr=subprocess.STDOUT)
        return out.decode('utf8').strip()
    except subprocess.CalledProcessError as e:
        if b"Application can't be found." in e.output:
            sys.stderr.write(e.output + '\n')
            raise TrzszError('Only supports iTerm2', trace=False)
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
        send_action(False, __version__)
        return

    check_path_writable(dest_path)

    reconfigure_stdin()

    send_action(True, __version__)
    config = recv_config()

    binary = config.get('binary', False)
    timeout = config.get('timeout', 0)
    overwrite = config.get('overwrite', False)
    escape_chars = config.get('escape_chars', [])
    callback = None if config.get('quiet', False) else ProgressCallback('Download')

    local_list = recv_files(dest_path, callback, overwrite, binary, escape_chars, timeout)

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
        send_action(False, __version__)
        return

    check_files_readable(file_list)

    reconfigure_stdin()

    send_action(True, __version__)
    config = recv_config()

    binary = config.get('binary', False)
    bufsize = config.get('bufsize', 10240)
    escape_chars = config.get('escape_chars', [])
    callback = None if config.get('quiet', False) else ProgressCallback('Upload')

    remote_list = send_files(file_list, callback, binary, escape_chars, bufsize)

    send_exit(True, 'Received %s' % ', '.join(remote_list))

def unique_id_exists(unique_id):
    if not unique_id or len(unique_id) < 8:
        return False
    unique_id = unique_id[1:] + '\n'
    unique_id_path = os.path.join(tempfile.gettempdir(), 'trzsz_unique_id')
    try:
        unique_id_list = open(unique_id_path, 'r').readlines()
    except EnvironmentError:
        unique_id_list = []
    if unique_id in unique_id_list:
        return True
    try:
        unique_id_list.append(unique_id)
        open(unique_id_path, 'w').writelines(unique_id_list[-50:])
    except EnvironmentError:
        pass
    return False

def main():
    try:
        parser = argparse.ArgumentParser(description='iTerm2 coprocess of trzsz which similar to lrzsz ' \
                                                     '( rz / sz ) but compatible with tmux.')
        parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) ' + __version__)
        parser.add_argument('mode', help='iTerm2 trigger parameter. (generally should be \\1)')
        args = parser.parse_args()

        trigger_regex = r':TRZSZ:TRANSFER:([SR]):(\d+\.\d+\.\d+)(:\d+)?'
        trigger_match = re.search(trigger_regex, args.mode)
        if not trigger_match:
            raise TrzszError('Please check iTerm2 Trigger configuration', trace=False)
        mode = trigger_match.group(1)
        version = trigger_match.group(2)
        unique_id = trigger_match.group(3)

        if unique_id_exists(unique_id):
            return

        if mode == 'S':
            download_files()
        elif mode == 'R':
            upload_files()
        else:
            raise TrzszError('Unknown transfer mode: %s' % mode, trace=False)

    except Exception as e:
        if progress_subprocess:
            progress_subprocess.terminate()
        fail_exit(e, False)

if __name__ == '__main__':
    main()
