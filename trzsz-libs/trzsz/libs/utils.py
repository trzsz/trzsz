# MIT License
#
# Copyright (c) 2023 Lonny Wong
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
import atexit
import base64
import select
import signal
import hashlib
import argparse
import platform
import traceback
import subprocess

NO_TMUX = 0
TMUX_NORMAL_MODE = 1
TMUX_CONTROL_MODE = 2

tmux_output_junk = False
tmux_real_stdout = sys.stdout
tmux_pane_width = -1
protocol_newline = '\n'
transfer_config = {}
is_windows = platform.system() == 'Windows'
remote_is_windows = False

if is_windows:
    # pylint: disable=unused-import
    from trzsz.libs.wins import set_stdin_raw, reset_stdin_tty, enable_virtual_terminal, setup_console_output
else:
    import tty
    import termios
    stdin_old_tty = None

    def set_stdin_raw():
        global stdin_old_tty
        stdin_old_tty = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno(), termios.TCSANOW)

    def reset_stdin_tty():
        global stdin_old_tty
        if stdin_old_tty:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, stdin_old_tty)
            stdin_old_tty = None

atexit.register(reset_stdin_tty)

if sys.version_info >= (3, ):
    unicode = str

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
            except Exception as e:
                msg = 'decode [%s] error: %s' % (msg, str(e))
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

class TrzszCallback(object):

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
        return None

    def __call__(self, parser, namespace, values, option_string=None):
        buf_size = self.parse_size(values)
        if self.min_size and buf_size < self.parse_size(self.min_size):
            raise argparse.ArgumentError(self, 'less than %s' % self.min_size)
        if self.max_size and buf_size > self.parse_size(self.max_size):
            raise argparse.ArgumentError(self, 'greater than %s' % self.max_size)
        setattr(namespace, self.dest, buf_size)

clean_timeout = 0.1

def clean_input(timeout):
    if is_windows:
        time.sleep(timeout)
        return
    while True:
        r, w, x = select.select([sys.stdin], [], [], timeout)
        if not r:
            break
        if not os.read(sys.stdin.fileno(), 10240):
            break

def encode_buffer(buf):
    return base64.b64encode(zlib.compress(buf)).decode('utf8')

def decode_buffer(buf):
    try:
        return zlib.decompress(base64.b64decode(buf))
    except (TypeError, zlib.error) as e:
        raise TrzszError(buf, str(e))

def send_line(typ, buf):
    tmux_real_stdout.write('#%s:%s%s' % (typ, buf, protocol_newline))
    tmux_real_stdout.flush()

next_buffer = b''

def read_buffer(size):
    if next_buffer:
        return next_buffer
    buf = os.read(sys.stdin.fileno(), size)
    if not buf:
        raise TrzszError('EndOfStdin', trace=False)
    return buf

def read_line():
    global next_buffer
    buffer = []
    while True:
        buf = read_buffer(10240)
        new_line_idx = buf.find(b'\n')
        if new_line_idx >= 0:
            next_buffer = buf[new_line_idx + 1:]  # +1 to ignroe the '\n'
            buf = buf[:new_line_idx]
        else:
            next_buffer = b''
        if buf.find(b'\x03') >= 0:  # `ctrl + c` to interrupt
            raise TrzszError('Interrupted', trace=False)
        buffer.append(buf)
        if new_line_idx >= 0:
            return b''.join(buffer).decode(encoding='latin1', errors='surrogateescape')

def read_binary(size):
    global next_buffer
    length = 0
    buffer = []
    while length < size:
        buf = read_buffer(size - length)
        next_buffer = b''
        length += len(buf)
        buffer.append(buf)
    return b''.join(buffer)

def is_vt100_end(b):
    if b'a' <= b <= b'z':
        return True
    if b'A' <= b <= b'Z':
        return True
    return False

def is_trzsz_letter(b):
    if b'a' <= b <= b'z':
        return True
    if b'A' <= b <= b'Z':
        return True
    if b'0' <= b <= b'9':
        return True
    if b in b'#:+/=':
        return True
    return False

