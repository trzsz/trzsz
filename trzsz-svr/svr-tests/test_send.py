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

import io
import sys
import unittest
import contextlib
from .trzsz.svr import send


class TestRecv(unittest.TestCase):

    def setUp(self):
        pass

    # pylint: disable-next=too-many-arguments
    def assert_args_equal(self,
                          args,
                          file,
                          quiet=False,
                          overwrite=False,
                          binary=False,
                          escape=False,
                          directory=False,
                          bufsize=10 * 1024 * 1024,
                          timeout=20):
        args = send.parse_args(args)
        self.assertEqual(quiet, args.quiet)
        self.assertEqual(overwrite, args.overwrite)
        self.assertEqual(binary, args.binary)
        self.assertEqual(escape, args.escape)
        self.assertEqual(directory, args.directory)
        self.assertEqual(bufsize, args.bufsize)
        self.assertEqual(timeout, args.timeout)
        self.assertEqual(file, args.file)

    def assert_args_raises(self, args, err_msg):
        if sys.version_info >= (3, 4):
            stderr = io.StringIO()
            with self.assertRaises(SystemExit) as context, contextlib.redirect_stderr(stderr):
                send.parse_args(args)
            self.assertEqual(context.exception.code, 2)
            self.assertIn(err_msg, stderr.getvalue())
        else:
            with self.assertRaises(SystemExit) as context:
                send.parse_args(args)
            self.assertEqual(context.exception.code, 2)

    def test_short_arg(self):
        self.assert_args_equal(['a'], ['a'])
        self.assert_args_equal(['-q', 'a'], ['a'], quiet=True)
        self.assert_args_equal(['-y', 'a'], ['a'], overwrite=True)
        self.assert_args_equal(['-b', 'a'], ['a'], binary=True)
        self.assert_args_equal(['-e', 'a'], ['a'], escape=True)
        self.assert_args_equal(['-d', 'a'], ['a'], directory=True)
        self.assert_args_equal(['-r', 'a'], ['a'], directory=True)
        self.assert_args_equal(['-B', '2k', 'a'], ['a'], bufsize=2 * 1024)
        self.assert_args_equal(['-t', '3', 'a'], ['a'], timeout=3)

    def test_long_arg(self):
        self.assert_args_equal(['a'], ['a'])
        self.assert_args_equal(['--quiet', 'a'], ['a'], quiet=True)
        self.assert_args_equal(['--overwrite', 'a'], ['a'], overwrite=True)
        self.assert_args_equal(['--binary', 'a'], ['a'], binary=True)
        self.assert_args_equal(['--escape', 'a'], ['a'], escape=True)
        self.assert_args_equal(['--directory', 'a'], ['a'], directory=True)
        self.assert_args_equal(['--recursive', 'a'], ['a'], directory=True)
        self.assert_args_equal(['--bufsize', '2M', 'a'], ['a'], bufsize=2 * 1024 * 1024)
        self.assert_args_equal(['--timeout', '55', 'a'], ['a'], timeout=55)

    def test_buffer_size(self):
        self.assert_args_equal(['-B1024', 'a'], ['a'], bufsize=1024)
        self.assert_args_equal(['-B1025b', 'a'], ['a'], bufsize=1025)
        self.assert_args_equal(['-B', '1026B', 'a'], ['a'], bufsize=1026)
        self.assert_args_equal(['-B', '1MB', 'a'], ['a'], bufsize=1024 * 1024)
        self.assert_args_equal(['-B', '2m', 'a'], ['a'], bufsize=2 * 1024 * 1024)
        self.assert_args_equal(['-B1G', 'a'], ['a'], bufsize=1024 * 1024 * 1024)
        self.assert_args_equal(['-B', '1gb', 'a'], ['a'], bufsize=1024 * 1024 * 1024)

    def test_combined_args(self):
        self.assert_args_equal(['-yq', 'a'], ['a'], quiet=True, overwrite=True)
        self.assert_args_equal(['-bed', 'a'], ['a'], binary=True, escape=True, directory=True)
        self.assert_args_equal(['-yrB', '2096', 'a'], ['a'], overwrite=True, directory=True, bufsize=2096)
        self.assert_args_equal(['-ebt300', 'a'], ['a'], escape=True, binary=True, timeout=300)
        self.assert_args_equal(['-yqB3K', '-eb', '-t', '9', '-d', 'a'], ['a'],
                               quiet=True,
                               overwrite=True,
                               bufsize=3 * 1024,
                               escape=True,
                               binary=True,
                               timeout=9,
                               directory=True)

    def test_send_file_args(self):
        self.assert_args_equal(['/tmp/b'], ['/tmp/b'])
        self.assert_args_equal(['-y', '-d', 'a', 'b', 'c'], ['a', 'b', 'c'], overwrite=True, directory=True)
        self.assert_args_equal(['-eqt60', './bb', '../xx'], ['./bb', '../xx'], escape=True, quiet=True, timeout=60)

    def test_invalid_args(self):
        self.assert_args_raises(['-B', '2gb', 'a'], 'greater than 1G')
        self.assert_args_raises(['-B10', 'a'], 'less than 1K')
        self.assert_args_raises(['-B10x', 'a'], 'invalid size 10x')
        self.assert_args_raises(['-Bb', 'a'], 'invalid size b')
        self.assert_args_raises(['-tiii', 'a'], 'iii')
        self.assert_args_raises(['-t --directory', 'a'], 'invalid int value')
        self.assert_args_raises(['-x', 'a'], 'unrecognized arguments: -x')
        self.assert_args_raises(['--kkk', 'a'], 'unrecognized arguments: --kkk')
        self.assert_args_raises(['-y'], 'the following arguments are required: file')
        self.assert_args_raises(['-q', '-B', '2k', '-et3'], 'the following arguments are required: file')


if __name__ == '__main__':
    unittest.main()
