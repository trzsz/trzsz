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

import os
import re
import sys
import enum
import select
import asyncio
import argparse
import tempfile
import threading
import contextlib
import subprocess
import iterm2
from trzsz.libs import utils
from trzsz.libs import transfer
from trzsz.iterm2.__version__ import __version__
from trzsz.iterm2.text_progress import TextProgressBar
from trzsz.iterm2.zenity_progress import ZenityProgressBar


class ProgressType(enum.Enum):
    TEXT = 'text'
    ZENITY = 'zenity'

    def __str__(self):
        return self.value


def run_osascript(script):
    try:
        out = subprocess.check_output(['osascript', '-l', 'JavaScript', '-e', script], stderr=subprocess.STDOUT)
        return out.decode('utf8').strip()
    except subprocess.CalledProcessError as ex:
        if b"Application can't be found." in ex.output:
            sys.stderr.write(ex.output + '\n')
            raise utils.TrzszError('Only supports iTerm2', trace=False)
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
    # pylint: disable-next=consider-using-f-string
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
        transfer.send_action(False, __version__, remote_is_windows)
        return

    utils.check_path_writable(dest_path)

    utils.reconfigure_stdin()

    transfer.send_action(True, __version__, remote_is_windows)
    config = transfer.recv_config()

    with contextlib.ExitStack() as stack:
        progress_bar = None
        if not config.quiet:
            if args.progress == ProgressType.TEXT and loop and session:
                progress_bar = TextProgressBar(loop, session, config.tmux_pane_width)
                progress_bar.hide_cursor()
                stack.callback(progress_bar.show_cursor)
            else:
                progress_bar = ZenityProgressBar('Downloading')

        local_list = transfer.recv_files(dest_path, progress_bar)

    transfer.client_exit(utils.format_saved_files(local_list, dest_path))


class GlobalVariables:

    def __init__(self):
        self.upload_file_list = None


GLOBAL = GlobalVariables()


def upload_files(args, loop, connection, session, directory, remote_is_windows):  # pylint: disable=too-many-arguments
    if GLOBAL.upload_file_list:
        file_list = GLOBAL.upload_file_list
        GLOBAL.upload_file_list = None
    else:
        paths = choose_upload_paths(loop, connection, directory)
        if not paths:
            transfer.send_action(False, __version__, remote_is_windows)
            return
        file_list = utils.check_paths_readable(paths, directory)

    utils.reconfigure_stdin()

    transfer.send_action(True, __version__, remote_is_windows)
    config = transfer.recv_config()

    if config.overwrite is True:
        utils.check_duplicate_names(file_list)

    with contextlib.ExitStack() as stack:
        progress_bar = None
        if not config.quiet:
            if args.progress == ProgressType.TEXT and loop and session:
                progress_bar = TextProgressBar(loop, session, config.tmux_pane_width)
                progress_bar.hide_cursor()
                stack.callback(progress_bar.show_cursor)
            else:
                progress_bar = ZenityProgressBar('Uploading')

        remote_list = transfer.send_files(file_list, progress_bar)

    transfer.client_exit(utils.format_saved_files(remote_list, ''))


async def keystroke_filter(connection, session):
    all_keys = iterm2.KeystrokePattern()
    all_keys.keycodes = list(iterm2.Keycode)
    async with iterm2.KeystrokeFilter(connection, [all_keys], session.session_id):
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
                    utils.stop_transferring()


async def get_running_session(force):
    session_id = os.environ.get('ITERM_SESSION_ID')
    if not session_id:
        if force:
            raise utils.TrzszError('Please upgrade iTerm2', trace=False)
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
            raise utils.TrzszError('Please enable iTerm2 Python API', trace=False)
        return None, None
    if force:
        raise utils.TrzszError("Can't find the session in iTerm2", trace=False)
    return None, None


def unique_id_exists(unique_id):
    if not unique_id or len(unique_id) < 8:
        return False
    if len(unique_id) == 14 and unique_id.endswith('00'):
        return False
    unique_id = unique_id[1:] + '\n'
    unique_id_path = os.path.join(tempfile.gettempdir(), 'trzsz_unique_id')
    try:
        with open(unique_id_path, 'r', encoding='utf8') as file:
            unique_id_list = file.readlines()
    except EnvironmentError:
        unique_id_list = []
    if unique_id in unique_id_list:
        return True
    try:
        unique_id_list.append(unique_id)
        with open(unique_id_path, 'w', encoding='utf8') as file:
            file.writelines(unique_id_list[-50:])
    except EnvironmentError:
        pass
    return False


