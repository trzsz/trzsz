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
import json
import stat
import time
import zlib
import errno
import atexit
import base64
import select
import signal
import hashlib
import argparse
import platform
import traceback
import subprocess

NO_TMUX_MODE = 0
TMUX_NORMAL_MODE = 1
TMUX_CONTROL_MODE = 2

IS_RUNNING_ON_WINDOWS = platform.system() == 'Windows'


class GlobalVariables:

    def __init__(self):
        self.stdin_old_tty = None
        self.tmux_mode = NO_TMUX_MODE
        self.trzsz_writer = sys.stdout
        self.windows_protocol = False
        self.next_read_buffer = b''
        self.clean_timeout = 0.1
        self.max_chunk_time = 0
        self.stopped = False


GLOBAL = GlobalVariables()


class TransferConfig:

    def __init__(self):
        self.quiet = False
        self.binary = False
        self.directory = False
        self.overwrite = False
        self.timeout = 20
        self.newline = '\n'
        self.protocol = 0
        self.max_buf_size = 10 * 1024 * 1024
        self.escape_chars = []
        self.tmux_pane_width = 0
        self.tmux_output_junk = False

    def loads(self, config):
        self.quiet = config.get('quiet', self.quiet)
        self.binary = config.get('binary', self.binary)
        self.directory = config.get('directory', self.directory)
        self.overwrite = config.get('overwrite', self.overwrite)
        self.timeout = config.get('timeout', self.timeout)
        self.newline = config.get('newline', self.newline)
        self.protocol = config.get('protocol', self.protocol)
        self.max_buf_size = config.get('bufsize', self.max_buf_size)
        self.escape_chars = config.get('escape_chars', self.escape_chars)
        self.tmux_pane_width = config.get('tmux_pane_width', self.tmux_pane_width)
        self.tmux_output_junk = config.get('tmux_output_junk', self.tmux_output_junk)


CONFIG = TransferConfig()

if IS_RUNNING_ON_WINDOWS:
    # pylint: disable-next=unused-import
    from trzsz.libs.wins import set_stdin_raw, reset_stdin_tty, enable_virtual_terminal, setup_console_output  # NOQA
else:
    import tty
    import termios

    def set_stdin_raw():
        GLOBAL.stdin_old_tty = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno(), termios.TCSANOW)

    def reset_stdin_tty():
        if GLOBAL.stdin_old_tty:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, GLOBAL.stdin_old_tty)
            GLOBAL.stdin_old_tty = None


atexit.register(reset_stdin_tty)

if sys.version_info >= (3, ):
    unicode = str  # pylint: disable=invalid-name


def convert_to_unicode(buf):
    if sys.version_info < (3, ) and not isinstance(buf, unicode):
        return unicode(buf, 'utf8')
    return buf


def encode_if_unicode(buf):
    if sys.version_info < (3, ) and isinstance(buf, unicode):
        return buf.encode('utf8')
    return buf


class TrzszError(Exception):

    def __init__(self, msg, typ=None, trace=True):
        msg = encode_if_unicode(msg)
        if typ in ('fail', 'FAIL', 'EXIT'):
            try:
                msg = encode_if_unicode(decode_buffer(msg).decode('utf8'))
            except Exception as ex:
                msg = 'decode [%s] error: %s' % (msg, str(ex))
        elif typ:
            msg = '[TrzszError] %s: %s' % (typ, msg)
        Exception.__init__(self, msg)
        self.typ = typ
        self.msg = msg
        self.trace = trace

    def trace_back(self):
        if self.typ in ('fail', 'EXIT'):
            return False
        return self.trace

    def is_remote_exit(self):
        return self.typ == 'EXIT'

    def is_remote_fail(self):
        return self.typ in ('fail', 'FAIL')

    def __str__(self):
        return self.msg

    @staticmethod
    def get_err_msg(ex):
        if isinstance(ex, TrzszError) and (not ex.trace_back()):
            return str(ex)
        if isinstance(ex, Exception):
            return traceback.format_exc().strip()
        return str(ex)


