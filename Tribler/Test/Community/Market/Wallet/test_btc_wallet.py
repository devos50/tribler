from twisted.internet.defer import inlineCallbacks, succeed

from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.twisted_thread import deferred
from Tribler.community.market.wallet.btc_wallet import BitcoinWallet
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestBtcWallet(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestBtcWallet, self).setUp(annotate=annotate)

    @deferred(timeout=20)
    def test_btc_wallet(self):
        """
        Test the creating, opening, transactions and balance query of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)

        def on_wallet_transactions(transactions):
            self.assertFalse(transactions)

        def on_wallet_balance(balance):
            self.assertDictEqual(balance, {'available': 0, 'pending': 0, 'currency': 'BTC'})
            return wallet.get_transactions().addCallback(on_wallet_transactions)

        def on_wallet_created(_):
            self.assertIsNotNone(wallet.wallet)
            self.assertTrue(wallet.get_address())
            return wallet.get_balance().addCallback(on_wallet_balance)

        return wallet.create_wallet(None).addCallback(on_wallet_created)

    def test_btc_wallet_name(self):
        """
        Test the name of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)
        self.assertEqual(wallet.get_name(), 'Bitcoin')

    def test_btc_wallet_identfier(self):
        """
        Test the identifier of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)
        self.assertEqual(wallet.get_identifier(), 'BTC')

    def test_btc_wallet_address(self):
        """
        Test the address of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)
        self.assertEqual(wallet.get_address(), '')

    def test_btc_wallet_unit(self):
        """
        Test the mininum unit of a Bitcoin wallet
        """
        wallet = BitcoinWallet(self.session_base_dir)
        self.assertEqual(wallet.min_unit(), 0.00000001)

    def test_btc_balance_no_wallet(self):
        """
        Test the retrieval of the balance of a BTC wallet that is not created yet
        """
        def on_wallet_balance(balance):
            self.assertDictEqual(balance, {'available': 0, 'pending': 0, 'currency': 'BTC'})

        wallet = BitcoinWallet(self.session_base_dir)
        return wallet.get_balance().addCallback(on_wallet_balance)
