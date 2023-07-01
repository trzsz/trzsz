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
import argparse
from trzsz.libs import utils
from trzsz.libs import transfer
from trzsz.svr.__version__ import __version__


def parse_args(sys_args):
    parser = argparse.ArgumentParser(description='Receive file(s), similar to rz and compatible with tmux.',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) py ' + __version__)
    parser.add_argument('-q', '--quiet', action='store_true', help='quiet (hide progress bar)')
    parser.add_argument('-y', '--overwrite', action='store_true', help='yes, overwrite existing file(s)')
    parser.add_argument('-b', '--binary', action='store_true', help='binary transfer mode, faster for binary files')
    parser.add_argument('-e', '--escape', action='store_true', help='escape all known control characters')
    parser.add_argument('-d', '--directory', action='store_true', help='transfer directories and files')
    parser.add_argument('-r', '--recursive', action='store_true', help='transfer directories and files, same as -d')
    parser.add_argument('-B',
                        '--bufsize',
                        min_size='1K',
                        max_size='1G',
                        default='10M',
                        action=utils.BufferSizeParser,
                        metavar='N',
                        help='max buffer chunk size (1K<=N<=1G). (default: 10M)')
    parser.add_argument('-t',
                        '--timeout',
                        type=int,
                        default=20,
                        metavar='N',
                        help='timeout ( N seconds ) for each buffer chunk.\nN <= 0 means never timeout. (default: 20)')
    parser.add_argument('path', nargs='?', default='.', help='path to save file(s). (default: current directory)')
    args = parser.parse_args(sys_args)
    if args.recursive is True:
        args.directory = True
    return args


def recv_files(args, dest_path):
    action = transfer.recv_action()

    if not action.get('confirm', False):
        transfer.server_exit('Cancelled')
        return

    # check if the client doesn't support binary mode
    if args.binary and action.get('binary') is False:
        args.binary = False
    # check if the client doesn't support transfer directory
    if args.directory and action.get('support_dir') is not True:
        raise utils.TrzszError("The client doesn't support transfer directory", trace=False)

    transfer.send_config(args, action, utils.get_escape_chars(args.escape))

    local_list = transfer.recv_files(dest_path, None)

    _ = transfer.recv_exit()
    transfer.server_exit(utils.format_saved_files(local_list, dest_path))


def main():
    args = parse_args(sys.argv[1:])
    dest_path = utils.convert_to_unicode(os.path.abspath(args.path))

    try:
        utils.check_path_writable(dest_path)
    except utils.TrzszError as ex:
        sys.stderr.write(str(ex) + '\n')
        return

    tmux_mode = utils.check_tmux()
    if args.binary and tmux_mode != utils.NO_TMUX_MODE:
        # 1. In tmux 1.8 normal mode, supports binary upload actually. But it's old version.
        # 2. In tmux 3.0a normal mode, tmux always runs with a UTF-8 locale for input.
        #    Tmux will convert binary data to UTF-8 encoding, and no option to change it.
        #    Try to convert the UTF-8 encoding data back to original, but fails in some case.
        #    Besides, don't know how to detect the input encoding of the running tmux version.
        #    See LC_CTYPE in tmux manual: https://man7.org/linux/man-pages/man1/tmux.1.html
        # 3. In tmux control mode, iTerm2 will ignore invisible characters, or something else.
        #    While sending the binary data, iTerm2 doesn't send 'send-keys' commands to tmux.
        sys.stdout.write('Binary upload in tmux is not supported, auto switch to base64 mode.\n')
        args.binary = False
    if args.binary and utils.IS_RUNNING_ON_WINDOWS:
        sys.stdout.write('Binary upload on Windows is not supported, auto switch to base64 mode.\n')
        args.binary = False

    unique_id = int(time.time() * 1000 % 10e10) * 100
    if utils.IS_RUNNING_ON_WINDOWS:
        utils.enable_virtual_terminal()
        utils.setup_console_output()
        unique_id += 10
    elif tmux_mode == utils.TMUX_NORMAL_MODE:
        sys.stdout.write('\n\n\x1b[2A\x1b[0J' if 0 < utils.get_columns() < 40 else '\n\x1b[1A\x1b[0J')
        unique_id += 20

    mode = 'D' if args.directory else 'R'
    sys.stdout.write('\x1b7\x07::TRZSZ:TRANSFER:%s:%s:%013d\r\n' % (mode, __version__, unique_id))
    sys.stdout.flush()

    try:
        utils.set_stdin_raw()
        utils.reconfigure_stdin()

        recv_files(args, dest_path)

    except Exception as ex:
        transfer.server_error(ex)


if __name__ == '__main__':
    main()
