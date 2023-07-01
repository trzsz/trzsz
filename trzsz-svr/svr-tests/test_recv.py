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
from .trzsz.svr import recv


class TestRecv(unittest.TestCase):

    def setUp(self):
        pass

    # pylint: disable-next=too-many-arguments
    def assert_args_equal(self,
                          args,
                          quiet=False,
                          overwrite=False,
                          binary=False,
                          escape=False,
                          directory=False,
                          bufsize=10 * 1024 * 1024,
                          timeout=20,
                          path='.'):
        args = recv.parse_args(args)
        self.assertEqual(quiet, args.quiet)
        self.assertEqual(overwrite, args.overwrite)
        self.assertEqual(binary, args.binary)
        self.assertEqual(escape, args.escape)
        self.assertEqual(directory, args.directory)
        self.assertEqual(bufsize, args.bufsize)
        self.assertEqual(timeout, args.timeout)
        self.assertEqual(path, args.path)

    def assert_args_raises(self, args, err_msg):
        if sys.version_info >= (3, 4):
            stderr = io.StringIO()
            with self.assertRaises(SystemExit) as context, contextlib.redirect_stderr(stderr):
                recv.parse_args(args)
            self.assertEqual(context.exception.code, 2)
            self.assertIn(err_msg, stderr.getvalue())
        else:
            with self.assertRaises(SystemExit) as context:
                recv.parse_args(args)
            self.assertEqual(context.exception.code, 2)

    def test_short_arg(self):
        self.assert_args_equal([])
        self.assert_args_equal(['-q'], quiet=True)
        self.assert_args_equal(['-y'], overwrite=True)
        self.assert_args_equal(['-b'], binary=True)
        self.assert_args_equal(['-e'], escape=True)
        self.assert_args_equal(['-d'], directory=True)
        self.assert_args_equal(['-r'], directory=True)
        self.assert_args_equal(['-B', '2k'], bufsize=2 * 1024)
        self.assert_args_equal(['-t', '3'], timeout=3)

    def test_long_arg(self):
        self.assert_args_equal([])
        self.assert_args_equal(['--quiet'], quiet=True)
        self.assert_args_equal(['--overwrite'], overwrite=True)
        self.assert_args_equal(['--binary'], binary=True)
        self.assert_args_equal(['--escape'], escape=True)
        self.assert_args_equal(['--directory'], directory=True)
        self.assert_args_equal(['--recursive'], directory=True)
        self.assert_args_equal(['--bufsize', '2M'], bufsize=2 * 1024 * 1024)
        self.assert_args_equal(['--timeout', '55'], timeout=55)

    def test_buffer_size(self):
        self.assert_args_equal(['-B1024'], bufsize=1024)
        self.assert_args_equal(['-B1025b'], bufsize=1025)
        self.assert_args_equal(['-B', '1026B'], bufsize=1026)
        self.assert_args_equal(['-B', '1MB'], bufsize=1024 * 1024)
        self.assert_args_equal(['-B', '2m'], bufsize=2 * 1024 * 1024)
        self.assert_args_equal(['-B1G'], bufsize=1024 * 1024 * 1024)
        self.assert_args_equal(['-B', '1gb'], bufsize=1024 * 1024 * 1024)

    def test_combined_args(self):
        self.assert_args_equal(['-yq'], quiet=True, overwrite=True)
        self.assert_args_equal(['-bed'], binary=True, escape=True, directory=True)
        self.assert_args_equal(['-yrB', '2096'], overwrite=True, directory=True, bufsize=2096)
        self.assert_args_equal(['-ebt300'], escape=True, binary=True, timeout=300)
        self.assert_args_equal(['-yqB3K', '-eb', '-t', '9', '-d'],
                               quiet=True,
                               overwrite=True,
                               bufsize=3 * 1024,
                               escape=True,
                               binary=True,
                               timeout=9,
                               directory=True)

    def test_dest_path_args(self):
        self.assert_args_equal(['/tmp'], path='/tmp')
        self.assert_args_equal(['-y', '-d', '../adir'], overwrite=True, directory=True, path='../adir')
        self.assert_args_equal(['-eqt60', './bbb'], escape=True, quiet=True, timeout=60, path='./bbb')

    def test_invalid_args(self):
        self.assert_args_raises(['-B', '2gb'], 'greater than 1G')
        self.assert_args_raises(['-B10'], 'less than 1K')
        self.assert_args_raises(['-B10x'], 'invalid size 10x')
        self.assert_args_raises(['-Bb'], 'invalid size b')
        self.assert_args_raises(['-tiii'], 'iii')
        self.assert_args_raises(['-t --directory'], 'invalid int value')
        self.assert_args_raises(['-x'], 'unrecognized arguments: -x')
        self.assert_args_raises(['--kkk'], 'unrecognized arguments: --kkk')
        self.assert_args_raises(['abc', 'xyz'], 'unrecognized arguments: xyz')
        self.assert_args_raises(['-q', '-B', '2k', '-et3', 'abc', 'xyz'], 'unrecognized arguments: xyz')


if __name__ == '__main__':
    unittest.main()
