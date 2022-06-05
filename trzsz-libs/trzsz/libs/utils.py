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
import json
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

if is_windows:
    # pylint: disable=unused-import
    from trzsz.libs.wins import set_stdin_raw, reset_stdin_tty
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

    def on_done(self, name):
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
        return
    while True:
        r, w, x = select.select([sys.stdin], [], [], timeout)
        if not r:
            break
        os.read(sys.stdin.fileno(), 1024 * 1024)

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

trzsz_stopped = False
interruptible = False

def read_line():
    global interruptible
    s = ''
    while True:
        if trzsz_stopped:
            raise TrzszError('Stopped', trace=False)
        try:
            interruptible = True
            c = sys.stdin.read(1)
            interruptible = False
        except KeyboardInterrupt:
            raise TrzszError('Stopped', trace=False)
        if c == '\n':
            break
        if c == '\x03':
            raise TrzszError('Interrupted', trace=False)
        s += c
    return s

def is_vt100_end(b):
    if 'a' <= b <= 'z':
        return True
    if 'A' <= b <= 'Z':
        return True
    return False

def is_trzsz_letter(b):
    if 'a' <= b <= 'z':
        return True
    if 'A' <= b <= 'Z':
        return True
    if '0' <= b <= '9':
        return True
    if b in '#:+/=':
        return True
    return False

def read_line_on_windows():
    global interruptible
    s = ''
    skip_vt100 = False
    while True:
        if trzsz_stopped:
            raise TrzszError('Stopped', trace=False)
        try:
            interruptible = True
            c = sys.stdin.read(1)
            interruptible = False
        except KeyboardInterrupt:
            raise TrzszError('Stopped', trace=False)
        if c == '!':
            break
        if c == '\x03':
            raise TrzszError('Interrupted', trace=False)
        if skip_vt100:
            if is_vt100_end(c):
                skip_vt100 = False
        elif c == '\x1b':
            skip_vt100 = True
        elif is_trzsz_letter(c):
            s += c
    return s

def recv_line(expect_typ, may_has_junk=False):
    if is_windows:
        line = read_line_on_windows()
        if tmux_output_junk or may_has_junk:
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
        data = sys.stdin.read(size).encode(encoding='latin1', errors='surrogateescape')
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

def send_action(confirm, version, remote_is_windows):
    action = {'lang': 'py', 'confirm': confirm, 'version': version}
    if remote_is_windows:
        global protocol_newline
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
    global clean_timeout, trzsz_stopped
    trzsz_stopped = True
    clean_timeout = max(max_chunk_time * 2, 0.5)
    if interruptible:
        os.kill(os.getpid(), signal.SIGINT)

def terminate(_signum, _frame):
    raise TrzszError('Terminated', trace=False)

signal.signal(signal.SIGTERM, terminate)

def interrupte(_signum, _frame):
    raise TrzszError('Interrupted', trace=False)

signal.signal(signal.SIGINT, interrupte)

def client_exit(msg):
    clean_input(0.2)
    send_string('EXIT', msg)

def recv_exit():
    return recv_string('EXIT')

def server_exit(msg):
    clean_input(0.2)
    reset_stdin_tty()
    sys.stdout.write('\x1b8\x1b[0J')
    if is_windows:
        sys.stdout.write('\r\n')
    sys.stdout.write(msg)
    sys.stdout.write('\n')

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

def check_files_readable(file_list):
    for f in file_list:
        if not os.path.exists(f):
            raise TrzszError('No such file: %s' % f, trace=False)
        if os.path.isdir(f):
            raise TrzszError('Is a directory: %s' % f, trace=False)
        if not os.path.isfile(f):
            raise TrzszError('Not a regular file: %s' % f, trace=False)
        if not os.access(f, os.R_OK):
            raise TrzszError('No permission to read: %s' % f, trace=False)
    return True

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
    try:
        if sys.version_info >= (3, 7):
            sys.stdin.reconfigure(encoding='latin1', errors='surrogateescape')
        elif sys.version_info < (3, 0):
            reload(sys)  # pylint:disable=undefined-variable
            sys.setdefaultencoding('latin1')
    except AttributeError:
        pass