class TrzszCallback:

    def on_num(self, num):
        pass

    def on_name(self, name):
        pass

    def on_size(self, size):
        pass

    def on_step(self, step):
        pass

    def on_done(self):
        pass


class BufferSizeParser(argparse.Action):

    def __init__(self, *args, **kwargs):
        self.min_size = kwargs['min_size']
        self.max_size = kwargs['max_size']
        kwargs.pop('min_size', None)
        kwargs.pop('max_size', None)
        if isinstance(kwargs['default'], str):
            kwargs['default'] = self.parse_size(kwargs['default'])
        argparse.Action.__init__(self, *args, **kwargs)

    def parse_size(self, value):
        size_match = re.search(r'^(\d+)(b|k|m|g|kb|mb|gb)?$', value, re.IGNORECASE)
        if not size_match:
            raise argparse.ArgumentError(self, 'invalid size ' + value)
        size_value = int(size_match.group(1))
        unit_suffix = size_match.group(2)
        if not unit_suffix:
            return size_value
        unit_suffix = unit_suffix.lower()
        if unit_suffix in ('b'):
            return size_value
        if unit_suffix in ('k', 'kb'):
            return size_value * 1024
        if unit_suffix in ('m', 'mb'):
            return size_value * 1024 * 1024
        if unit_suffix in ('g', 'gb'):
            return size_value * 1024 * 1024 * 1024
        raise argparse.ArgumentError(self, 'invalid size ' + value)

    def __call__(self, parser, namespace, values, option_string=None):
        buf_size = self.parse_size(values)
        if self.min_size and buf_size < self.parse_size(self.min_size):
            raise argparse.ArgumentError(self, 'less than %s' % self.min_size)
        if self.max_size and buf_size > self.parse_size(self.max_size):
            raise argparse.ArgumentError(self, 'greater than %s' % self.max_size)
        setattr(namespace, self.dest, buf_size)


def is_eintr_error(err):
    if hasattr(err, 'errno'):
        err_no = err.errno
    elif hasattr(err, '__getitem__') and len(err) > 0:
        err_no = err[0]
    else:
        return False
    return err_no == errno.EINTR


def clean_input(timeout):
    GLOBAL.stopped = True
    if IS_RUNNING_ON_WINDOWS:
        time.sleep(timeout)
        return
    while True:
        try:
            rlist, _wlist, _xlist = select.select([sys.stdin], [], [], timeout)
            if not rlist:
                break
            if not os.read(sys.stdin.fileno(), 32 * 1024):
                break
        except (OSError, select.error) as err:
            if is_eintr_error(err):
                continue
            break
        except:  # NOQA pylint:disable=bare-except
            break


def encode_buffer(buf):
    return base64.b64encode(zlib.compress(buf)).decode('utf8')


def decode_buffer(buf):
    try:
        return zlib.decompress(base64.b64decode(buf))
    except (TypeError, zlib.error) as ex:
        raise TrzszError(buf, str(ex))


def send_line(typ, buf):
    GLOBAL.trzsz_writer.write('#%s:%s%s' % (typ, buf, CONFIG.newline))
    GLOBAL.trzsz_writer.flush()


def read_buffer(size):
    if GLOBAL.next_read_buffer:
        return GLOBAL.next_read_buffer
    while True:
        try:
            buf = os.read(sys.stdin.fileno(), size)
            break
        except (OSError, select.error) as err:
            if is_eintr_error(err):
                continue
            raise
    if not buf:
        raise TrzszError('EndOfStdin', trace=False)
    return buf


def read_line():
    buffer = []
    while True:
        buf = read_buffer(32 * 1024)
        new_line_idx = buf.find(b'\n')
        if new_line_idx >= 0:
            # +1 to ignroe the '\n'
            GLOBAL.next_read_buffer = buf[new_line_idx + 1:]
            buf = buf[:new_line_idx]
        else:
            GLOBAL.next_read_buffer = b''
        if buf.find(b'\x03') >= 0:  # `ctrl + c` to interrupt
            raise TrzszError('Interrupted', trace=False)
        buffer.append(buf)
        if new_line_idx >= 0:
            return b''.join(buffer).decode(encoding='latin1', errors='surrogateescape')