def side_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def read_server_output(timeout):
    output = []
    while True:
        rlist, _wlist, _xlist = select.select([sys.stdin], [], [], timeout)
        if not rlist:
            break
        out = os.read(sys.stdin.fileno(), 32 * 1024)
        if not out:
            break
        output.append(out)
    return b''.join(output)


TRZSZ_TRIGGER_REGEX = r':TRZSZ:TRANSFER:([SRD]):(\d+\.\d+\.\d+)(:\d+)?'


def drag_files_to_upload(file_paths, loop, session):
    if not loop or not session:
        sys.stderr.write('Please enable iTerm2 Python API')
        return None

    try:
        file_list = utils.check_paths_readable(file_paths, True)

        sys.stdout.write('\x03')
        sys.stdout.flush()
        read_server_output(0.2)

        has_dir = False
        for file in file_list:
            if file['is_dir'] or len(file['path_name']) > 1:
                has_dir = True
                break
        if has_dir:
            sys.stdout.write('trz -d\r')
        else:
            sys.stdout.write('trz\r')
        sys.stdout.flush()

        for _ in range(20):
            output = read_server_output(0.15)
            idx = output.find(b'\n')
            if idx > 0 and output[:idx].rstrip() in (b'trz', b'trz -d'):
                output = b'\r\n' + output[idx + 1:]
            trigger_match = re.search(TRZSZ_TRIGGER_REGEX, output.decode('latin1'))
            if trigger_match:
                loop.create_task(session.async_inject(output.replace(b'TRANSFER', b'DRAGFILE')))
                GLOBAL.upload_file_list = file_list
                return trigger_match
            loop.create_task(session.async_inject(output))
        return None

    except Exception as ex:
        sys.stderr.write(utils.TrzszError.get_err_msg(ex))
        return None


def main():
    try:
        parser = argparse.ArgumentParser(description='iTerm2 coprocess of trzsz which similar to lrzsz '
                                         '( rz / sz ) and compatible with tmux.')
        parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) py ' + __version__)
        parser.add_argument('-p',
                            '--progress',
                            type=ProgressType,
                            choices=list(ProgressType),
                            default=ProgressType.ZENITY,
                            help='the progress bar type. (default: zenity)')
        parser.add_argument('-d',
                            '--destpath',
                            type=str,
                            default=None,
                            help='the default save destination path. (default: choose each time)')
        parser.add_argument('args', nargs='+', help='iTerm2 trigger parameters. (generally should be \\1)')
        args = parser.parse_args()

        loop = asyncio.new_event_loop()
        force = args.progress == ProgressType.TEXT and args.args[0] != 'dragfiles'
        connection, session = loop.run_until_complete(get_running_session(force))
        if connection and session:
            thread = threading.Thread(target=side_thread, args=(loop, ), daemon=True)
            thread.start()
            asyncio.run_coroutine_threadsafe(keystroke_filter(connection, session), loop)
            asyncio.run_coroutine_threadsafe(keystroke_monitor(connection, session), loop)

        if len(args.args) > 1 and args.args[0] == 'dragfiles':
            trigger_match = drag_files_to_upload(args.args[1:], loop, session)
            if not trigger_match:
                return
        else:
            trigger_match = re.search(TRZSZ_TRIGGER_REGEX, args.args[0])
            if not trigger_match:
                raise utils.TrzszError('Please check iTerm2 Trigger configuration', trace=False)

        mode = trigger_match.group(1)
        unique_id = trigger_match.group(3)
        remote_is_windows = False
        if unique_id == ':1' or (len(unique_id) == 14 and unique_id.endswith('10')):
            remote_is_windows = True

        if unique_id_exists(unique_id):
            return
        if mode == 'S':
            download_files(args, loop, connection, session, remote_is_windows)
        elif mode == 'R':
            upload_files(args, loop, connection, session, False, remote_is_windows)
        elif mode == 'D':
            upload_files(args, loop, connection, session, True, remote_is_windows)
        else:
            raise utils.TrzszError(f'Unknown transfer mode: {mode}', trace=False)

    except Exception as ex:
        transfer.client_error(ex)


if __name__ == '__main__':
    main()
