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
import zlib
import atexit
import base64
import select
import hashlib
import termios

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

class FileError(Exception):
    pass

class SendError(Exception):
    def __init__(self, typ, msg):
        Exception.__init__(self, msg)
        self.typ = typ
        self.msg = msg

    def __str__(self):
        if self.typ:
            return '[SendError] %s: %s' % (self.typ, self.msg)
        return '[SendError] %s' % self.msg

class RecvError(Exception):
    def __init__(self, typ, msg):
        Exception.__init__(self, msg)
        self.typ = typ
        self.msg = msg

    def __str__(self):
        if self.typ:
            return '[RecvError] %s: %s' % (self.typ, self.msg)
        return '[RecvError] %s' % self.msg

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

def delay_exit(succ, msg):
    if isinstance(msg, (bytes, bytearray)):
        msg = msg.decode('utf8')
    if not isinstance(msg, str):
        msg = str(msg)
    while True:
        r, w, x = select.select([sys.stdin], [], [], 0.2)
        if not r:
            break
        sys.stdin.readline()
    reset_stdin_tty()
    if succ:
        sys.stdout.write(msg.ljust(30) + '\n')
        sys.exit(0)
    else:
        sys.stderr.write(msg.ljust(30) + '\n')
        sys.exit(1)

def send_line(typ, buf):
    if not isinstance(buf, (bytes, bytearray)):
        buf = buf.encode('utf8')
    enc = base64.b64encode(zlib.compress(buf)).decode('utf8')
    sys.stdout.write('%s:%s\n' % (typ, enc))
    sys.stdout.flush()

def recv_line(binary=False):
    s = sys.stdin.readline()
    try:
        typ, buf = s.split(':', 1)
        dec = zlib.decompress(base64.b64decode(buf))
        return typ, (dec if binary else dec.decode('utf8'))
    except ValueError:
        return False, s
    except TypeError:
        return False, s
    except zlib.error:
        return False, s

def check_succ():
    typ, buf = recv_line()
    if typ == '#EXIT':
        delay_exit(False, buf)
    if typ != 'SUCC':
        raise SendError(typ, buf)
    return buf

def send_succ(info):
    send_line('SUCC', info)

def send_fail(info):
    send_line('FAIL', info)

def send_exit(succ, msg):
    while True:
        r, w, x = select.select([sys.stdin], [], [], 0.2)
        if not r:
            break
        sys.stdin.readline()
    send_line('#EXIT', msg)
    if succ:
        sys.exit(0)
    else:
        sys.exit(1)

def check_exit(succ):
    typ, buf = recv_line()
    delay_exit(succ and typ == '#EXIT', buf)

def send_check(typ, buf):
    send_line(typ, buf)
    return check_succ()

def recv_check(expect_typ, binary=False):
    typ, buf = recv_line(binary)
    if typ == '#EXIT':
        delay_exit(False, buf)
    if typ != expect_typ:
        raise RecvError(typ, buf)
    return buf

def check_path(dest_path):
    if not os.path.isdir(dest_path):
        raise FileError('Not a directory: %s' % dest_path)
    if not os.access(dest_path, os.W_OK):
        raise FileError('No permission to write: %s' % dest_path)
    return True

def check_files(file_list):
    for f in file_list:
        if not os.path.exists(f):
            raise FileError('No such file: %s' % f)
        if not os.path.isfile(f):
            raise FileError('Not a regular file: %s' % f)
        if not os.access(f, os.R_OK):
            raise FileError('No permission to read: %s' % f)
    return True

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
    raise RecvError(False, 'Fail to assign new file name')

def recv_files(dest_path, callback=None):
    num = int(recv_check('NUM'))
    send_succ(str(num))
    if callback:
        callback.on_num(num)

    local_list = []

    for i in range(num):
        name = recv_check('NAME')
        file_name = get_new_name(dest_path, name)
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
            raise RecvError(False, 'Check MD5 of %s failed' % name)
        if callback:
            callback.on_done(file_name)
        local_list.append(file_name)

    return local_list
