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

import os
import re
import sys
import enum
import asyncio
import argparse
import tempfile
import threading
import subprocess
import iterm2
from trzsz.libs.utils import *
from trzsz.iterm2.__version__ import __version__
from trzsz.iterm2.text_progress import TextProgressBar
from trzsz.iterm2.zenity_progress import ZenityProgressBar

class ProgressType(enum.Enum):
    text = 'text'
    zenity = 'zenity'

    def __str__(self):
        return self.value

def run_osascript(script):
    try:
        out = subprocess.check_output(['osascript', '-l', 'JavaScript', '-e', script], stderr=subprocess.STDOUT)
        return out.decode('utf8').strip()
    except subprocess.CalledProcessError as e:
        if b"Application can't be found." in e.output:
            sys.stderr.write(e.output + '\n')
            raise TrzszError('Only supports iTerm2', trace=False)
        raise

def choose_download_path(loop, connection):
    if connection and iterm2.capabilities.supports_file_panels(connection):
        panel = iterm2.OpenPanel()
        panel.message = 'Choose a folder to save file(s)'
        panel.options.clear()
        panel.options.append(iterm2.OpenPanel.Options.CAN_CHOOSE_DIRECTORIES)
        panel.options.append(iterm2.OpenPanel.Options.CAN_CREATE_DIRECTORIES)
        panel.options.append(iterm2.OpenPanel.Options.SHOWS_HIDDEN_FILES)
        panel.options.append(iterm2.OpenPanel.Options.TREATS_FILE_PACKAGES_AS_DIRECTORIES)
        future = asyncio.ensure_future(panel.async_run(connection), loop=loop)
        event = threading.Event()
        future.add_done_callback(lambda x: event.set())
        event.wait()
        result = future.result()
        if result and result.files:
            return result.files[0]
        return None
    return run_osascript('''(function () {
        const app = Application("iTerm2");
        app.includeStandardAdditions = true;
        app.activate();
        try {
            var dest_path = app.chooseFolder({
                withPrompt: "Choose a folder to save file(s)",
                invisibles: true,
                showingPackageContents: true,
            });
            return dest_path.toString();
        } catch (e) {
            return "";
        }
    })();''')

def choose_upload_paths(loop, connection, directory):
    if connection and iterm2.capabilities.supports_file_panels(connection):
        panel = iterm2.OpenPanel()
        panel.message = 'Choose some files to send'
        panel.options.clear()
        panel.options.append(iterm2.OpenPanel.Options.CAN_CHOOSE_FILES)
        if directory:
            panel.options.append(iterm2.OpenPanel.Options.CAN_CHOOSE_DIRECTORIES)
        panel.options.append(iterm2.OpenPanel.Options.ALLOWS_MULTIPLE_SELECTION)
        panel.options.append(iterm2.OpenPanel.Options.SHOWS_HIDDEN_FILES)
        panel.options.append(iterm2.OpenPanel.Options.TREATS_FILE_PACKAGES_AS_DIRECTORIES)
        future = asyncio.ensure_future(panel.async_run(connection), loop=loop)
        event = threading.Event()
        future.add_done_callback(lambda x: event.set())
        event.wait()
        result = future.result()
        if result:
            return result.files
        return None
    file_list = run_osascript('''(function () {
        const app = Application("iTerm2");
        app.includeStandardAdditions = true;
        app.activate();
        try {
            var files = app.%s({
                withPrompt: "Choose some files to send",
                invisibles: true,
                showingPackageContents: true,
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
    })();''' % ('chooseFolder' if directory else 'chooseFile'))
    return [f for f in file_list.split('\n') if f]

def download_files(args, loop, connection, session, remote_is_windows):
    dest_path = args.destpath or choose_download_path(loop, connection)

    if not dest_path:
        send_action(False, __version__, remote_is_windows)
        return

    check_path_writable(dest_path)

    reconfigure_stdin()

    send_action(True, __version__, remote_is_windows)
    config = recv_config()

    callback = None
    if not config.get('quiet', False):
        if args.progress == ProgressType.text and loop and session:
            callback = TextProgressBar(loop, session, config.get('tmux_pane_width'))
        else:
            callback = ZenityProgressBar('Download')

    local_list = recv_files(dest_path, callback)

    client_exit('Saved %s to %s' % (', '.join(local_list), dest_path))