def read_binary(size):
    length = 0
    buffer = []
    while length < size:
        buf = read_buffer(size - length)
        GLOBAL.next_read_buffer = b''
        length += len(buf)
        buffer.append(buf)
    return b''.join(buffer)


def is_vt100_end(char):
    if b'a' <= char <= b'z':
        return True
    if b'A' <= char <= b'Z':
        return True
    return False


def is_trzsz_letter(char):
    if b'a' <= char <= b'z':
        return True
    if b'A' <= char <= b'Z':
        return True
    if b'0' <= char <= b'9':
        return True
    if char in b'#:+/=':
        return True
    return False


def read_line_on_windows():  # pylint: disable=too-many-branches
    buffer = []
    last_byte = b'\x1b'
    skip_vt100 = False
    has_new_line = False
    may_duplicate = False
    has_cursor_home = False
    pre_has_cursor_home = False
    while True:
        buf = read_buffer(32 * 1024)
        new_line_idx = buf.find(b'!')
        if new_line_idx >= 0:
            # +1 to ignroe the '\n'
            GLOBAL.next_read_buffer = buf[new_line_idx + 1:]
            buf = buf[:new_line_idx]
        else:
            GLOBAL.next_read_buffer = b''
        for i in range(len(buf)):
            char = buf[i:i + 1]
            if char == b'\x03':  # `ctrl + c` to interrupt
                raise TrzszError('Interrupted', trace=False)
            if char == b'\n':
                has_new_line = True
            if skip_vt100:
                if is_vt100_end(char):
                    skip_vt100 = False
                    # moving the cursor may result in duplicate characters
                    if char == b'H' and b'0' <= last_byte <= b'9':
                        may_duplicate = True
                if last_byte == b'[' and char == b'H':
                    has_cursor_home = True
                last_byte = char
            elif char == b'\x1b':
                skip_vt100 = True
                last_byte = char
            elif is_trzsz_letter(char):
                if may_duplicate:
                    may_duplicate = False
                    # skip the duplicate characters, e.g., the "8" in "8\r\n\x1b[25;119H8".
                    if has_new_line and len(buffer) > 0 and (char == buffer[-1] or pre_has_cursor_home):
                        buffer[-1] = char
                        continue
                buffer.append(char)
                pre_has_cursor_home = has_cursor_home
                has_cursor_home = False
                has_new_line = False
        if new_line_idx >= 0 and len(buffer) > 0 and not skip_vt100:
            return b''.join(buffer).decode(encoding='latin1', errors='surrogateescape')


def recv_line(expect_typ, may_has_junk=False):
    if GLOBAL.stopped:
        raise TrzszError('Stopped', trace=False)
    if IS_RUNNING_ON_WINDOWS or GLOBAL.windows_protocol:
        line = read_line_on_windows()
        idx = line.rfind('#' + expect_typ + ':')
        if idx >= 0:
            line = line[idx:]
        return line
    line = read_line()
    if CONFIG.tmux_output_junk or may_has_junk:
        if line:
            while line[-1] == '\r':
                line = line[:-1] + read_line()
        idx = line.rfind('#' + expect_typ + ':')
        if idx >= 0:
            line = line[idx:]
    return line


def recv_check(expect_typ, may_has_junk=False):
    line = recv_line(expect_typ, may_has_junk)
    idx = line.find(':')
    if idx < 1:
        raise TrzszError(encode_buffer(line.encode('utf8')), 'colon')
    typ = line[1:idx]
    buf = line[idx + 1:]
    if typ != expect_typ:
        raise TrzszError(buf, typ)
    return buf


def send_integer(typ, value):
    send_line(typ, str(value))


def recv_integer(typ, may_has_junk=False):
    return int(recv_check(typ, may_has_junk))


def check_integer(expect):
    result = recv_integer('SUCC')
    if result != expect:
        raise TrzszError('Integer check [%d] <> [%d]' % (result, expect))


def send_string(typ, buf):
    if sys.version_info >= (3, ) or isinstance(buf, unicode):
        buf = buf.encode('utf8')
    send_line(typ, encode_buffer(buf))


