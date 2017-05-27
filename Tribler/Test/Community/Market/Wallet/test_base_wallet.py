from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.wallet.wallet import Wallet


class TestBaseWallet(AbstractServer):

    def test_generate_txid(self):
        """
        Test the generation of a transaction id
        """
        txid = Wallet().generate_txid(length=20)
        self.assertIsInstance(txid, str)
        self.assertEqual(len(txid), 20)

    def test_not_implemented_wallet(self):
        """
        Test the methods of a base wallet
        """
        self.assertRaises(NotImplementedError, Wallet().get_identifier)
        self.assertRaises(NotImplementedError, Wallet().get_name)
        self.assertRaises(NotImplementedError, Wallet().create_wallet)
        self.assertRaises(NotImplementedError, Wallet().get_balance)
        self.assertRaises(NotImplementedError, Wallet().transfer)
        self.assertRaises(NotImplementedError, Wallet().get_address)
        self.assertRaises(NotImplementedError, Wallet().get_transactions)
        self.assertRaises(NotImplementedError, Wallet().min_unit)
