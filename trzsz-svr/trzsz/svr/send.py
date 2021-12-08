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
    check_exit(False)

def main():
    parser = ArgumentParser(description='Send file(s), similar to sz but compatible with tmux (control mode).')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s (trzsz) ' + __version__)
    parser.add_argument('file', nargs='+', help='File(s) to be sent.')
    args = parser.parse_args()
    file_list = args.file

    try:
        check_files(file_list)
    except FileError as e:
        sys.stderr.write(str(e) + '\n')
        return

    sys.stdout.write('\x07::TRZSZ:TRANSFER:S:%s\n' % __version__)
    sys.stdout.flush()

    tty.setraw(sys.stdin.fileno(), termios.TCSADRAIN)

    try:
        cmd = recv_check('CMD')
    except RecvError as e:
        handle_error(str(e))

    if cmd == 'CANCELLED':
        delay_exit(False, 'Cancelled')

    if not cmd.startswith('CONFIRMED#'):
        handle_error('Unknown command: %s' % cmd)

    try:
        send_files(file_list)
    except Exception as e:
        handle_error(str(e))

    check_exit(True)

if __name__ == '__main__':
    main()