def upload_files(args, loop, connection, session, directory, remote_is_windows):
    paths = choose_upload_paths(loop, connection, directory)
    if not paths:
        send_action(False, __version__, remote_is_windows)
        return

    file_list = check_paths_readable(paths, directory)

    reconfigure_stdin()

    send_action(True, __version__, remote_is_windows)
    config = recv_config()

    if config.get('overwrite') is True:
        check_duplicate_names(file_list)

    callback = None
    if not config.get('quiet', False):
        if args.progress == ProgressType.text and loop and session:
            callback = TextProgressBar(loop, session, config.get('tmux_pane_width'))
        else:
            callback = ZenityProgressBar('Upload')

    remote_list = send_files(file_list, callback)

    client_exit('Received %s' % ', '.join(remote_list))

async def keystroke_filter(connection, session):
    all_keys = iterm2.KeystrokePattern()
    all_keys.keycodes = list(iterm2.Keycode)
    filter = iterm2.KeystrokeFilter(connection, [all_keys], session.session_id)
    async with filter as mon:
        while True:
            await asyncio.sleep(1)

async def keystroke_monitor(connection, session):
    async with iterm2.KeystrokeMonitor(connection) as mon:
        while True:
            keystroke = await mon.async_get()
            if keystroke.characters == '\x03':
                app = await iterm2.async_get_app(connection)
                current_session = app.current_window.current_tab.current_session
                if current_session.session_id == session.session_id:
                    stop_transferring()

async def get_running_session(force):
    session_id = os.environ.get('ITERM_SESSION_ID')
    if not session_id:
        if force:
            raise TrzszError('Please upgrade iTerm2', trace=False)
        return None, None
    try:
        connection = await iterm2.Connection.async_create()
        app = await iterm2.async_get_app(connection)
        current_session = app.current_window.current_tab.current_session
        if current_session.session_id in session_id:
            return connection, current_session
        for win in app.windows:
            for tab in win.tabs:
                for session in tab.sessions:
                    if session.session_id in session_id:
                        return connection, session
    except Exception:
        if force:
            raise TrzszError('Please enable iTerm2 Python API', trace=False)
        return None, None
    if force:
        raise TrzszError("Can't find the session in iTerm2", trace=False)
    return None, None

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

def side_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def main():
    try:
        parser = argparse.ArgumentParser(description='iTerm2 coprocess of trzsz which similar to lrzsz ' \
                                                     '( rz / sz ) and compatible with tmux.')
        parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) py ' + __version__)
        parser.add_argument('-p',
                            '--progress',
                            type=ProgressType,
                            choices=list(ProgressType),
                            default=ProgressType.zenity,
                            help='the progress bar type. (default: zenity)')
        parser.add_argument('-d',
                            '--destpath',
                            type=str,
                            default=None,
                            help='the default save destination path. (default: choose each time)')
        parser.add_argument('mode', help='iTerm2 trigger parameter. (generally should be \\1)')
        args = parser.parse_args()

        trigger_regex = r':TRZSZ:TRANSFER:([SRD]):(\d+\.\d+\.\d+)(:\d+)?'
        trigger_match = re.search(trigger_regex, args.mode)
        if not trigger_match:
            raise TrzszError('Please check iTerm2 Trigger configuration', trace=False)
        mode = trigger_match.group(1)
        version = trigger_match.group(2)
        unique_id = trigger_match.group(3)
        remote_is_windows = unique_id == ':1'

        if unique_id_exists(unique_id):
            return

        loop = asyncio.new_event_loop()
        connection, session = loop.run_until_complete(get_running_session(args.progress == ProgressType.text))
        if connection and session:
            thread = threading.Thread(target=side_thread, args=(loop, ), daemon=True)
            thread.start()
            asyncio.run_coroutine_threadsafe(keystroke_filter(connection, session), loop)
            asyncio.run_coroutine_threadsafe(keystroke_monitor(connection, session), loop)

        if mode == 'S':
            download_files(args, loop, connection, session, remote_is_windows)
        elif mode == 'R':
            upload_files(args, loop, connection, session, False, remote_is_windows)
        elif mode == 'D':
            upload_files(args, loop, connection, session, True, remote_is_windows)
        else:
            raise TrzszError('Unknown transfer mode: %s' % mode, trace=False)

    except Exception as e:
        client_error(e)

if __name__ == '__main__':
    main()
