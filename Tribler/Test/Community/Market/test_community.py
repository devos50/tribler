from __future__ import absolute_import

import hashlib
import random
import string

from twisted.internet.defer import fail, inlineCallbacks
from twisted.python.failure import Failure

from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import trial_timeout
from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.tradingengine import TradingEngine
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8


class MockTradingEngine(TradingEngine):
    """
    Trading engine that immediately completes a trade.
    """

    def trade(self, trade):
        self.completed_trades.append(trade)

        # The trade ID must be the same on the two nodes
        trade_id = hashlib.sha1(str(trade.proposal_id)).digest()
        self.matching_community.on_trade_completed(trade, trade_id)


class TestMarketCommunityBase(TestBase):
    __testing__ = False
    NUM_NODES = 2

    def setUp(self):
        super(TestMarketCommunityBase, self).setUp()
        self.initialize(MarketCommunity, self.NUM_NODES)
        for node in self.nodes:
            node.overlay._use_main_thread = True

    def create_node(self):
        trading_engine = MockTradingEngine()
        mock_ipv8 = MockIPv8(u"curve25519", MarketCommunity, is_matchmaker=True, create_dht=True, use_database=False, working_directory=u":memory:", trading_engine=trading_engine)
        return mock_ipv8


class TestMarketCommunity(TestMarketCommunityBase):
    __testing__ = True
    NUM_NODES = 3

    def setUp(self):
        super(TestMarketCommunity, self).setUp()

        self.nodes[0].overlay.disable_matchmaker()
        self.nodes[1].overlay.disable_matchmaker()

    @trial_timeout(2)
    @inlineCallbacks
    def test_create_ask(self):
        """
        Test creating an ask and sending it to others
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(0.5)

        orders = list(self.nodes[0].overlay.order_manager.order_repository.find_all())
        self.assertTrue(orders)
        self.assertTrue(orders[0].is_ask())
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)

    @trial_timeout(2)
    @inlineCallbacks
    def test_create_bid(self):
        """
        Test creating a bid and sending it to others
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_bid(AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(0.5)

        orders = list(self.nodes[0].overlay.order_manager.order_repository.find_all())
        self.assertTrue(orders)
        self.assertFalse(orders[0].is_ask())
        self.assertEqual(len(self.nodes[2].overlay.order_book.bids), 1)

    @trial_timeout(2)
    @inlineCallbacks
    def test_order_broadcast(self):
        """
        Test that an order is broadcast across multiple hops
        """
        self.nodes[0].overlay.walk_to(self.nodes[1].endpoint.wan_address)
        self.nodes[1].overlay.walk_to(self.nodes[2].endpoint.wan_address)
        yield self.deliver_messages()

        self.nodes[0].overlay.create_bid(AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(0.5)

        self.assertEqual(len(self.nodes[2].overlay.order_book.bids), 1)

    def test_create_invalid_ask_bid(self):
        """
        Test creating an invalid ask/bid with invalid asset pairs.
        """
        invalid_pair = AssetPair(AssetAmount(1, 'DUM2'), AssetAmount(2, 'DUM2'))
        self.assertRaises(RuntimeError, self.nodes[0].overlay.create_ask, invalid_pair, 3600)
        self.assertRaises(RuntimeError, self.nodes[0].overlay.create_bid, invalid_pair, 3600)

    @trial_timeout(2)
    @inlineCallbacks
    def test_decline_trade(self):
        """
        Test declining a trade
        """
        yield self.introduce_nodes()

        order = yield self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(1, 'DUM2')), 3600)
        order._traded_quantity = 1  # So it looks like this order has already been fulfilled

        yield self.sleep(0.5)

        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(1, 'DUM2')), 3600)

        yield self.sleep(1)

        # The ask should be removed since this node thinks the order is already completed
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 0)

    @trial_timeout(3)
    @inlineCallbacks
    def test_decline_trade_cancel(self):
        """
        Test whether a cancelled order is correctly declined when negotiating
        """
        yield self.introduce_nodes()

        order = self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)
        self.nodes[0].overlay.cancel_order(order.order_id, broadcast=False)

        self.assertEqual(order.status, "cancelled")

        yield self.sleep(0.5)

        self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(1)

        # No trade should have been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 0)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 0)
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 0)

    @trial_timeout(2)
    @inlineCallbacks
    def test_decline_match_cancel(self):
        """
        Test whether an order is removed when the matched order is cancelled
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)
        yield self.sleep(0.5)

        order = self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)
        self.nodes[1].overlay.cancel_order(order.order_id, broadcast=False)  # Immediately cancel it

        yield self.sleep(0.5)
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 0)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 0)
        self.assertEqual(len(self.nodes[2].overlay.order_book.bids), 0)

    @trial_timeout(3)
    @inlineCallbacks
    def test_counter_trade(self):
        """
        Test making a counter trade
        """
        yield self.introduce_nodes()

        order = yield self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)
        order._traded_quantity = 1  # Partially fulfill this order

        yield self.sleep(0.5)  # Give it some time to complete the trade

        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(1)

        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.first.amount, 1)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.second.amount, 1)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 1)

    @trial_timeout(3)
    @inlineCallbacks
    def test_completed_trade(self):
        """
        Test whether a completed trade is removed from the orderbook of a matchmaker
        """
        yield self.introduce_nodes()

        yield self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(0.5)  # Give it some time to disseminate

        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        order = self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)
        order._traded_quantity = 2  # Fulfill this order

        yield self.sleep(0.5)

        # Matchmaker should have removed this order from the orderbook
        self.assertFalse(self.nodes[2].overlay.order_book.tick_exists(order.order_id))

    @trial_timeout(3)
    @inlineCallbacks
    def test_other_completed_trade(self):
        """
        Test whether a completed trade of a counterparty is removed from the orderbook of a matchmaker
        """
        yield self.introduce_nodes()

        order = yield self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(0.5)  # Give it some time to disseminate

        order._traded_quantity = 2  # Fulfill this order
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(1)

        # Matchmaker should have removed this order from the orderbook
        self.assertFalse(self.nodes[2].overlay.order_book.tick_exists(order.order_id))

    @trial_timeout(3)
    @inlineCallbacks
    def test_e2e_trade(self):
        """
        Test trading dummy tokens against bandwidth tokens between two persons, with a matchmaker
        """
        yield self.introduce_nodes()

        yield self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(50, 'DUM1'), AssetAmount(50, 'MB')), 3600)
        yield self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(50, 'DUM1'), AssetAmount(50, 'MB')), 3600)

        yield self.sleep(1)  # Give it some time to complete the trade

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.first.amount, 50)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.second.amount, 50)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.first.amount, 50)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.second.amount, 50)

    @trial_timeout(3)
    @inlineCallbacks
    def test_e2e_trade_dht(self):
        """
        Test a full trade with (dummy assets), where both traders are not connected to each other
        """
        yield self.introduce_nodes()

        for node in self.nodes:
            for other in self.nodes:
                if other != node:
                    node.dht.walk_to(other.endpoint.wan_address)
        yield self.deliver_messages()

        # Remove the address from the mid registry from the trading peers
        self.nodes[0].overlay.mid_register.pop(TraderId(self.nodes[1].overlay.mid))
        self.nodes[1].overlay.mid_register.pop(TraderId(self.nodes[0].overlay.mid))

        for node in self.nodes:
            node.dht.store_peer()
        yield self.deliver_messages()

        yield self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
        yield self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)

        yield self.sleep(1)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.first.amount, 10)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.second.amount, 10)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.first.amount, 10)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.second.amount, 10)

    @inlineCallbacks
    def test_cancel(self):
        """
        Test cancelling an order
        """
        yield self.introduce_nodes()

        ask_order = yield self.nodes[0].overlay.create_ask(
            AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(1, 'DUM2')), 3600)

        yield self.sleep(0.5)

        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 1)
        self.nodes[0].overlay.cancel_order(ask_order.order_id)

        yield self.sleep(0.5)

        self.assertTrue(self.nodes[0].overlay.order_manager.order_repository.find_by_id(ask_order.order_id).cancelled)
        self.assertEqual(len(self.nodes[2].overlay.order_book.asks), 0)

    @trial_timeout(3)
    @inlineCallbacks
    def test_proposed_trade_timeout(self):
        """
        Test whether we unreserve the quantity if a proposed trade timeouts
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.decode_map[chr(10)] = lambda *_: None

        ask_order = yield self.nodes[0].overlay.create_ask(
            AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(1, 'DUM2')), 3600)
        bid_order = yield self.nodes[1].overlay.create_bid(
            AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(1, 'DUM2')), 3600)

        yield self.sleep(1)

        outstanding = self.nodes[1].overlay.get_outstanding_proposals(bid_order.order_id, ask_order.order_id)
        self.assertTrue(outstanding)
        outstanding[0][1].on_timeout()

        yield self.sleep(0.5)

        self.assertEqual(ask_order.reserved_quantity, 0)
        self.assertEqual(bid_order.reserved_quantity, 0)

    @trial_timeout(4)
    @inlineCallbacks
    def test_orderbook_sync(self):
        """
        Test whether orderbooks are synchronized with a new node
        """
        yield self.introduce_nodes()

        ask_order = yield self.nodes[0].overlay.create_ask(
            AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)
        bid_order = yield self.nodes[1].overlay.create_bid(
            AssetPair(AssetAmount(1, 'DUM1'), AssetAmount(1, 'DUM2')), 3600)

        yield self.deliver_messages(timeout=.5)

        # Add a node that crawls the matchmaker
        self.add_node_to_experiment(self.create_node())
        yield self.introduce_nodes()

        self.nodes[3].overlay.sync_orderbook()
        yield self.sleep(0.2)  # For processing the tick blocks

        self.assertTrue(self.nodes[3].overlay.order_book.get_tick(ask_order.order_id))
        self.assertTrue(self.nodes[3].overlay.order_book.get_tick(bid_order.order_id))

        # Add another node that crawls our newest node
        self.add_node_to_experiment(self.create_node())
        self.nodes[4].overlay.send_orderbook_sync(self.nodes[3].overlay.my_peer)
        yield self.deliver_messages(timeout=.5)
        yield self.sleep(0.2)  # For processing the tick blocks

        self.assertTrue(self.nodes[4].overlay.order_book.get_tick(ask_order.order_id))
        self.assertTrue(self.nodes[4].overlay.order_book.get_tick(bid_order.order_id))

    @trial_timeout(4)
    @inlineCallbacks
    def test_partial_trade(self):
        """
        Test a partial trade between two nodes with a matchmaker
        """
        yield self.introduce_nodes()

        yield self.nodes[0].overlay.create_ask(
            AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
        yield self.nodes[1].overlay.create_bid(
            AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(1)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.first.amount, 2)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.second.amount, 2)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.first.amount, 2)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.second.amount, 2)

        yield self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(8, 'DUM1'), AssetAmount(8, 'DUM2')), 3600)

        yield self.sleep(1)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 2)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[1].assets.first.amount, 8)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[1].assets.second.amount, 8)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 2)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[1].assets.first.amount, 8)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[1].assets.second.amount, 8)


