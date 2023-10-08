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
import json
import platform
import unittest
from .trzsz.libs import utils
from .trzsz.libs import transfer


class TestArgs():

    def __init__(self):
        self.quiet = True
        self.binary = True
        self.overwrite = True
        self.directory = True
        self.bufsize = 1024
        self.timeout = 10


class TestTransferConfig(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None  # pylint: disable=invalid-name
        utils.IS_RUNNING_ON_WINDOWS = False  # test as on Linux
        self.protocol_version = utils.PROTOCOL_VERSION

    def tearDown(self):
        utils.IS_RUNNING_ON_WINDOWS = platform.system() == 'Windows'
        utils.PROTOCOL_VERSION = self.protocol_version
        utils.CONFIG = utils.TransferConfig()
        utils.GLOBAL = utils.GlobalVariables()

    def test_transfer_config(self):
        stdout = io.StringIO()
        utils.GLOBAL.trzsz_writer = stdout
        args = TestArgs()
        action = {'protocol': 2}
        escape_chars = utils.get_escape_chars(True)
        if sys.version_info < (3, ):
            escape_chars = json.loads(json.dumps(escape_chars, encoding='latin1'), encoding='latin1')
        utils.PROTOCOL_VERSION = 2
        utils.CONFIG.tmux_pane_width = 88
        utils.GLOBAL.tmux_mode = utils.TMUX_NORMAL_MODE
        transfer.send_config(args, action, escape_chars)
        self.assertIn('#CFG:', stdout.getvalue())
        config = {
            'quiet': True,
            'binary': True,
            'directory': True,
            'overwrite': True,
            'timeout': 10,
            'newline': '\n',
            'protocol': 2,
            'max_buf_size': 1024,
            'escape_chars': escape_chars,
            'tmux_pane_width': 88,
            'tmux_output_junk': True,
        }
        self.assertEqual(config, utils.CONFIG.__dict__)

        def assert_config_equal(cfg_str):
            utils.GLOBAL.next_read_buffer = cfg_str.encode('utf8')
            self.assertEqual(config, transfer.recv_config().__dict__)
            self.assertEqual(config, utils.CONFIG.__dict__)
        cfg_str = '#CFG:eJxN0ctOwzAQBdBfibzuwgldhO54teXRLwhR5CQDdR+xccaUtoJvZ0KDZna+R1f2yHNWO9O9q1mi/FFNElXbzoQj' + \
            'ZQwRKPvg0DVuR5JRxH38qlxEH7HaxG7LxY9oATlC3xgPVbM2oSctCvUatQYY3ricxlxOkkL9MKcXGYLOmG9GDky33Ew1853glPl' + \
            'e8BXzg+CceS64Zl4IbpmXzLngR+ZrMeCTYDHgs2Ax4ItgcfdKleX/PrzpoDrYFtf003k+sN0DbYliqim2NkCDTu61jm+9PcFfI5' + \
            'sSuE8Ih2ARxs73L+eXlsk=\n'
        assert_config_equal(cfg_str)
        assert_config_equal(stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