def send_files(file_list, callback=None):
    binary = transfer_config.get('binary', False)
    max_buf_size = transfer_config.get('bufsize', 10 * 1024 * 1024)
    escape_chars = transfer_config.get('escape_chars', [])

    num = len(file_list)
    send_integer('NUM', num)
    check_integer(num)
    if callback:
        callback.on_num(num)

    buf_size = 1024
    remote_list = []

    for file_path in file_list:
        name = os.path.basename(file_path)
        send_string('NAME', name)
        file_name = recv_string('SUCC')
        if callback:
            callback.on_name(name)

        file_size = os.path.getsize(file_path)
        send_integer('SIZE', file_size)
        check_integer(file_size)
        if callback:
            callback.on_size(file_size)

        step = 0
        m = hashlib.md5()
        with open(file_path, 'rb') as f:
            while step < file_size:
                begin_time = time.time()
                data = f.read(buf_size)
                send_data(data, binary, escape_chars)
                m.update(data)
                check_integer(len(data))
                step += len(data)
                if callback:
                    callback.on_step(step)
                chunk_time = time.time() - begin_time
                if chunk_time < 1.0 and buf_size < max_buf_size:
                    buf_size = min(buf_size * 2, max_buf_size)
                global max_chunk_time
                if chunk_time > max_chunk_time:
                    max_chunk_time = chunk_time

        digest = m.digest()
        send_binary('MD5', digest)
        check_binary(digest)
        if callback:
            callback.on_done(file_name)
        remote_list.append(file_name)

    return remote_list

def get_new_name(path, name):
    if not os.path.exists(os.path.join(path, name)):
        return name
    for i in range(1000):
        new_name = '%s.%d' % (name, i)
        if not os.path.exists(os.path.join(path, new_name)):
            return new_name
    raise TrzszError('Fail to assign new file name', trace=False)

def open_dest_file(file_path):
    try:
        return open(file_path, 'wb')
    except IOError as e:
        if e.errno == 13:
            err_msg = 'No permission to write: %s' % file_path
        elif e.errno == 21:
            err_msg = 'Is a directory: %s' % file_path
        else:
            err_msg = str(e)
        raise TrzszError(err_msg, trace=False)

def recv_files(dest_path, callback=None):
    binary = transfer_config.get('binary', False)
    overwrite = transfer_config.get('overwrite', False)
    timeout = transfer_config.get('timeout', 100)
    escape_chars = transfer_config.get('escape_chars', [])

    num = recv_integer('NUM')
    send_integer('SUCC', num)
    if callback:
        callback.on_num(num)

    local_list = []

    for i in range(num):
        name = recv_string('NAME')
        file_name = name if overwrite else get_new_name(dest_path, name)
        with open_dest_file(os.path.join(dest_path, file_name)) as f:
            send_string('SUCC', file_name)
            if callback:
                callback.on_name(name)

            file_size = recv_integer('SIZE')
            send_integer('SUCC', file_size)
            if callback:
                callback.on_size(file_size)

            step = 0
            m = hashlib.md5()
            while step < file_size:
                begin_time = time.time()
                data = recv_data(binary, escape_chars, timeout)
                f.write(data)
                step += len(data)
                if callback:
                    callback.on_step(step)
                send_integer('SUCC', len(data))
                m.update(data)
                chunk_time = time.time() - begin_time
                global max_chunk_time
                if chunk_time > max_chunk_time:
                    max_chunk_time = chunk_time

        digest = recv_binary('MD5')
        if digest == m.digest():
            send_binary('SUCC', digest)
        else:
            raise TrzszError('Check MD5 of %s failed' % name, trace=False)
        if callback:
            callback.on_done(file_name)
        local_list.append(file_name)

    return local_list
