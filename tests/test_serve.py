# SPDX-License-Identifier: MIT
import argparse
import errno
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, sentinel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from serve import DEFAULT_PORT, create_server, port_number


class LocalServerTests(unittest.TestCase):
    @patch("serve.ThreadingHTTPServer")
    def test_busy_default_asks_os_for_free_port(self, factory):
        factory.side_effect = [OSError(errno.EADDRINUSE, "busy"), sentinel.server]
        self.assertIs(create_server(Path("dist")), sentinel.server)
        self.assertEqual(factory.call_args_list[0].args[0], ("127.0.0.1", DEFAULT_PORT))
        self.assertEqual(factory.call_args_list[1].args[0], ("127.0.0.1", 0))

    @patch("serve.ThreadingHTTPServer")
    def test_explicit_port_is_not_silently_changed(self, factory):
        factory.side_effect = OSError(errno.EADDRINUSE, "busy")
        with self.assertRaises(OSError):
            create_server(Path("dist"), 9001)
        factory.assert_called_once()
        self.assertEqual(factory.call_args.args[0], ("127.0.0.1", 9001))

    @patch("serve.ThreadingHTTPServer")
    def test_unrelated_bind_error_is_not_hidden(self, factory):
        factory.side_effect = OSError(errno.EACCES, "permission denied")
        with self.assertRaises(OSError):
            create_server(Path("dist"))
        factory.assert_called_once()

    def test_port_range(self):
        self.assertEqual(port_number("0"), 0)
        self.assertEqual(port_number("65535"), 65535)
        for invalid in ("-1", "65536", "abc"):
            with self.assertRaises(argparse.ArgumentTypeError):
                port_number(invalid)


if __name__ == "__main__":
    unittest.main()
