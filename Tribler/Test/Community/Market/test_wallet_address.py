import unittest

from Tribler.community.market.core.wallet_address import WalletAddress


class WalletAddressTestSuite(unittest.TestCase):
    """Bitcoin address test cases."""

    def setUp(self):
        # Object creation
        self.wallet_address = WalletAddress(b"0")
        self.wallet_address2 = WalletAddress(b"1")

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(b"1", bytes(self.wallet_address2))