def recv_string(typ, may_has_junk=False):
    return decode_buffer(recv_check(typ, may_has_junk)).decode('utf8')


def check_string(expect):
    result = recv_string('SUCC')
    if result != expect:
        raise TrzszError('String check [%s] <> [%s]' % (result, expect))


def send_binary(typ, data):
    send_line(typ, encode_buffer(data))


def recv_binary(typ, may_has_junk=False):
    return decode_buffer(recv_check(typ, may_has_junk))


def check_binary(expect):
    result = recv_binary('SUCC')
    if result != expect:
        raise TrzszError('Binary check [%s] <> [%s]' % (str(result), str(expect)))


def get_escape_chars(escape_all):
    escape_chars = [['\xee', '\xee\xee'], ['\x7e', '\xee\x31']]
    if escape_all:
        for i, char in enumerate('\x02\x10\x1b\x1d\x9d'):
            escape_chars.append([char, '\xee' + chr(0x41 + i)])
    return escape_chars


def escape_data(data, escape_chars):
    if not escape_chars:
        return data
    pattern = b'|'.join(b'(%s)' % re.escape(p.encode('latin1')) for p, s in escape_chars)
    substs = [s.encode('latin1') for p, s in escape_chars]
    return re.sub(pattern, lambda m: substs[m.lastindex - 1], data)


def unescape_data(data, escape_chars):
    if not escape_chars:
        return data
    pattern = b'|'.join(b'(%s)' % re.escape(s.encode('latin1')) for p, s in escape_chars)
    substs = [p.encode('latin1') for p, s in escape_chars]
    return re.sub(pattern, lambda m: substs[m.lastindex - 1], data)


def send_data(data):
    if not CONFIG.binary:
        send_binary('DATA', data)
        return
    buf = escape_data(data, CONFIG.escape_chars)
    out = GLOBAL.trzsz_writer.buffer if hasattr(GLOBAL.trzsz_writer, 'buffer') else GLOBAL.trzsz_writer
    out.write(b'#DATA:%d\n%s' % (len(buf), buf))
    out.flush()


def recv_timeout(_signum, _frame):
    GLOBAL.clean_timeout = 3
    raise TrzszError('Receive data timeout', trace=False)


if not IS_RUNNING_ON_WINDOWS:
    signal.signal(signal.SIGALRM, recv_timeout)


def recv_data():
    if CONFIG.timeout > 0 and not IS_RUNNING_ON_WINDOWS:
        signal.alarm(CONFIG.timeout)
    try:
        if not CONFIG.binary:
            return recv_binary('DATA')
        size = recv_integer('DATA')
        data = read_binary(size)
        return unescape_data(data, CONFIG.escape_chars)
    finally:
        if CONFIG.timeout > 0 and not IS_RUNNING_ON_WINDOWS:
            signal.alarm(0)


def send_json(typ, dic):
    send_string(typ, json.dumps(dic, encoding='latin1') if sys.version_info < (3, ) else json.dumps(dic))


def recv_json(typ, may_has_junk=False):
    dic = recv_string(typ, may_has_junk)
    try:
        return json.loads(dic, encoding='latin1') if sys.version_info < (3, ) else json.loads(dic)
    except ValueError as ex:
        raise TrzszError(dic, str(ex))


def send_action(confirm, version, remote_is_windows):
    action = {'lang': 'py', 'confirm': confirm, 'version': version, 'support_dir': True, 'protocol': 1}
    if IS_RUNNING_ON_WINDOWS or remote_is_windows:
        action['newline'] = '!\n'
        action['binary'] = False
    if remote_is_windows:
        GLOBAL.windows_protocol = True
        CONFIG.newline = '!\n'
    send_json('ACT', action)


def recv_action():
    action = recv_json('ACT')
    if 'newline' in action:
        CONFIG.newline = action['newline']
    return action


