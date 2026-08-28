import unittest
from unittest.mock import Mock, patch

from module.device.method.minitouch import retry
from module.device.method.nemu_ipc import CaptureStd


class DeviceConnectionStabilityTest(unittest.TestCase):
    def test_minitouch_rebuilds_control_socket_before_adb_reconnect(self):
        class Device:
            def __init__(self):
                self._minitouch_client = Mock()
                self.minitouch_builder = object()
                self.calls = 0
                self.adb_reconnect = Mock()

            @retry
            def send(self):
                self.calls += 1
                if self.calls == 1:
                    raise ConnectionResetError('stale socket')
                return 'ok'

        device = Device()
        with patch('module.device.method.minitouch.retry_sleep'):
            self.assertEqual(device.send(), 'ok')

        device._minitouch_client.close.assert_called_once_with()
        device.adb_reconnect.assert_not_called()
        self.assertNotIn('minitouch_builder', device.__dict__)

    def test_minitouch_escalates_after_second_control_socket_failure(self):
        class Device:
            def __init__(self):
                self._minitouch_client = Mock()
                self.minitouch_builder = object()
                self.calls = 0
                self.adb_reconnect = Mock()

            @retry
            def send(self):
                self.calls += 1
                if self.calls < 3:
                    raise ConnectionAbortedError('closed socket')
                return 'ok'

        device = Device()
        with patch('module.device.method.minitouch.retry_sleep'):
            self.assertEqual(device.send(), 'ok')

        self.assertEqual(device._minitouch_client.close.call_count, 2)
        device.adb_reconnect.assert_called_once_with()

    def test_capture_std_allows_background_process_without_streams(self):
        capture = CaptureStd()
        with patch.object(CaptureStd, '_stream_fileno', return_value=None):
            with capture:
                pass

        self.assertFalse(capture._capture_enabled)
        self.assertEqual(capture.stdout, b'')
        self.assertEqual(capture.stderr, b'')


if __name__ == '__main__':
    unittest.main()
