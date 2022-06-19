# MIT License
#
# Copyright (c) 2022 Lonny Wong
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

import re
import unittest
import unittest.mock
from .trzsz.iterm2.text_progress import *

class GridSize():
    def __init__(self, width):
        self.width = width

class Session():
    def __init__(self, width):
        self.grid_size = GridSize(width)

def output_length(s):
    return display_length(re.sub(r'(\u2588|\u2591)', '*', re.sub(r'\u001b\[\d+[mD]', '', re.sub(r'\r', '', s))))

class TestTextProgressBar(unittest.TestCase):

    def setUp(self):
        self.loop = {}
        self.session = Session(100)
        self.tgb = TextProgressBar(self.loop, self.session)
        self.mock_inject = unittest.mock.Mock()
        # pylint: disable=protected-access
        self.tgb._inject_to_iterm2 = self.mock_inject

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564135])
    def test_empty_file(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀test.txt')
        self.tgb.on_size(0)
        self.tgb.on_step(0)
        self.assertEqual(mock_time.call_count, 2)
        self.mock_inject.assert_not_called()

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564135])
    def test_nan_speed(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀test.txt')
        self.tgb.on_size(100)
        self.tgb.on_step(0)
        self.assertEqual(mock_time.call_count, 2)
        self.mock_inject.assert_called_once()
        self.assertIn('中文😀test.txt [', self.mock_inject.call_args[0][0])
        self.assertIn('] 0% | 0.00B | NaN/s | NaN ETA', self.mock_inject.call_args[0][0])
        self.assertEqual(output_length(self.mock_inject.call_args[0][0]), 100)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564135.001, 1646564135.099])
    def test_output_once_only(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀test.txt')
        self.tgb.on_size(100)
        self.tgb.on_step(1)
        self.tgb.on_step(2)
        self.assertEqual(mock_time.call_count, 3)
        self.mock_inject.assert_called_once()
        self.assertIn('中文😀test.txt [', self.mock_inject.call_args[0][0])
        self.assertIn('] 1% | 1.00B | 1000B/s | 00:00 ETA', self.mock_inject.call_args[0][0])
        self.assertEqual(output_length(self.mock_inject.call_args[0][0]), 100)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136])
    def test_super_fast(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀test.txt')
        self.tgb.on_size(1024 * 1024 * 1024 * 1024 * 1024)
        self.tgb.on_step(10.1 * 1024 * 1024 * 1024 * 1024)
        self.assertEqual(mock_time.call_count, 2)
        self.mock_inject.assert_called_once()
        self.assertIn('中文😀test.txt [', self.mock_inject.call_args[0][0])
        self.assertIn('] 1% | 10.1TB | 10.1TB/s | 01:40 ETA', self.mock_inject.call_args[0][0])
        self.assertEqual(output_length(self.mock_inject.call_args[0][0]), 100)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136])
    def test_very_slow(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀test.txt')
        self.tgb.on_size(1024 * 1024)
        self.tgb.on_step(1)
        self.assertEqual(mock_time.call_count, 2)
        self.mock_inject.assert_called_once()
        self.assertIn('中文😀test.txt [', self.mock_inject.call_args[0][0])
        self.assertIn('] 0% | 1.00B | 1.00B/s | 291:16:15 ETA', self.mock_inject.call_args[0][0])
        self.assertEqual(output_length(self.mock_inject.call_args[0][0]), 100)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136, 1646564138])
    def test_long_name(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀非常长非常长非常长非常长非常长非常长非常长非常长.txt')
        self.tgb.on_size(1000 * 1024)
        self.tgb.columns = 110
        self.tgb.on_step(100 * 1024)
        self.tgb.columns = 100
        self.tgb.on_step(200 * 1024)
        self.assertEqual(mock_time.call_count, 3)
        self.assertEqual(self.mock_inject.call_count, 2)
        self.assertIn('中文😀非常长非常长非常长非常长非常长非常长非常... [', self.mock_inject.call_args_list[0].args[0])
        self.assertIn('] 10% | 100KB | 100KB/s | 00:09 ETA', self.mock_inject.call_args_list[0].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[0].args[0]), 110)
        self.assertIn('中文😀非常长非常长非常长非常长非常长... [', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('] 20% | 200KB | 66.7KB/s | 00:12 ETA', self.mock_inject.call_args_list[1].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[1].args[0]), 100)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136, 1646564138])
    def test_no_total(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀非常长非常长非常长非常长非常长非常长非常长非常长.txt')
        self.tgb.on_size(1000 * 1024 * 1024 * 1024)
        self.tgb.columns = 90
        self.tgb.on_step(100 * 1024 * 1024)
        self.tgb.columns = 80
        self.tgb.on_step(200 * 1024 * 1024 * 1024)
        self.assertEqual(mock_time.call_count, 3)
        self.assertEqual(self.mock_inject.call_count, 2)
        self.assertIn('中文😀非常长非常长非常长非常长非常长... [', self.mock_inject.call_args_list[0].args[0])
        self.assertIn('] 0% | 100MB/s | 2:50:39 ETA', self.mock_inject.call_args_list[0].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[0].args[0]), 90)
        self.assertIn('中文😀非常长非常长非常长非... [', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('] 20% | 66.7GB/s | 00:12 ETA', self.mock_inject.call_args_list[1].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[1].args[0]), 80)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136, 1646564138])
    def test_no_speed(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀longlonglonglonglonglongname.txt')
        self.tgb.on_size(1000)
        self.tgb.columns = 70
        self.tgb.on_step(100)
        self.tgb.columns = 60
        self.tgb.on_step(200)
        self.assertEqual(mock_time.call_count, 3)
        self.assertEqual(self.mock_inject.call_count, 2)
        self.assertIn('中文😀longlonglonglonglongl... [', self.mock_inject.call_args_list[0].args[0])
        self.assertIn('] 10% | 00:09 ETA', self.mock_inject.call_args_list[0].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[0].args[0]), 70)
        self.assertIn('中文😀longlonglonglonglongl... [', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('] 20%', self.mock_inject.call_args_list[1].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[1].args[0]), 60)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136, 1646564138])
    def test_no_name(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀llong文件名.txt')
        self.tgb.on_size(1000)
        self.tgb.columns = 48
        self.tgb.on_step(100)
        self.tgb.columns = 30
        self.tgb.on_step(200)
        self.assertEqual(mock_time.call_count, 3)
        self.assertEqual(self.mock_inject.call_count, 2)
        self.assertIn('中文😀llong文件名... [', self.mock_inject.call_args_list[0].args[0])
        self.assertIn('] 10%', self.mock_inject.call_args_list[0].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[0].args[0]), 48)
        self.assertNotIn('中文', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('] 20%', self.mock_inject.call_args_list[1].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[1].args[0]), 30)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136])
    def test_no_bar(self, mock_time):
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀test.txt')
        self.tgb.on_size(1000)
        self.tgb.columns = 10
        self.tgb.on_step(300)
        self.assertEqual(mock_time.call_count, 2)
        self.assertEqual(self.mock_inject.call_count, 1)
        self.assertEqual('30%', self.mock_inject.call_args_list[0].args[0])

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136, 1646564137, 1646564139])
    def test_multiple_files(self, mock_time):
        self.tgb.on_num(2)
        self.tgb.on_name('中文😀test.txt')
        self.tgb.on_size(1000)
        self.tgb.on_step(100)
        self.tgb.on_done()
        self.tgb.on_name('英文😀test.txt')
        self.tgb.on_size(2000)
        self.tgb.on_step(300)
        self.tgb.on_done()
        self.assertEqual(mock_time.call_count, 4)
        self.assertEqual(self.mock_inject.call_count, 2)
        self.assertNotIn('\r', self.mock_inject.call_args_list[0].args[0])
        self.assertIn('(1/2) 中文😀test.txt [', self.mock_inject.call_args_list[0].args[0])
        self.assertIn('] 10% | 100B | 100B/s | 00:09 ETA', self.mock_inject.call_args_list[0].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[0].args[0]), 100)
        self.assertIn('\r', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('(2/2) 英文😀test.txt [', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('] 15% | 300B | 150B/s | 00:11 ETA', self.mock_inject.call_args_list[1].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[1].args[0]), 100)

    @unittest.mock.patch('time.time', side_effect=[1646564135, 1646564136, 1646564137, 1646564138])
    def test_tmux_pane(self, mock_time):
        self.tgb = TextProgressBar(self.loop, self.session, 80)
        # pylint: disable=protected-access
        self.tgb._inject_to_iterm2 = self.mock_inject
        self.tgb.on_num(1)
        self.tgb.on_name('中文😀test.txt')
        self.tgb.on_size(1000)
        self.tgb.on_step(100)
        self.tgb.on_step(200)
        self.tgb.on_step(300)

        self.assertEqual(mock_time.call_count, 4)
        self.assertEqual(self.mock_inject.call_count, 3)
        self.assertNotIn('\r', self.mock_inject.call_args_list[0].args[0])
        self.assertNotIn('\x1b[80D', self.mock_inject.call_args_list[0].args[0])
        self.assertIn('中文😀test.txt [', self.mock_inject.call_args_list[0].args[0])
        self.assertIn('] 10% | 100B | 100B/s | 00:09 ETA', self.mock_inject.call_args_list[0].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[0].args[0]), 80)

        self.assertNotIn('\r', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('\x1b[80D', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('中文😀test.txt [', self.mock_inject.call_args_list[1].args[0])
        self.assertIn('] 20% | 200B | 100B/s | 00:08 ETA', self.mock_inject.call_args_list[1].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[1].args[0]), 80)

        self.assertNotIn('\r', self.mock_inject.call_args_list[2].args[0])
        self.assertIn('\x1b[80D', self.mock_inject.call_args_list[2].args[0])
        self.assertIn('中文😀test.txt [', self.mock_inject.call_args_list[2].args[0])
        self.assertIn('] 30% | 300B | 100B/s | 00:07 ETA', self.mock_inject.call_args_list[2].args[0])
        self.assertEqual(output_length(self.mock_inject.call_args_list[2].args[0]), 80)

if __name__ == '__main__':
    unittest.main()
