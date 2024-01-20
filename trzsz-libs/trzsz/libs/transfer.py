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
import sys
import time
import select
import hashlib
from . import utils


def send_action(confirm, version, remote_is_windows):
    action = {
        'lang': 'py',
        'confirm': confirm,
        'version': version,
        'support_dir': True,
        'protocol': utils.PROTOCOL_VERSION
    }
    if utils.IS_RUNNING_ON_WINDOWS or remote_is_windows:
        action['newline'] = '!\n'
        action['binary'] = False
    if remote_is_windows:
        utils.GLOBAL.windows_protocol = True
        utils.CONFIG.newline = '!\n'
    utils.send_json('ACT', action)


def recv_action():
    action = utils.recv_json('ACT', True)
    if 'newline' in action:
        utils.CONFIG.newline = action['newline']
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
    if utils.GLOBAL.tmux_mode == utils.TMUX_NORMAL_MODE:
        config['tmux_output_junk'] = True
    if utils.CONFIG.tmux_pane_width > 0:
        config['tmux_pane_width'] = utils.CONFIG.tmux_pane_width
    if 'protocol' in action:
        config['protocol'] = min(action['protocol'], utils.PROTOCOL_VERSION)
    utils.CONFIG.loads(config)
    utils.send_json('CFG', config)


def recv_config():
    config = utils.recv_json('CFG', True)
    utils.CONFIG.loads(config)
    return utils.CONFIG


def client_exit(msg):
    utils.send_string('EXIT', msg)


def recv_exit():
    return utils.recv_string('EXIT')


def server_exit(msg):
    utils.clean_input(0.5)
    utils.reset_stdin_tty()
    if utils.IS_RUNNING_ON_WINDOWS:
        msg = msg.replace('\n', '\r\n')
        sys.stdout.write('\x1b[H\x1b[2J\x1b[?1049l')
    else:
        sys.stdout.write('\x1b8\x1b[0J')
    sys.stdout.write(msg)
    sys.stdout.write('\r\n')
    sys.stdout.write('\x1b[?25h')
    if utils.CONFIG.tmux_output_junk:
        utils.tmux_refresh_client()


def client_error(ex):
    utils.clean_input(utils.GLOBAL.clean_timeout)
    err_msg = utils.TrzszError.get_err_msg(ex)
    trace = True
    if isinstance(ex, utils.TrzszError):
        trace = ex.trace_back()
        if ex.is_remote_exit():
            return
        if ex.is_remote_fail():
            if trace:
                sys.stderr.write(err_msg + '\n')
            return
    utils.send_string('FAIL' if trace else 'fail', err_msg)
    if trace:
        sys.stderr.write(err_msg + '\n')


def server_error(ex):
    utils.clean_input(utils.GLOBAL.clean_timeout)
    err_msg = utils.TrzszError.get_err_msg(ex)
    trace = True
    if isinstance(ex, utils.TrzszError):
        if ex.is_stop_and_delete():
            deleted_files = utils.delete_created_files()
            if deleted_files:
                server_exit('\r\n- '.join([ex.msg + ':'] + deleted_files))
                return
        trace = ex.trace_back()
        if ex.is_remote_exit() or ex.is_remote_fail():
            server_exit(err_msg)
            return
    utils.send_string('FAIL' if trace else 'fail', err_msg)
    server_exit(err_msg)


def send_file_num(num, callback):
    utils.send_integer('NUM', num)
    utils.check_integer(num)
    if callback:
        callback.on_num(num)


def send_file_name(file, callback):
    name = file['path_name'][-1]
    if utils.CONFIG.directory:
        file_copy = file.copy()
        del file_copy['abs_path']
        utils.send_json('NAME', file_copy)
    else:
        utils.send_string('NAME', name)
    remote_name = utils.recv_string('SUCC')
    if callback:
        callback.on_name(name)
    return remote_name


def send_file_size(file, callback):
    file_size = os.path.getsize(file['abs_path'])
    utils.send_integer('SIZE', file_size)
    utils.check_integer(file_size)
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
                if utils.is_eintr_error(err):
                    continue
                raise
        length = len(data)
        utils.send_data(data)
        md5.update(data)
        utils.check_integer(length)
        step += length
        if callback:
            callback.on_step(step)
        chunk_time = time.time() - begin_time
        if length == buf_size and chunk_time < 0.5 and buf_size < utils.CONFIG.max_buf_size:
            buf_size = min(buf_size * 2, utils.CONFIG.max_buf_size)
        elif chunk_time >= 2.0 and buf_size > 1024:
            buf_size = 1024
        if chunk_time > utils.GLOBAL.max_chunk_time:
            utils.GLOBAL.max_chunk_time = chunk_time
    return md5.digest()


def send_file_md5(digest, callback):
    utils.send_binary('MD5', digest)
    utils.check_binary(digest)
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
    num = utils.recv_integer('NUM')
    utils.send_integer('SUCC', num)
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
    raise utils.TrzszError('Fail to assign new file name', trace=False)


def do_create_file(path):
    try:
        file = open(path, 'wb')  # pylint: disable=consider-using-with
        utils.add_created_files(path)
        return file
    except IOError as ex:
        if ex.errno == 21 or (utils.IS_RUNNING_ON_WINDOWS and os.path.isdir(path)):
            err_msg = 'Is a directory: %s' % path
        elif ex.errno == 13:
            err_msg = 'No permission to write: %s' % path
        else:
            err_msg = str(ex)
        raise utils.TrzszError(err_msg, trace=False)


def do_create_directory(path):
    if not os.path.exists(path):
        try:
            os.makedirs(path, 0o755)
            utils.add_created_files(path)
            return
        except OSError:
            raise utils.TrzszError("Fail to create directory: %s" % path, trace=False)
    if not os.path.isdir(path):
        raise utils.TrzszError('Not a directory: %s' % path, trace=False)


def create_file(path, file_name):
    if utils.CONFIG.overwrite:
        local_name = file_name
    else:
        local_name = get_new_name(path, file_name)
    file = do_create_file(os.path.join(path, local_name))
    return file, local_name


file_name_map = {}


def create_dir_or_file(path, file):
    if 'path_name' not in file or 'path_id' not in file or 'is_dir' not in file or len(file['path_name']) < 1:
        raise utils.TrzszError('Invalid name: %s' % path, trace=False)

    file_name = file['path_name'][-1]

    if utils.CONFIG.overwrite:
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
    if utils.CONFIG.directory:
        json_name = utils.recv_json('NAME')
        file, local_name, file_name = create_dir_or_file(path, json_name)
    else:
        file_name = utils.recv_string('NAME')
        file, local_name = create_file(path, file_name)
    utils.send_string('SUCC', local_name)
    if callback:
        callback.on_name(file_name)
    return file, local_name


def recv_file_size(callback):
    file_size = utils.recv_integer('SIZE')
    utils.send_integer('SUCC', file_size)
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
        data = utils.recv_data()
        file.write(data)
        step += len(data)
        if callback:
            callback.on_step(step)
        utils.send_integer('SUCC', len(data))
        md5.update(data)
        chunk_time = time.time() - begin_time
        if chunk_time > utils.GLOBAL.max_chunk_time:
            utils.GLOBAL.max_chunk_time = chunk_time
    return md5.digest()


def recv_file_md5(digest, callback):
    expect_digest = utils.recv_binary('MD5')
    if digest != expect_digest:
        raise utils.TrzszError('Check MD5 failed', trace=False)
    utils.send_binary('SUCC', digest)
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
