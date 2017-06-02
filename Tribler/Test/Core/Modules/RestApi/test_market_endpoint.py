import json

from Tribler.community.market.core.payment import Payment
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.wallet_address import WalletAddress
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred
from Tribler.community.market.core.message import MessageId, MessageNumber
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber, Order
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestWalletsEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestWalletsEndpoint, self).setUp(autoload_discovery=autoload_discovery)
        dummy1_wallet = DummyWallet1()
        dummy2_wallet = DummyWallet2()

        self.session.lm.market_community.wallets = {dummy1_wallet.get_identifier(): dummy1_wallet,
                                                    dummy2_wallet.get_identifier(): dummy2_wallet}

    def add_transaction_and_payment(self):
        """
        Add a transaction and a payment to the market
        """
        proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                       OrderId(TraderId('0'), OrderNumber(1)),
                                       OrderId(TraderId('1'), OrderNumber(2)),
                                       Price(63400, 'BTC'), Quantity(30, 'MC'), Timestamp(1462224447.117))
        accepted_trade = Trade.accept(MessageId(TraderId('0'), MessageNumber('message_number')),
                                      Timestamp(1462224447.117), proposed_trade)
        transaction = self.session.lm.market_community.transaction_manager.create_from_accepted_trade(accepted_trade)

        payment = Payment(MessageId(TraderId("0"), MessageNumber("1")), transaction.transaction_id,
                          Quantity(0, 'MC'), Price(20, 'BTC'), WalletAddress('a'), WalletAddress('b'),
                          PaymentId('aaa'), Timestamp(4.0))
        transaction.add_payment(payment)
        self.session.lm.market_community.transaction_manager.transaction_repository.update(transaction)

        return transaction

    @blocking_call_on_reactor_thread
    def setUpPreSession(self):
        super(TestWalletsEndpoint, self).setUpPreSession()
        self.config.set_dispersy(True)

    @deferred(timeout=10)
    def test_get_asks(self):
        """
        Test whether the API returns the right asks in the order book when performing a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('asks', json_response)
            self.assertEqual(len(json_response['asks']), 1)
            self.assertIn('ticks', json_response['asks'][0])
            self.assertEqual(len(json_response['asks'][0]['ticks']), 1)

        self.session.lm.market_community.create_ask(10, 'DUM1', 10, 'DUM2', 3600)
        self.should_check_equality = False
        return self.do_request('market/asks', expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_create_ask(self):
        """
        Test whether we can create an ask using the API
        """
        def on_response(_):
            self.assertEqual(len(self.session.lm.market_community.order_book.asks), 1)

        self.should_check_equality = False
        post_data = {'price': 10, 'quantity': 10, 'price_type': 'DUM1', 'quantity_type': 'DUM2'}
        return self.do_request('market/asks', expected_code=200, request_type='PUT', post_data=post_data)\
            .addCallback(on_response)

    @deferred(timeout=10)
    def test_get_bids(self):
        """
        Test whether the API returns the right bids in the order book when performing a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('bids', json_response)
            self.assertEqual(len(json_response['bids']), 1)
            self.assertIn('ticks', json_response['bids'][0])
            self.assertEqual(len(json_response['bids'][0]['ticks']), 1)

        self.session.lm.market_community.create_bid(10, 'DUM1', 10, 'DUM2', 3600)
        self.should_check_equality = False
        return self.do_request('market/bids', expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_create_bid(self):
        """
        Test whether we can create a bid using the API
        """
        def on_response(_):
            self.assertEqual(len(self.session.lm.market_community.order_book.bids), 1)

        self.should_check_equality = False
        post_data = {'price': 10, 'quantity': 10, 'price_type': 'DUM1', 'quantity_type': 'DUM2'}
        return self.do_request('market/bids', expected_code=200, request_type='PUT', post_data=post_data) \
            .addCallback(on_response)

    @deferred(timeout=10)
    def test_get_transactions(self):
        """
        Test whether the API returns the right transactions in the order book when performing a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('transactions', json_response)
            self.assertEqual(len(json_response['transactions']), 1)

        self.add_transaction_and_payment()
        self.should_check_equality = False
        return self.do_request('market/transactions', expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_get_orders(self):
        """
        Test whether the API returns the right orders when we perform a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('orders', json_response)
            self.assertEqual(len(json_response['orders']), 1)

        self.session.lm.market_community.order_manager.create_ask_order(
            Price(3, 'DUM1'), Quantity(4, 'DUM2'), Timeout(3600))

        self.should_check_equality = False
        return self.do_request('market/orders', expected_code=200).addCallback(on_response)

    @deferred(timeout=10)
    def test_get_payments(self):
        """
        Test whether the API returns the right payments when we perform a request
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('payments', json_response)
            self.assertEqual(len(json_response['payments']), 1)

        transaction = self.add_transaction_and_payment()
        self.should_check_equality = False
        return self.do_request('market/transactions/%s/%s/payments' %
                               (transaction.transaction_id.trader_id, transaction.transaction_id.transaction_number),
                               expected_code=200).addCallback(on_response)