def read_line_on_windows():
    global next_buffer
    buffer = []
    last_byte = b'\x1b'
    skip_vt100 = False
    has_new_line = False
    may_duplicate = False
    has_cursor_home = False
    pre_has_cursor_home = False
    while True:
        buf = read_buffer(10240)
        new_line_idx = buf.find(b'!')
        if new_line_idx >= 0:
            next_buffer = buf[new_line_idx + 1:]  # +1 to ignroe the '\n'
            buf = buf[:new_line_idx]
        else:
            next_buffer = b''
        for i in range(len(buf)):
            c = buf[i:i + 1]
            if c == b'\x03':  # `ctrl + c` to interrupt
                raise TrzszError('Interrupted', trace=False)
            if c == b'\n':
                has_new_line = True
            if skip_vt100:
                if is_vt100_end(c):
                    skip_vt100 = False
                    # moving the cursor may result in duplicate characters
                    if c == b'H' and b'0' <= last_byte <= b'9':
                        may_duplicate = True
                if last_byte == b'[' and c == b'H':
                    has_cursor_home = True
                last_byte = c
            elif c == b'\x1b':
                skip_vt100 = True
                last_byte = c
            elif is_trzsz_letter(c):
                if may_duplicate:
                    may_duplicate = False
                    # skip the duplicate characters, e.g., the "8" in "8\r\n\x1b[25;119H8".
                    if has_new_line and len(buffer) > 0 and (c == buffer[-1] or pre_has_cursor_home):
                        buffer[-1] = c
                        continue
                buffer.append(c)
                pre_has_cursor_home = has_cursor_home
                has_cursor_home = False
                has_new_line = False
        if new_line_idx >= 0 and len(buffer) > 0 and not skip_vt100:
            return b''.join(buffer).decode(encoding='latin1', errors='surrogateescape')

def recv_line(expect_typ, may_has_junk=False):
    if is_windows or remote_is_windows:
        line = read_line_on_windows()
        idx = line.rfind('#' + expect_typ + ':')
        if idx >= 0:
            line = line[idx:]
        return line
    line = read_line()
    if tmux_output_junk or may_has_junk:
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
        raise TrzszError('[%d] <> [%d]' % (result, expect))

def send_string(typ, buf):
    if sys.version_info >= (3, ) or isinstance(buf, unicode):
        buf = buf.encode('utf8')
    send_line(typ, encode_buffer(buf))

def recv_string(typ, may_has_junk=False):
    return decode_buffer(recv_check(typ, may_has_junk)).decode('utf8')

def check_string(expect):
    result = recv_string('SUCC')
    if result != expect:
        raise TrzszError('[%s] <> [%s]' % (result, expect))

def send_binary(typ, data):
    send_line(typ, encode_buffer(data))

def recv_binary(typ, may_has_junk=False):
    return decode_buffer(recv_check(typ, may_has_junk))

def check_binary(expect):
    result = recv_binary('SUCC')
    if result != expect:
        raise TrzszError('[%s] <> [%s]' % (str(result), str(expect)))

def get_escape_chars(escape_all):
    escape_chars = [['\xee', '\xee\xee'], ['\x7e', '\xee\x31']]
    if escape_all:
        for i, e in enumerate('\x02\x10\x1b\x1d\x9d'):
            escape_chars.append([e, '\xee' + chr(0x41 + i)])
    return escape_chars

def escape_data(data, escape_chars):
    if not escape_chars:
        return data
    pattern = b'|'.join(b'(%s)' % re.escape(p.encode('latin1')) for p, s in escape_chars)
    substs = [s.encode('latin1') for p, s in escape_chars]
    replace = lambda m: substs[m.lastindex - 1]
    return re.sub(pattern, replace, data)

def unescape_data(data, escape_chars):
    if not escape_chars:
        return data
    pattern = b'|'.join(b'(%s)' % re.escape(s.encode('latin1')) for p, s in escape_chars)
    substs = [p.encode('latin1') for p, s in escape_chars]
    replace = lambda m: substs[m.lastindex - 1]
    return re.sub(pattern, replace, data)

def send_data(data, binary, escape_chars):
    if not binary:
        send_binary('DATA', data)
        return
    buf = escape_data(data, escape_chars)
    out = tmux_real_stdout.buffer if hasattr(tmux_real_stdout, 'buffer') else tmux_real_stdout
    out.write(b'#DATA:%d\n%s' % (len(buf), buf))
    out.flush()

def recv_timeout(_signum, _frame):
    global clean_timeout
    clean_timeout = 3
    raise TrzszError('Receive data timeout', trace=False)

if not is_windows:
    signal.signal(signal.SIGALRM, recv_timeout)

def recv_data(binary, escape_chars, timeout):
    if timeout > 0 and not is_windows:
        signal.alarm(timeout)
    try:
        if not binary:
            return recv_binary('DATA')
        size = recv_integer('DATA')
        data = read_binary(size)
        return unescape_data(data, escape_chars)
    finally:
        if timeout > 0 and not is_windows:
            signal.alarm(0)

def send_json(typ, dic):
    send_string(typ, json.dumps(dic, encoding='latin1') if sys.version_info < (3, ) else json.dumps(dic))

def recv_json(typ, may_has_junk=False):
    dic = recv_string(typ, may_has_junk)
    try:
        return json.loads(dic, encoding='latin1') if sys.version_info < (3, ) else json.loads(dic)
    except ValueError as e:
        raise TrzszError(dic, str(e))

