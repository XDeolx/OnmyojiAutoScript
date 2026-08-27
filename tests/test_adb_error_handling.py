import unittest
from unittest.mock import patch

from adbutils.errors import AdbError

from module.device.method.utils import handle_adb_error


class AdbErrorHandlingTest(unittest.TestCase):
    def test_empty_adb_error_is_retryable(self):
        with patch('module.device.method.utils.logger.warning') as warning:
            self.assertTrue(handle_adb_error(AdbError('')))

        warning.assert_called_once_with(
            'ADB returned an empty error response, reconnect and retry'
        )

    def test_unknown_adb_error_still_requires_manual_check(self):
        with patch('module.device.method.utils.logger.exception'), \
                patch('module.device.method.utils.possible_reasons'):
            self.assertFalse(handle_adb_error(AdbError('permission denied')))


if __name__ == '__main__':
    unittest.main()
