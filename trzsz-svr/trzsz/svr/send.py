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
import tty
import time
import termios
import argparse
from trzsz.libs.utils import *
from trzsz.svr.__version__ import __version__

def main():
    parser = argparse.ArgumentParser(description='Send file(s), similar to sz but compatible with tmux.',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) ' + __version__)
    parser.add_argument('-q', '--quiet', action='store_true', help='quiet (hide progress bar)')
    parser.add_argument('-y', '--overwrite', action='store_true', help='yes, overwrite existing file(s)')
    parser.add_argument('-b', '--binary', action='store_true', help='binary transfer mode, faster for binary files')
    parser.add_argument('-e', '--escape', action='store_true', help='escape all known control characters')
    parser.add_argument('-B', '--bufsize', min_size='1K', max_size='100M', default='1M', action=BufferSizeParser,
                        metavar='N', help='buffer chunk size ( 1K <= N <= 100M ). (default: 1M)')
    parser.add_argument('-t', '--timeout', type=int, default=100, metavar='N',
                        help='timeout ( N seconds ) for each buffer chunk.\nN <= 0 means never timeout. (default: 100)')
    parser.add_argument('file', nargs='+', type=convert_to_unicode, help='file(s) to be sent')
    args = parser.parse_args()
    file_list = args.file

    try:
        check_files_readable(file_list)
    except TrzszError as e:
        sys.stderr.write(str(e) + '\n')
        return

    tmux_mode = check_tmux()
    if tmux_mode == TMUX_CONTROL_MODE and args.binary:
        '''
        1. In tmux control mode, tmux will convert some invisible characters to Octal text.
           E.g., tmux will convert ascii '\0' to text "\000", which from 1 byte to 4 bytes.
        2. Got some junk data from stdin in tmux control mode, e.g. '[?1;2c', don't know why.
        '''
        sys.stdout.write('Binary download in tmux control mode is slower, auto switch to base64 mode.\n')
        args.binary = False
    if tmux_mode == TMUX_NORMAL_MODE:
        sys.stdout.write('\n\n\x1b[2A\x1b[0J' if 0 < get_columns() < 40 else '\n\x1b[1A\x1b[0J')

    unique_id = str(int(time.time() * 1000) if tmux_mode == TMUX_NORMAL_MODE else 0)[::-1]
    sys.stdout.write('\x1b7\x07::TRZSZ:TRANSFER:S:%s:%s\n' % (__version__, unique_id))
    sys.stdout.flush()

    try:
        reconfigure_stdin()
        tty.setraw(sys.stdin.fileno(), termios.TCSADRAIN)

        action = recv_action()

        if not action.get('confirm', False):
            delay_exit(False, 'Cancelled')

        escape_chars = []

        send_config(args, escape_chars)

        send_files(file_list, None, args.binary, escape_chars, args.bufsize)

        check_exit()

    except Exception as e:
        fail_exit(e, True)

if __name__ == '__main__':
    main()
