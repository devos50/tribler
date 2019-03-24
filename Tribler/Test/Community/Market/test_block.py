from __future__ import absolute_import

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.block import MarketBlock
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.tick import Ask
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import Transaction, TransactionId, TransactionNumber


class TestMarketBlock(AbstractServer):
    """
    This class contains tests for a TrustChain block as used in the market.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestMarketBlock, self).setUp()

        self.ask = Ask(OrderId(TraderId(b'0' * 40), OrderNumber(1)),
                       AssetPair(AssetAmount(30, b'BTC'), AssetAmount(30, b'MB')), Timeout(30), Timestamp(0.0), True)
        self.bid = Ask(OrderId(TraderId(b'1' * 40), OrderNumber(1)),
                       AssetPair(AssetAmount(30, b'BTC'), AssetAmount(30, b'MB')), Timeout(30), Timestamp(0.0), False)
        self.transaction = Transaction(TransactionId(TraderId(b'0' * 40), TransactionNumber(1)),
                                       AssetPair(AssetAmount(30, b'BTC'), AssetAmount(30, b'MB')),
                                       OrderId(TraderId(b'0' * 40), OrderNumber(1)),
                                       OrderId(TraderId(b'1' * 40), OrderNumber(1)), Timestamp(0.0))

        ask_tx = self.ask.to_block_dict()
        bid_tx = self.bid.to_block_dict()

        self.tick_block = MarketBlock()
        self.tick_block.type = b'ask'
        self.tick_block.transaction = {b'tick': ask_tx}

        self.cancel_block = MarketBlock()
        self.cancel_block.type = b'cancel_order'
        self.cancel_block.transaction = {b'trader_id': b'a' * 40, b'order_number': 1}

        self.tx_block = MarketBlock()
        self.tx_block.type = b'tx_init'
        self.tx_block.transaction = {
            b'ask': ask_tx,
            b'bid': bid_tx,
            b'tx': self.transaction.to_dictionary()
        }

        payment = {
            b'trader_id': b'a' * 40,
            b'transaction_number': 3,
            b'transferred': {
                b'amount': 3,
                b'type': b'BTC'
            },
            b'payment_id': b'a',
            b'address_from': b'a',
            b'address_to': b'b',
            b'timestamp': 1234.3,
            b'success': True
        }
        self.payment_block = MarketBlock()
        self.payment_block.type = b'tx_payment'
        self.payment_block.transaction = {b'payment': payment}

    def test_tick_block(self):
        """
        Test whether a tick block can be correctly verified
        """
        self.assertTrue(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction[b'tick'][b'timeout'] = -1
        self.assertFalse(self.tick_block.is_valid_tick_block())
        self.tick_block.transaction[b'tick'][b'timeout'] = 3600

        self.tick_block.type = b'test'
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.type = b'ask'
        self.tick_block.transaction[b'test'] = self.tick_block.transaction.pop(b'tick')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction[b'tick'] = self.tick_block.transaction.pop(b'test')
        self.tick_block.transaction[b'tick'].pop(b'timeout')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction[b'tick'][b'timeout'] = b"300"
        self.assertFalse(self.tick_block.is_valid_tick_block())

        self.tick_block.transaction[b'tick'][b'timeout'] = 300
        self.tick_block.transaction[b'tick'][b'trader_id'] = b'g' * 40
        self.assertFalse(self.tick_block.is_valid_tick_block())

        # Make the asset pair invalid
        assets = self.tick_block.transaction[b'tick'][b'assets']
        self.tick_block.transaction[b'tick'][b'trader_id'] = b'a' * 40
        assets[b'test'] = assets.pop(b'first')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets[b'first'] = assets.pop(b'test')
        assets[b'first'][b'test'] = assets[b'first'].pop(b'amount')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets[b'first'][b'amount'] = assets[b'first'][b'test']
        assets[b'second'][b'test'] = assets[b'second'].pop(b'amount')
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets[b'second'][b'amount'] = assets[b'second'][b'test']
        assets[b'first'][b'amount'] = 3.4
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets[b'first'][b'amount'] = 2 ** 64
        self.assertFalse(self.tick_block.is_valid_tick_block())

        assets[b'first'][b'amount'] = 3
        assets[b'second'][b'type'] = 4
        self.assertFalse(self.tick_block.is_valid_tick_block())

    def test_cancel_block(self):
        """
        Test whether a cancel block can be correctly verified
        """
        self.assertTrue(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.type = b'cancel'
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.type = b'cancel_order'
        self.cancel_block.transaction.pop(b'trader_id')
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

        self.cancel_block.transaction[b'trader_id'] = 3
        self.assertFalse(self.cancel_block.is_valid_cancel_block())

    def test_tx_init_done_block(self):
        """
        Test whether a tx_init/tx_done block can be correctly verified
        """
        self.assertTrue(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.type = b'test'
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.type = b'tx_init'
        self.tx_block.transaction[b'test'] = self.tx_block.transaction.pop(b'ask')
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction[b'ask'] = self.tx_block.transaction.pop(b'test')
        self.tx_block.transaction[b'ask'][b'timeout'] = 3.44
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction[b'ask'][b'timeout'] = 3
        self.tx_block.transaction[b'bid'][b'timeout'] = 3.44
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction[b'bid'][b'timeout'] = 3
        self.tx_block.transaction[b'tx'].pop(b'trader_id')
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction[b'tx'][b'trader_id'] = b'a' * 40
        self.tx_block.transaction[b'tx'][b'test'] = 3
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction[b'tx'].pop(b'test')
        self.tx_block.transaction[b'tx'][b'trader_id'] = b'a'
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction[b'tx'][b'trader_id'] = b'a' * 40
        self.tx_block.transaction[b'tx'][b'assets'][b'first'][b'amount'] = 3.4
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction[b'tx'][b'assets'][b'first'][b'amount'] = 3
        self.tx_block.transaction[b'tx'][b'transferred'][b'first'][b'amount'] = 3.4
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

        self.tx_block.transaction[b'tx'][b'transferred'][b'first'][b'amount'] = 3
        self.tx_block.transaction[b'tx'][b'transaction_number'] = 3.4
        self.assertFalse(self.tx_block.is_valid_tx_init_done_block())

    def test_tx_payment_block(self):
        """
        Test whether a tx_payment block can be correctly verified
        """
        self.assertTrue(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.type = b'test'
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.type = b'tx_payment'
        self.payment_block.transaction[b'test'] = self.payment_block.transaction.pop(b'payment')
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction[b'payment'] = self.payment_block.transaction.pop(b'test')
        self.payment_block.transaction[b'payment'].pop(b'address_to')
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction[b'payment'][b'address_to'] = b'a'
        self.payment_block.transaction[b'payment'][b'test'] = b'a'
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction[b'payment'].pop(b'test')
        self.payment_block.transaction[b'payment'][b'address_to'] = 3
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

        self.payment_block.transaction[b'payment'][b'address_to'] = b'a'
        self.payment_block.transaction[b'payment'][b'trader_id'] = b'a' * 39
        self.assertFalse(self.payment_block.is_valid_tx_payment_block())

    def test_is_valid_asset_pair(self):
        """
        Test the method to verify whether an asset pair is valid
        """
        self.assertFalse(MarketBlock.is_valid_asset_pair({b'a': b'b'}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({b'first': {b'amount': 3, b'type': b'DUM1'},
                                                          b'second': {b'amount': 3}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({b'first': {b'type': b'DUM1'},
                                                          b'second': {b'amount': 3, b'type': b'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({b'first': {b'amount': b"4", b'type': b'DUM1'},
                                                          b'second': {b'amount': 3, b'type': b'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({b'first': {b'amount': 4, b'type': b'DUM1'},
                                                          b'second': {b'amount': "3", b'type': b'DUM2'}}))
        self.assertFalse(MarketBlock.is_valid_asset_pair({b'first': {b'amount': -4, b'type': b'DUM1'},
                                                          b'second': {b'amount': 3, b'type': b'DUM2'}}))
