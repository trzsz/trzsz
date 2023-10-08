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
import platform
import unittest
from .trzsz.libs import utils
from .trzsz.libs import transfer


class TestTransferAction(unittest.TestCase):

    def setUp(self):
        utils.IS_RUNNING_ON_WINDOWS = False  # test as on Linux

    def tearDown(self):
        utils.IS_RUNNING_ON_WINDOWS = platform.system() == 'Windows'
        utils.CONFIG = utils.TransferConfig()
        utils.GLOBAL = utils.GlobalVariables()

    def test_action_compatible(self):
        utils.GLOBAL.next_read_buffer = b'#ACT:eJw0ykEKwkAMQNG7/HUojMucRZBaxxIYkyGdKiLe3YV0+3gf' + \
            b'2uwryhoIz5qbhaOUqUwFYQm/Wz7QkXsVvL6aeUU5O0LPGLFEQ0/C1XzO9zG3vffIcblZ/un7CwAA//8fnSN6\n'
        action = transfer.recv_action()
        self.assertEqual(
            {
                'binary': True,
                'confirm': True,
                'lang': 'go',
                'newline': '\n',
                'protocol': 2,
                'support_dir': True,
                'version': '1.1.1'
            }, action)
        self.assertFalse(utils.GLOBAL.windows_protocol)
        self.assertEqual('\n', utils.CONFIG.newline)

    def test_linux_2_linux(self):
        utils.IS_RUNNING_ON_WINDOWS = False
        stdout = io.StringIO()
        utils.GLOBAL.trzsz_writer = stdout
        transfer.send_action(True, '1.0.0', False)
        self.assertIn('#ACT:', stdout.getvalue())
        self.assertFalse(utils.GLOBAL.windows_protocol)
        self.assertEqual('\n', utils.CONFIG.newline)

        utils.IS_RUNNING_ON_WINDOWS = False
        utils.GLOBAL.next_read_buffer = stdout.getvalue().encode('utf8')
        action = transfer.recv_action()
        self.assertEqual('\n', action.get('newline', '\n'))
        self.assertTrue(action.get('binary', True))
        self.assertFalse(utils.GLOBAL.windows_protocol)
        self.assertEqual('\n', utils.CONFIG.newline)
        self.assertEqual(1, action.get('protocol', 0))

    def test_windows_2_linux(self):
        utils.IS_RUNNING_ON_WINDOWS = True
        stdout = io.StringIO()
        utils.GLOBAL.trzsz_writer = stdout
        transfer.send_action(True, '1.0.0', False)
        self.assertIn('#ACT:', stdout.getvalue())
        self.assertFalse(utils.GLOBAL.windows_protocol)
        self.assertEqual('\n', utils.CONFIG.newline)

        utils.IS_RUNNING_ON_WINDOWS = False
        utils.GLOBAL.next_read_buffer = stdout.getvalue().encode('utf8')
        action = transfer.recv_action()
        self.assertEqual('!\n', action.get('newline', '\n'))
        self.assertFalse(action.get('binary', True))
        self.assertFalse(utils.GLOBAL.windows_protocol)
        self.assertEqual('!\n', utils.CONFIG.newline)
        self.assertEqual(1, action.get('protocol', 0))

    def test_linux_2_windows(self):
        utils.IS_RUNNING_ON_WINDOWS = False
        stdout = io.StringIO()
        utils.GLOBAL.trzsz_writer = stdout
        transfer.send_action(True, '1.0.0', True)
        self.assertIn('#ACT:', stdout.getvalue())
        self.assertTrue(utils.GLOBAL.windows_protocol)
        self.assertEqual('!\n', utils.CONFIG.newline)

        utils.IS_RUNNING_ON_WINDOWS = True
        utils.GLOBAL.next_read_buffer = stdout.getvalue().encode('utf8')
        action = transfer.recv_action()
        self.assertEqual('!\n', action.get('newline', '\n'))
        self.assertFalse(action.get('binary', True))
        self.assertTrue(utils.IS_RUNNING_ON_WINDOWS or utils.GLOBAL.windows_protocol)
        self.assertEqual('!\n', utils.CONFIG.newline)
        self.assertEqual(1, action.get('protocol', 0))

    def test_windows_2_windows(self):
        utils.IS_RUNNING_ON_WINDOWS = True
        stdout = io.StringIO()
        utils.GLOBAL.trzsz_writer = stdout
        transfer.send_action(True, '1.0.0', True)
        self.assertIn('#ACT:', stdout.getvalue())
        self.assertTrue(utils.GLOBAL.windows_protocol)
        self.assertEqual('!\n', utils.CONFIG.newline)

        utils.IS_RUNNING_ON_WINDOWS = True
        utils.GLOBAL.next_read_buffer = stdout.getvalue().encode('utf8')
        action = transfer.recv_action()
        self.assertEqual('!\n', action.get('newline', '\n'))
        self.assertFalse(action.get('binary', True))
        self.assertTrue(utils.IS_RUNNING_ON_WINDOWS or utils.GLOBAL.windows_protocol)
        self.assertEqual('!\n', utils.CONFIG.newline)
        self.assertEqual(1, action.get('protocol', 0))


if __name__ == '__main__':
    unittest.main()