def send_action(confirm, version, is_windows):
    action = {'lang': 'py', 'confirm': confirm, 'version': version, 'support_dir': True}
    if is_windows:
        action['binary'] = False
        action['newline'] = '!\n'
        global protocol_newline, remote_is_windows
        remote_is_windows = True
        protocol_newline = '!\n'
    send_json('ACT', action)

def recv_action():
    action = recv_json('ACT')
    if 'newline' in action:
        global protocol_newline
        protocol_newline = action['newline']
    return action

def send_config(args, escape_chars):
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
    if tmux_real_stdout != sys.stdout:
        config['tmux_output_junk'] = True
        config['tmux_pane_width'] = tmux_pane_width
    global transfer_config
    transfer_config = config
    send_json('CFG', config)

def recv_config():
    config = recv_json('CFG', True)
    global transfer_config, tmux_output_junk
    transfer_config = config
    tmux_output_junk = config.get('tmux_output_junk', False)
    return config

max_chunk_time = 0

def stop_transferring():
    global clean_timeout
    clean_timeout = max(max_chunk_time * 2, 0.5)
    os.kill(os.getpid(), signal.SIGINT)

def terminate(_signum, _frame):
    raise TrzszError('Terminated', trace=False)

signal.signal(signal.SIGTERM, terminate)

def interrupte(_signum, _frame):
    raise TrzszError('Stopped', trace=False)

signal.signal(signal.SIGINT, interrupte)

def client_exit(msg):
    send_string('EXIT', msg)

def recv_exit():
    return recv_string('EXIT')

def server_exit(msg):
    clean_input(0.5)
    reset_stdin_tty()
    if is_windows:
        msg = msg.replace('\n', '\r\n')
        sys.stdout.write('\x1b[H\x1b[2J\x1b[?1049l')
    else:
        sys.stdout.write('\x1b8\x1b[0J')
    sys.stdout.write(msg)
    sys.stdout.write('\r\n')

def client_error(ex):
    clean_input(clean_timeout)
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
    clean_input(clean_timeout)
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

def check_path_readable(path_id, path, mode, file_list, rel_path, visited_dir):
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
        p = os.path.join(path, file)
        r = rel_path[:]
        r.append(file)
        check_path_readable(path_id, p, os.stat(p).st_mode, file_list, r, visited_dir)

def check_paths_readable(paths, directory):
    file_list = []
    for i, p in enumerate(paths):
        path = os.path.abspath(p)
        if not os.path.exists(path):
            raise TrzszError('No such file: %s' % path, trace=False)
        mode = os.stat(path).st_mode
        if not directory and stat.S_ISDIR(mode):
            raise TrzszError('Is a directory: %s' % path, trace=False)
        visited_dir = set()
        check_path_readable(i, path, mode, file_list, [os.path.basename(path)], visited_dir)
    return file_list

def check_duplicate_names(files):
    names = set()
    for f in files:
        p = os.path.join(*f['path_name'])
        if p in names:
            raise TrzszError('Duplicate name: %s' % p, trace=False)
        names.add(p)

def check_tmux():
    if 'TMUX' not in os.environ:
        return NO_TMUX
    out = subprocess.check_output(
        ['tmux', 'display-message', '-p', '#{client_tty}:#{client_control_mode}:#{pane_width}'])
    output = out.decode('utf8').strip()
    tokens = output.split(':')
    if len(tokens) != 3:
        raise TrzszError('tmux unexpect output: %s' % output)
    tmux_tty, control_mode, pane_width = tokens
    if control_mode == '1' or (not tmux_tty.startswith('/')) or (not os.path.exists(tmux_tty)):
        return TMUX_CONTROL_MODE
    global tmux_real_stdout, tmux_pane_width
    tmux_real_stdout = open(tmux_tty, 'w')
    if pane_width:
        tmux_pane_width = int(pane_width)
    return TMUX_NORMAL_MODE

def get_columns():
    try:
        _rows, columns = subprocess.check_output(['stty', 'size']).split()
        return int(columns)
    except Exception:
        return 0

def reconfigure_stdin():
    if sys.version_info >= (3, ):
        return
    try:
        reload(sys)  # pylint:disable=undefined-variable
        sys.setdefaultencoding('latin1')
    except AttributeError:
        pass

def send_file_num(num, callback):
    send_integer('NUM', num)
    check_integer(num)
    if callback:
        callback.on_num(num)

def send_file_name(file, directory, callback):
    name = file['path_name'][-1]
    if directory:
        f = file.copy()
        del f['abs_path']
        send_json('NAME', f)
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

