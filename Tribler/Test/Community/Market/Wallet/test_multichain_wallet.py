from twisted.internet.defer import inlineCallbacks, Deferred, succeed

from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.test_as_server import AbstractServer
from Tribler.Test.twisted_thread import deferred
from Tribler.community.market.wallet.mc_wallet import MultichainWallet
from Tribler.community.market.wallet.wallet import InsufficientFunds
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMultichainWallet(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestMultichainWallet, self).setUp(annotate=annotate)

        latest_block = MockObject()
        latest_block.total_up = 10
        latest_block.total_down = 5
        latest_block.previous_hash_requester = 'b' * 5

        self.mc_community = MockObject()
        self.mc_community.add_discovered_candidate = lambda _: None
        self.mc_community.create_introduction_request = lambda *_: None
        self.mc_community.wait_for_intro_of_candidate = lambda _: succeed(None)
        self.mc_community.publish_signature_request_message = lambda *_: None
        self.mc_community.wait_for_signature_request = lambda _: succeed('a')
        self.mc_community.my_member = MockObject()
        self.mc_community.my_member.public_key = 'a' * 20
        self.mc_community.persistence = MockObject()
        self.mc_community.persistence.get_latest = lambda _: latest_block

        self.mc_wallet = MultichainWallet(self.mc_community)

    def test_get_mc_wallet_name(self):
        """
        Test the identifier of the Multichain wallet
        """
        self.assertEqual(self.mc_wallet.get_name(), 'Reputation')

    def test_get_mc_wallet_id(self):
        """
        Test the identifier of a Multichain wallet
        """
        self.assertEqual(self.mc_wallet.get_identifier(), 'MC')

    @deferred(timeout=10)
    def test_get_balance(self):
        """
        Test the balance retrieval of a Multichain wallet
        """
        def on_balance(balance):
            self.assertEqual(balance['available'], 5)

        return self.mc_wallet.get_balance().addCallback(on_balance)

    @deferred(timeout=10)
    def test_transfer_invalid(self):
        """
        Test the transfer method of a Multichain wallet
        """
        test_deferred = Deferred()

        def on_error(failure):
            self.assertIsInstance(failure.value, InsufficientFunds)
            test_deferred.callback(None)

        self.mc_wallet.transfer(200, None).addErrback(on_error)
        return test_deferred

    @deferred(timeout=10)
    def test_transfer_no_member(self):
        """
        Test the transfer method of a Multichain wallet when there's no member available
        """
        candidate = MockObject()
        candidate.get_member = lambda: None
        candidate.sock_addr = ("127.0.0.1", 1234)
        self.mc_community.get_candidate = lambda _: candidate

        def on_transfer(prev_hash):
            self.assertEqual(prev_hash, 'b' * 5)

        return self.mc_wallet.transfer(1, candidate).addCallback(on_transfer)

    @deferred(timeout=10)
    def test_monitor_transaction(self):
        """
        Test the monitoring of a transaction in a Multichain wallet
        """
        def on_transaction(transaction):
            self.assertEqual(transaction, 'a')

        return self.mc_wallet.monitor_transaction(None).addCallback(on_transaction)

    def test_address(self):
        """
        Test the address of a Multichain wallet
        """
        self.assertIsInstance(self.mc_wallet.get_address(), str)

    @deferred(timeout=10)
    def test_get_transaction(self):
        """
        Test the retrieval of transactions of a dummy wallet
        """

        def on_transactions(transactions):
            self.assertIsInstance(transactions, list)

        return self.mc_wallet.get_transactions().addCallback(on_transactions)

    def test_min_unit(self):
        """
        Test the minimum unit of a Multichain wallet
        """
        self.assertEqual(self.mc_wallet.min_unit(), 1)
