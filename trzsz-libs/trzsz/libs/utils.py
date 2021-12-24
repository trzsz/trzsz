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
import sys
import json
import zlib
import atexit
import base64
import select
import hashlib
import termios
import subprocess

tmux_output_junk = False
tmux_real_stdout = sys.stdout

try:
    stdin_old_tty = termios.tcgetattr(sys.stdin.fileno())
except termios.error:
    stdin_old_tty = None

def reset_stdin_tty():
    global stdin_old_tty
    if stdin_old_tty:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, stdin_old_tty)
        stdin_old_tty = None

atexit.register(reset_stdin_tty)

class TrzszError(Exception):
    def __init__(self, msg, typ=False):
        Exception.__init__(self, msg)
        self.typ = typ
        self.msg = msg

    def __str__(self):
        if self.typ:
            return '[TrzszError] %s: %s' % (self.typ, self.msg)
        return '[TrzszError] %s' % self.msg

class Callback(object):
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

def clean_input(timeout):
    while True:
        r, w, x = select.select([sys.stdin], [], [], timeout)
        if not r:
            break
        os.read(sys.stdin.fileno(), 1024)

def delay_exit(succ, msg):
    if isinstance(msg, (bytes, bytearray)):
        msg = msg.decode('utf8')
    if not isinstance(msg, str):
        msg = str(msg)
    clean_input(0.2)
    reset_stdin_tty()
    sys.stdout.write('\x1b8\x1b[0J')
    sys.stdout.flush()
    if succ:
        sys.stdout.write(msg + '\n')
    else:
        sys.stderr.write(msg + '\n')
    sys.exit(0 if succ else 1)

def send_line(typ, buf):
    if not isinstance(buf, (bytes, bytearray)):
        buf = buf.encode('utf8')
    enc = base64.b64encode(zlib.compress(buf)).decode('utf8')
    tmux_real_stdout.write('%s:%s\n' % (typ, enc))
    tmux_real_stdout.flush()

def recv_line(expect_typ, binary=False, may_has_junk=False):
    s = sys.stdin.readline()
    if tmux_output_junk or may_has_junk:
        while s[-2] == '\r':
            s += sys.stdin.readline()
        flag = expect_typ + ':'
        if flag in s:
            s = flag + s.split(flag)[-1]
    try:
        typ, buf = s.split(':', 1)
        dec = zlib.decompress(base64.b64decode(buf))
        return typ, (dec if binary else dec.decode('utf8'))
    except (ValueError, TypeError, zlib.error):
        return False, s

def check_succ():
    typ, buf = recv_line('SUCC')
    if typ == '#EXIT':
        delay_exit(False, buf)
    if typ != 'SUCC':
        raise TrzszError(buf, typ)
    return buf

def send_succ(info):
    send_line('SUCC', info)

def send_fail(info):
    send_line('FAIL', info)

def send_exit(succ, msg):
    clean_input(0.2)
    send_line('#EXIT', msg)
    sys.exit(0 if succ else 1)

def send_config(quiet=False, overwrite=False):
    config = {}
    if quiet:
        config['quiet'] = True
    if overwrite:
        config['overwrite'] = True
    if tmux_real_stdout != sys.stdout:
        config['tmux_output_junk'] = True
    send_succ(json.dumps(config))

def check_config():
    typ, cfg = recv_line('SUCC', False, True)
    if typ != 'SUCC':
        raise TrzszError(cfg, typ)
    if cfg == 'OK':
        return {}
    try:
        config = json.loads(cfg)
    except ValueError:
        raise TrzszError(cfg, 'JSON INVALID')
    global tmux_output_junk
    tmux_output_junk = config.get('tmux_output_junk', False)
    return config

def check_exit():
    typ, buf = recv_line('#EXIT')
    delay_exit(typ == '#EXIT', buf)

def send_check(typ, buf):
    send_line(typ, buf)
    return check_succ()

def recv_check(expect_typ, binary=False):
    typ, buf = recv_line(expect_typ, binary)
    if typ == '#EXIT':
        delay_exit(False, buf)
    if typ != expect_typ:
        raise TrzszError(buf, typ)
    return buf

def check_path(dest_path):
    if not os.path.isdir(dest_path):
        raise TrzszError('Not a directory: %s' % dest_path)
    if not os.access(dest_path, os.W_OK):
        raise TrzszError('No permission to write: %s' % dest_path)
    return True

def check_files(file_list):
    for f in file_list:
        if not os.path.exists(f):
            raise TrzszError('No such file: %s' % f)
        if not os.path.isfile(f):
            raise TrzszError('Not a regular file: %s' % f)
        if not os.access(f, os.R_OK):
            raise TrzszError('No permission to read: %s' % f)
    return True

def check_tmux():
    if 'TMUX' not in os.environ:
        return
    output = subprocess.check_output(['tmux', 'display-message', '-p', '#{client_tty}:#{client_control_mode}'])
    tmux_tty, control_mode = output.decode('utf8').strip().split(':')
    if control_mode == '1' or (not tmux_tty.startswith('/')) or (not os.path.exists(tmux_tty)):
        return
    global tmux_real_stdout
    tmux_real_stdout = open(tmux_tty, 'w')
    sys.stdout.write('\n\x1b[1A\x1b[0J')

def send_files(file_list, callback=None):
    send_check('NUM', str(len(file_list)))
    if callback:
        callback.on_num(len(file_list))

    remote_list = []

    for file_path in file_list:
        name = os.path.basename(file_path)
        file_name = send_check('NAME', name)
        if callback:
            callback.on_name(name)

        file_size = os.path.getsize(file_path)
        send_check('SIZE', str(file_size))
        if callback:
            callback.on_size(file_size)

        step = 0
        m = hashlib.md5()
        with open(file_path, 'rb') as f:
            while step < file_size:
                data = f.read(10240)
                send_line('DATA', data)
                m.update(data)
                check_succ()
                step += len(data)
                if callback:
                    callback.on_step(step)

        send_check('MD5', m.hexdigest())
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
    raise TrzszError('Fail to assign new file name')

def recv_files(dest_path, callback=None, overwrite=False):
    num = int(recv_check('NUM'))
    send_succ(str(num))
    if callback:
        callback.on_num(num)

    local_list = []

    for i in range(num):
        name = recv_check('NAME')
        file_name = name if overwrite else get_new_name(dest_path, name)
        send_succ(file_name)
        if callback:
            callback.on_name(name)

        file_size = int(recv_check('SIZE'))
        send_succ(str(file_size))
        if callback:
            callback.on_size(file_size)

        step = 0
        m = hashlib.md5()
        with open(os.path.join(dest_path, file_name), 'wb') as f:
            while step < file_size:
                data = recv_check('DATA', True)
                f.write(data)
                step += len(data)
                if callback:
                    callback.on_step(step)
                send_succ(str(len(data)))
                m.update(data)

        digest = recv_check('MD5')
        if digest == m.hexdigest():
            send_succ(digest)
        else:
            raise TrzszError('Check MD5 of %s failed' % name)
        if callback:
            callback.on_done(file_name)
        local_list.append(file_name)

    return local_list
