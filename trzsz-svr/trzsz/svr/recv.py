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

import sys
import time
import argparse
from trzsz.libs.utils import *
from trzsz.svr.__version__ import __version__

def main():
    parser = argparse.ArgumentParser(description='Receive file(s), similar to rz and compatible with tmux.',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) py ' + __version__)
    parser.add_argument('-q', '--quiet', action='store_true', help='quiet (hide progress bar)')
    parser.add_argument('-y', '--overwrite', action='store_true', help='yes, overwrite existing file(s)')
    parser.add_argument('-b', '--binary', action='store_true', help='binary transfer mode, faster for binary files')
    parser.add_argument('-e', '--escape', action='store_true', help='escape all known control characters')
    parser.add_argument('-B',
                        '--bufsize',
                        min_size='1K',
                        max_size='1G',
                        default='10M',
                        action=BufferSizeParser,
                        metavar='N',
                        help='max buffer chunk size (1K<=N<=1G). (default: 10M)')
    parser.add_argument('-t',
                        '--timeout',
                        type=int,
                        default=100,
                        metavar='N',
                        help='timeout ( N seconds ) for each buffer chunk.\nN <= 0 means never timeout. (default: 100)')
    parser.add_argument('path', nargs='?', default='.', help='path to save file(s). (default: current directory)')
    args = parser.parse_args()
    dest_path = convert_to_unicode(os.path.abspath(args.path))

    try:
        check_path_writable(dest_path)
    except TrzszError as e:
        sys.stderr.write(str(e) + '\n')
        return

    tmux_mode = check_tmux()
    if args.binary and tmux_mode != NO_TMUX:
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
    if args.binary and is_windows:
        sys.stdout.write('Binary upload on Windows is not supported, auto switch to base64 mode.\n')
        args.binary = False

    unique_id = '0'
    if tmux_mode == TMUX_NORMAL_MODE:
        sys.stdout.write('\n\n\x1b[2A\x1b[0J' if 0 < get_columns() < 40 else '\n\x1b[1A\x1b[0J')
        unique_id = str(int(time.time() * 1000))[::-1]
    if is_windows:
        unique_id = '1'
    sys.stdout.write('\x1b7\x07::TRZSZ:TRANSFER:R:%s:%s\n' % (__version__, unique_id))
    sys.stdout.flush()

    try:
        set_stdin_raw()
        reconfigure_stdin()

        action = recv_action()

        if not action.get('confirm', False):
            server_exit('Cancelled')
            return

        # check if the client doesn't support binary mode
        if args.binary and action.get('binary') is False:
            args.binary = False

        send_config(args, get_escape_chars(args.escape))

        local_list = recv_files(dest_path, None)

        _ = recv_exit()
        server_exit('Received %s to %s' % (', '.join(local_list), dest_path))

    except Exception as e:
        server_error(e)

if __name__ == '__main__':
    main()
