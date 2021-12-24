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
import termios
from argparse import ArgumentParser
from trzsz.libs.utils import *
from trzsz.svr.__version__ import __version__

def handle_error(msg):
    send_fail(msg)
    delay_exit(False, msg)

def main():
    parser = ArgumentParser(description='Receive file(s), similar to rz but compatible with tmux.')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) ' + __version__)
    parser.add_argument('-q', '--quiet', action='store_true', help='quiet (hide progress bar)')
    parser.add_argument('-y', '--overwrite', action='store_true', help='overwrite existing file(s)')
    parser.add_argument('path', nargs='?', default='.', help='path to save file(s). (default: current directory)')
    args = parser.parse_args()
    dest_path = args.path

    try:
        check_path(dest_path)
    except Exception as e:
        sys.stderr.write(str(e) + '\n')
        return

    check_tmux()

    sys.stdout.write('\x1b7\x07::TRZSZ:TRANSFER:R:%s\n' % __version__)
    sys.stdout.flush()

    try:
        tty.setraw(sys.stdin.fileno(), termios.TCSADRAIN)

        cmd = recv_check('CMD')

        if cmd == 'CANCELLED':
            delay_exit(False, 'Cancelled')

        if not cmd.startswith('CONFIRMED#'):
            handle_error('Unknown command: %s' % cmd)

        send_config(args.quiet, args.overwrite)

        recv_files(dest_path, overwrite=args.overwrite)

    except Exception as e:
        handle_error(str(e))

    check_exit()

if __name__ == '__main__':
    main()