def send_config(args, action, escape_chars):
    config = {'lang': 'py'}
    if args.quiet:
        config['quiet'] = True
    if args.binary:
        config['binary'] = True
        config['escape_chars'] = escape_chars
    if args.directory:
        config['directory'] = True
    if args.bufsize:
        config['bufsize'] = args.bufsize
    if args.timeout:
        config['timeout'] = args.timeout
    if args.overwrite:
        config['overwrite'] = True
    if GLOBAL.tmux_mode == TMUX_NORMAL_MODE:
        config['tmux_output_junk'] = True
        config['tmux_pane_width'] = CONFIG.tmux_pane_width
    if 'protocol' in action:
        config['protocol'] = action['protocol']
    CONFIG.loads(config)
    send_json('CFG', config)


def recv_config():
    config = recv_json('CFG', True)
    CONFIG.loads(config)
    return CONFIG


def stop_transferring():
    if GLOBAL.stopped:
        return
    GLOBAL.stopped = True
    GLOBAL.clean_timeout = max(GLOBAL.max_chunk_time * 2, 0.5)
    os.kill(os.getpid(), signal.SIGINT)


def terminate(_signum, _frame):
    GLOBAL.stopped = True
    raise TrzszError('Terminated', trace=False)


signal.signal(signal.SIGTERM, terminate)


def interrupte(_signum, _frame):
    GLOBAL.stopped = True
    raise TrzszError('Stopped', trace=False)


signal.signal(signal.SIGINT, interrupte)


def client_exit(msg):
    send_string('EXIT', msg)


def recv_exit():
    return recv_string('EXIT')


def server_exit(msg):
    clean_input(0.5)
    reset_stdin_tty()
    if IS_RUNNING_ON_WINDOWS:
        msg = msg.replace('\n', '\r\n')
        sys.stdout.write('\x1b[H\x1b[2J\x1b[?1049l')
    else:
        sys.stdout.write('\x1b8\x1b[0J')
    sys.stdout.write(msg)
    sys.stdout.write('\r\n')


def client_error(ex):
    clean_input(GLOBAL.clean_timeout)
    err_msg = TrzszError.get_err_msg(ex)
    trace = True
    if isinstance(ex, TrzszError):
        trace = ex.trace_back()
        if ex.is_remote_exit():
            return
        if ex.is_remote_fail():
            if trace:
                sys.stderr.write(err_msg + '\n')
            return
    send_string('FAIL' if trace else 'fail', err_msg)
    if trace:
        sys.stderr.write(err_msg + '\n')


def server_error(ex):
    clean_input(GLOBAL.clean_timeout)
    err_msg = TrzszError.get_err_msg(ex)
    trace = True
    if isinstance(ex, TrzszError):
        trace = ex.trace_back()
        if ex.is_remote_exit() or ex.is_remote_fail():
            server_exit(err_msg)
            return
    send_string('FAIL' if trace else 'fail', err_msg)
    server_exit(err_msg)


def check_path_writable(dest_path):
    if not os.path.isdir(dest_path):
        raise TrzszError('Not a directory: %s' % dest_path, trace=False)
    if not os.access(dest_path, os.W_OK):
        raise TrzszError('No permission to write: %s' % dest_path, trace=False)
    return True


def check_path_readable(path_id, path, mode, file_list, rel_path, visited_dir):  # pylint: disable=too-many-arguments
    if not stat.S_ISDIR(mode):
        if not stat.S_ISREG(mode):
            raise TrzszError('Not a regular file: %s' % path, trace=False)
        if not os.access(path, os.R_OK):
            raise TrzszError('No permission to read: %s' % path, trace=False)
        file_list.append({'path_id': path_id, 'abs_path': path, 'path_name': rel_path, 'is_dir': False})
        return
    real_path = os.path.realpath(path)
    if real_path in visited_dir:
        raise TrzszError('Duplicate link: %s' % path, trace=False)
    visited_dir.add(real_path)
    file_list.append({'path_id': path_id, 'abs_path': path, 'path_name': rel_path, 'is_dir': True})
    for file in os.listdir(path):
        file_path = os.path.join(path, file)
        rel_path_copy = rel_path[:]
        rel_path_copy.append(file)
        check_path_readable(path_id, file_path, os.stat(file_path).st_mode, file_list, rel_path_copy, visited_dir)