class TestMarketCommunityFourNodes(TestMarketCommunityBase):
    __testing__ = True
    NUM_NODES = 5

    def setUp(self):
        super(TestMarketCommunityFourNodes, self).setUp()

        self.nodes[0].overlay.disable_matchmaker()
        self.nodes[1].overlay.disable_matchmaker()
        self.nodes[2].overlay.disable_matchmaker()

    @trial_timeout(2)
    @inlineCallbacks
    def test_partial_match(self):
        """
        Test matchmaking with partial orders
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(5, 'DUM1'), AssetAmount(5, 'DUM2')), 3600)
        self.nodes[1].overlay.create_ask(AssetPair(AssetAmount(5, 'DUM1'), AssetAmount(5, 'DUM2')), 3600)

        yield self.sleep(0.5)

        self.nodes[2].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)

        yield self.sleep(0.5)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(len(self.nodes[2].overlay.trading_engine.completed_trades), 2)
        self.assertEqual(self.nodes[2].overlay.trading_engine.completed_trades[0].assets.first.amount, 5)
        self.assertEqual(self.nodes[2].overlay.trading_engine.completed_trades[0].assets.second.amount, 5)
        self.assertEqual(self.nodes[2].overlay.trading_engine.completed_trades[1].assets.first.amount, 5)
        self.assertEqual(self.nodes[2].overlay.trading_engine.completed_trades[1].assets.second.amount, 5)

    @inlineCallbacks
    def match_window_impl(self, test_ask):
        yield self.introduce_nodes()

        self.nodes[2].overlay.settings.match_window = 0.5  # Wait 1 sec before accepting (the best) match

        if test_ask:
            order1 = self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
            order2 = self.nodes[0].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(20, 'DUM2')), 3600)
            expected_amount = 20
        else:
            order1 = self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
            order2 = self.nodes[1].overlay.create_ask(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(20, 'DUM2')), 3600)
            expected_amount = 10

        yield self.sleep(0.2)

        # Make sure that the two matchmaker match different orders
        order1_tick = self.nodes[3].overlay.order_book.get_tick(order1.order_id)
        order2_tick = self.nodes[4].overlay.order_book.get_tick(order2.order_id)
        order1_tick.available_for_matching = 0
        order2_tick.available_for_matching = 0

        if test_ask:
            self.nodes[2].overlay.create_ask(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(20, 'DUM2')), 3600)
        else:
            self.nodes[2].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(20, 'DUM2')), 3600)

        yield self.sleep(1)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.first.amount, 10)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.second.amount, expected_amount)
        self.assertEqual(len(self.nodes[2].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[2].overlay.trading_engine.completed_trades[0].assets.first.amount, 10)
        self.assertEqual(self.nodes[2].overlay.trading_engine.completed_trades[0].assets.second.amount, expected_amount)

    @trial_timeout(4)
    @inlineCallbacks
    def test_match_window_bid(self):
        """
        Test the match window when one is matching a new bid
        """
        yield self.match_window_impl(False)

    @trial_timeout(4)
    @inlineCallbacks
    def test_match_window_ask(self):
        """
        Test the match window when one is matching a new ask
        """
        yield self.match_window_impl(True)

    @trial_timeout(4)
    @inlineCallbacks
    def test_match_window_multiple(self):
        """
        Test whether multiple ask orders in the matching window will get matched
        """
        yield self.introduce_nodes()

        self.nodes[2].overlay.settings.match_window = 0.5  # Wait 1 sec before accepting (the best) match

        order1 = self.nodes[0].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
        order2 = self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)

        yield self.sleep(0.3)

        # Make sure that the two matchmaker match different orders
        order1_tick = self.nodes[3].overlay.order_book.get_tick(order1.order_id)
        order2_tick = self.nodes[4].overlay.order_book.get_tick(order2.order_id)
        order1_tick.available_for_matching = 0
        order2_tick.available_for_matching = 0

        self.nodes[2].overlay.create_ask(AssetPair(AssetAmount(20, 'DUM1'), AssetAmount(20, 'DUM2')), 3600)

        yield self.sleep(1.5)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[2].overlay.trading_engine.completed_trades), 2)
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 1)


class TestMarketCommunityTwoNodes(TestMarketCommunityBase):
    __testing__ = True

    @trial_timeout(3)
    @inlineCallbacks
    def test_e2e_trade(self):
        """
        Test a direct trade between two nodes
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(13, 'DUM2')), 3600)
        self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(13, 'DUM2')), 3600)

        yield self.sleep(1)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.first.amount, 10)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.second.amount, 13)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.first.amount, 10)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.second.amount, 13)

    @trial_timeout(3)
    @inlineCallbacks
    def test_partial_trade(self):
        """
        Test a partial trade between two nodes
        """
        yield self.introduce_nodes()

        self.nodes[0].overlay.create_ask(AssetPair(AssetAmount(10, 'DUM1'), AssetAmount(10, 'DUM2')), 3600)
        self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(2, 'DUM1'), AssetAmount(2, 'DUM2')), 3600)

        yield self.sleep(1)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.first.amount, 2)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[0].assets.second.amount, 2)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 1)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.first.amount, 2)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[0].assets.second.amount, 2)

        # There should be no reserved quantity in the orderbook
        ask_order_id = list(self.nodes[0].overlay.order_manager.order_repository.find_all())[0].order_id
        for node_nr in [0, 1]:
            ask_tick_entry = self.nodes[node_nr].overlay.order_book.get_tick(ask_order_id)
            if ask_tick_entry:
                self.assertEqual(ask_tick_entry.reserved_for_matching, 0, "Node %d" % node_nr)

        yield self.nodes[1].overlay.create_bid(AssetPair(AssetAmount(8, 'DUM1'), AssetAmount(8, 'DUM2')), 3600)

        yield self.sleep(1)

        # Verify that the trade has been made
        self.assertEqual(len(self.nodes[0].overlay.trading_engine.completed_trades), 2)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[1].assets.first.amount, 8)
        self.assertEqual(self.nodes[0].overlay.trading_engine.completed_trades[1].assets.second.amount, 8)
        self.assertEqual(len(self.nodes[1].overlay.trading_engine.completed_trades), 2)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[1].assets.first.amount, 8)
        self.assertEqual(self.nodes[1].overlay.trading_engine.completed_trades[1].assets.second.amount, 8)

        for node_nr in [0, 1]:
            self.assertEqual(len(self.nodes[node_nr].overlay.order_book.asks), 0)
            self.assertEqual(len(self.nodes[node_nr].overlay.order_book.bids), 0)

    @inlineCallbacks
    def test_ping_pong(self):
        """
        Test the ping/pong mechanism of the market
        """
        yield self.nodes[0].overlay.ping_peer(self.nodes[1].overlay.my_peer)