def send_file_data(file, size, binary, escape_chars, max_buf_size, callback):
    step = 0
    buf_size = 1024
    m = hashlib.md5()
    while step < size:
        begin_time = time.time()
        data = file.read(buf_size)
        length = len(data)
        send_data(data, binary, escape_chars)
        m.update(data)
        check_integer(length)
        step += length
        if callback:
            callback.on_step(step)
        chunk_time = time.time() - begin_time
        if length == buf_size and chunk_time < 0.5 and buf_size < max_buf_size:
            buf_size = min(buf_size * 2, max_buf_size)
        elif chunk_time >= 2.0 and buf_size > 1024:
            buf_size = 1024
        global max_chunk_time
        if chunk_time > max_chunk_time:
            max_chunk_time = chunk_time
    return m.digest()

def send_file_md5(digest, callback):
    send_binary('MD5', digest)
    check_binary(digest)
    if callback:
        callback.on_done()

def send_files(file_list, callback=None):
    binary = transfer_config.get('binary', False)
    directory = transfer_config.get('directory', False)
    max_buf_size = transfer_config.get('bufsize', 10 * 1024 * 1024)
    escape_chars = transfer_config.get('escape_chars', [])

    send_file_num(len(file_list), callback)

    remote_list = []

    for file in file_list:
        remote_name = send_file_name(file, directory, callback)

        if remote_name not in remote_list:
            remote_list.append(remote_name)

        if file['is_dir']:
            continue

        size = send_file_size(file, callback)

        with open(file['abs_path'], 'rb') as f:
            md5 = send_file_data(f, size, binary, escape_chars, max_buf_size, callback)

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
    except IOError as e:
        if e.errno == 21 or (is_windows and os.path.isdir(path)):
            err_msg = 'Is a directory: %s' % path
        elif e.errno == 13:
            err_msg = 'No permission to write: %s' % path
        else:
            err_msg = str(e)
        raise TrzszError(err_msg, trace=False)

def do_create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path, 0o755)
    if not os.path.isdir(path):
        raise TrzszError('Not a directory: %s' % path, trace=False)

def create_file(path, file_name, overwrite):
    if overwrite:
        local_name = file_name
    else:
        local_name = get_new_name(path, file_name)
    file = do_create_file(os.path.join(path, local_name))
    return file, local_name

file_name_map = {}

def create_dir_or_file(path, file, overwrite):
    if 'path_name' not in file or 'path_id' not in file or 'is_dir' not in file or len(file['path_name']) < 1:
        raise TrzszError('Invalid name: %s' % path, trace=False)

    file_name = file['path_name'][-1]

    if overwrite:
        local_name = file['path_name'][0]
    else:
        if file['path_id'] in file_name_map:
            local_name = file_name_map[file['path_id']]
        else:
            local_name = get_new_name(path, file['path_name'][0])
            file_name_map[file['path_id']] = local_name

    if len(file['path_name']) > 1:
        p = os.path.join(path, local_name, *file['path_name'][1:-1])
        do_create_directory(p)
        full_path = os.path.join(p, file_name)
    else:
        full_path = os.path.join(path, local_name)

    if file['is_dir']:
        do_create_directory(full_path)
        return None, local_name, file_name
    file = do_create_file(full_path)
    return file, local_name, file_name

def recv_file_name(path, directory, overwrite, callback):
    if directory:
        json_name = recv_json('NAME')
        file, local_name, file_name = create_dir_or_file(path, json_name, overwrite)
    else:
        file_name = recv_string('NAME')
        file, local_name = create_file(path, file_name, overwrite)
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

def recv_file_data(file, size, binary, escape_chars, timeout, callback):
    step = 0
    m = hashlib.md5()
    while step < size:
        begin_time = time.time()
        data = recv_data(binary, escape_chars, timeout)
        file.write(data)
        step += len(data)
        if callback:
            callback.on_step(step)
        send_integer('SUCC', len(data))
        m.update(data)
        chunk_time = time.time() - begin_time
        global max_chunk_time
        if chunk_time > max_chunk_time:
            max_chunk_time = chunk_time
    return m.digest()

def recv_file_md5(digest, callback):
    expect_digest = recv_binary('MD5')
    if digest != expect_digest:
        raise TrzszError('Check MD5 failed', trace=False)
    send_binary('SUCC', digest)
    if callback:
        callback.on_done()

def recv_files(dest_path, callback=None):
    binary = transfer_config.get('binary', False)
    directory = transfer_config.get('directory', False)
    overwrite = transfer_config.get('overwrite', False)
    timeout = transfer_config.get('timeout', 100)
    escape_chars = transfer_config.get('escape_chars', [])

    num = recv_file_num(callback)

    local_list = []

    for i in range(num):
        file, local_name = recv_file_name(dest_path, directory, overwrite, callback)

        if local_name not in local_list:
            local_list.append(local_name)

        if not file:
            continue

        with file:
            size = recv_file_size(callback)
            md5 = recv_file_data(file, size, binary, escape_chars, timeout, callback)

        recv_file_md5(md5, callback)

    return local_list