def check_paths_readable(paths, directory):
    file_list = []
    for i, path in enumerate(paths):
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            raise TrzszError('No such file: %s' % abs_path, trace=False)
        mode = os.stat(abs_path).st_mode
        if not directory and stat.S_ISDIR(mode):
            raise TrzszError('Is a directory: %s' % abs_path, trace=False)
        visited_dir = set()
        check_path_readable(i, abs_path, mode, file_list, [os.path.basename(abs_path)], visited_dir)
    return file_list


def check_duplicate_names(files):
    names = set()
    for file in files:
        path = os.path.join(*file['path_name'])
        if path in names:
            raise TrzszError('Duplicate name: %s' % path, trace=False)
        names.add(path)


def check_tmux():
    if 'TMUX' not in os.environ:
        return NO_TMUX_MODE
    out = subprocess.check_output(
        ['tmux', 'display-message', '-p', '#{client_tty}:#{client_control_mode}:#{pane_width}'])
    output = out.decode('utf8').strip()
    tokens = output.split(':')
    if len(tokens) != 3:
        raise TrzszError('tmux unexpect output: %s' % output)
    tmux_tty, control_mode, pane_width = tokens
    if control_mode == '1' or (not tmux_tty.startswith('/')) or (not os.path.exists(tmux_tty)):
        GLOBAL.tmux_mode = TMUX_CONTROL_MODE
        return TMUX_CONTROL_MODE
    GLOBAL.trzsz_writer = open(tmux_tty, 'w')  # pylint: disable=consider-using-with
    if pane_width:
        CONFIG.tmux_pane_width = int(pane_width)
    GLOBAL.tmux_mode = TMUX_NORMAL_MODE
    return TMUX_NORMAL_MODE


def get_columns():
    try:
        _rows, columns = subprocess.check_output(['stty', 'size']).split()
        return int(columns)
    except:  # NOQA pylint:disable=bare-except
        return 0


def reconfigure_stdin():
    if sys.version_info >= (3, ):
        return
    try:
        reload(sys)  # NOQA pylint:disable=undefined-variable
        sys.setdefaultencoding('latin1')
    except AttributeError:
        pass


def send_file_num(num, callback):
    send_integer('NUM', num)
    check_integer(num)
    if callback:
        callback.on_num(num)


def send_file_name(file, callback):
    name = file['path_name'][-1]
    if CONFIG.directory:
        file_copy = file.copy()
        del file_copy['abs_path']
        send_json('NAME', file_copy)
    else:
        send_string('NAME', name)
    remote_name = recv_string('SUCC')
    if callback:
        callback.on_name(name)
    return remote_name


def send_file_size(file, callback):
    file_size = os.path.getsize(file['abs_path'])
    send_integer('SIZE', file_size)
    check_integer(file_size)
    if callback:
        callback.on_size(file_size)
    return file_size


def send_file_data(file, size, callback):
    step = 0
    if callback:
        callback.on_step(step)
    buf_size = 1024
    md5 = hashlib.md5()
    while step < size:
        begin_time = time.time()
        while True:
            try:
                data = file.read(buf_size)
                break
            except (OSError, select.error) as err:
                if is_eintr_error(err):
                    continue
                raise
        length = len(data)
        send_data(data)
        md5.update(data)
        check_integer(length)
        step += length
        if callback:
            callback.on_step(step)
        chunk_time = time.time() - begin_time
        if length == buf_size and chunk_time < 0.5 and buf_size < CONFIG.max_buf_size:
            buf_size = min(buf_size * 2, CONFIG.max_buf_size)
        elif chunk_time >= 2.0 and buf_size > 1024:
            buf_size = 1024
        if chunk_time > GLOBAL.max_chunk_time:
            GLOBAL.max_chunk_time = chunk_time
    return md5.digest()


def send_file_md5(digest, callback):
    send_binary('MD5', digest)
    check_binary(digest)
    if callback:
        callback.on_done()


def send_files(file_list, callback=None):
    send_file_num(len(file_list), callback)

    remote_list = []
    for file in file_list:
        remote_name = send_file_name(file, callback)

        if remote_name not in remote_list:
            remote_list.append(remote_name)

        if file['is_dir']:
            continue

        size = send_file_size(file, callback)

        with open(file['abs_path'], 'rb') as file_obj:
            md5 = send_file_data(file_obj, size, callback)

        send_file_md5(md5, callback)

    return remote_list


def recv_file_num(callback):
    num = recv_integer('NUM')
    send_integer('SUCC', num)
    if callback:
        callback.on_num(num)
    return num


def get_new_name(path, name):
    if not os.path.exists(os.path.join(path, name)):
        return name
    for i in range(1000):
        new_name = '%s.%d' % (name, i)
        if not os.path.exists(os.path.join(path, new_name)):
            return new_name
    raise TrzszError('Fail to assign new file name', trace=False)


def do_create_file(path):
    try:
        return open(path, 'wb')
    except IOError as ex:
        if ex.errno == 21 or (IS_RUNNING_ON_WINDOWS and os.path.isdir(path)):
            err_msg = 'Is a directory: %s' % path
        elif ex.errno == 13:
            err_msg = 'No permission to write: %s' % path
        else:
            err_msg = str(ex)
        raise TrzszError(err_msg, trace=False)


def do_create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path, 0o755)
    if not os.path.isdir(path):
        raise TrzszError('Not a directory: %s' % path, trace=False)


def create_file(path, file_name):
    if CONFIG.overwrite:
        local_name = file_name
    else:
        local_name = get_new_name(path, file_name)
    file = do_create_file(os.path.join(path, local_name))
    return file, local_name


file_name_map = {}


def create_dir_or_file(path, file):
    if 'path_name' not in file or 'path_id' not in file or 'is_dir' not in file or len(file['path_name']) < 1:
        raise TrzszError('Invalid name: %s' % path, trace=False)

    file_name = file['path_name'][-1]

    if CONFIG.overwrite:
        local_name = file['path_name'][0]
    else:
        if file['path_id'] in file_name_map:
            local_name = file_name_map[file['path_id']]
        else:
            local_name = get_new_name(path, file['path_name'][0])
            file_name_map[file['path_id']] = local_name

    if len(file['path_name']) > 1:
        parent_path = os.path.join(path, local_name, *file['path_name'][1:-1])
        do_create_directory(parent_path)
        full_path = os.path.join(parent_path, file_name)
    else:
        full_path = os.path.join(path, local_name)

    if file['is_dir']:
        do_create_directory(full_path)
        return None, local_name, file_name
    file = do_create_file(full_path)
    return file, local_name, file_name


def recv_file_name(path, callback):
    if CONFIG.directory:
        json_name = recv_json('NAME')
        file, local_name, file_name = create_dir_or_file(path, json_name)
    else:
        file_name = recv_string('NAME')
        file, local_name = create_file(path, file_name)
    send_string('SUCC', local_name)
    if callback:
        callback.on_name(file_name)
    return file, local_name


def recv_file_size(callback):
    file_size = recv_integer('SIZE')
    send_integer('SUCC', file_size)
    if callback:
        callback.on_size(file_size)
    return file_size


def recv_file_data(file, size, callback):
    step = 0
    if callback:
        callback.on_step(step)
    md5 = hashlib.md5()
    while step < size:
        begin_time = time.time()
        data = recv_data()
        file.write(data)
        step += len(data)
        if callback:
            callback.on_step(step)
        send_integer('SUCC', len(data))
        md5.update(data)
        chunk_time = time.time() - begin_time
        if chunk_time > GLOBAL.max_chunk_time:
            GLOBAL.max_chunk_time = chunk_time
    return md5.digest()


def recv_file_md5(digest, callback):
    expect_digest = recv_binary('MD5')
    if digest != expect_digest:
        raise TrzszError('Check MD5 failed', trace=False)
    send_binary('SUCC', digest)
    if callback:
        callback.on_done()


def recv_files(dest_path, callback=None):
    num = recv_file_num(callback)

    local_list = []
    for _ in range(num):
        file, local_name = recv_file_name(dest_path, callback)

        if local_name not in local_list:
            local_list.append(local_name)

        if not file:
            continue

        with file:
            size = recv_file_size(callback)
            md5 = recv_file_data(file, size, callback)

        recv_file_md5(md5, callback)

    return local_list
