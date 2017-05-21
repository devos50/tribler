import unittest
import os
from mock import Mock, MagicMock
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.core.message import TraderId, MessageId, MessageNumber
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Ask
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade
from Tribler.community.market.ttl import Ttl
from Tribler.community.market.wallet.dummy_wallet import DummyWallet1, DummyWallet2
from Tribler.dispersy.candidate import Candidate, WalkCandidate
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class CommunityTestSuite(AbstractTestCommunity):
    """Community test cases."""

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(CommunityTestSuite, self).setUp(annotate=annotate)

        dummy1_wallet = DummyWallet1()
        dummy2_wallet = DummyWallet2()

        self.market_community = MarketCommunity(self.dispersy, self.master_member, self.member)
        self.market_community.initialize(wallets={dummy1_wallet.get_identifier(): dummy1_wallet,
                                                  dummy2_wallet.get_identifier(): dummy2_wallet})
        self.market_community.use_local_address = True
        self.dispersy._lan_address = ("127.0.0.1", 1234)

        self.dispersy.attach_community(self.market_community)

        self.ask = Ask(MessageId(TraderId('0'), MessageNumber('message_number')),
                       OrderId(TraderId('0'), OrderNumber(1234)), Price(63400, 'DUM1'), Quantity(30, 'DUM2'),
                       Timeout(3600), Timestamp.now())
        self.bid = Ask(MessageId(TraderId('1'), MessageNumber('message_number')),
                       OrderId(TraderId('1'), OrderNumber(1234)), Price(343, 'DUM1'), Quantity(22, 'DUM2'),
                       Timeout(3600), Timestamp.now())
        self.proposed_trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                            OrderId(TraderId('0'), OrderNumber(23)),
                                            OrderId(TraderId(self.market_community.mid), OrderNumber(24)),
                                            Price(63400, 'DUM1'), Quantity(30, 'DUM2'), Timestamp.now())

    @blocking_call_on_reactor_thread
    def test_lookup_ip(self):
        # Test for lookup ip
        self.market_community.update_ip(TraderId('0'), ("1.1.1.1", 0))
        self.assertEquals(("1.1.1.1", 0), self.market_community.lookup_ip(TraderId('0')))

    @blocking_call_on_reactor_thread
    def test_create_ask(self):
        # Test for create ask
        self.assertRaises(RuntimeError, self.market_community.create_ask, 20, 'DUM2', 100, 'DUM2', 0.0)
        self.assertRaises(RuntimeError, self.market_community.create_ask, 20, 'NOTEXIST', 100, 'DUM2', 0.0)
        self.assertRaises(RuntimeError, self.market_community.create_ask, 20, 'DUM2', 100, 'NOTEXIST', 0.0)
        self.assertTrue(self.market_community.create_ask(20, 'DUM1', 100, 'DUM2', 3600))
        self.assertEquals(1, len(self.market_community.order_book._asks))
        self.assertEquals(0, len(self.market_community.order_book._bids))

    def test_on_ask(self):
        # Test for on ask
        meta = self.market_community.get_meta_message(u"ask")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            payload=self.ask.to_network() + (Ttl.default(), "127.0.0.1", 1234)
        )
        self.market_community.on_ask([message])
        self.assertEquals(1, len(self.market_community.order_book._asks))
        self.assertEquals(0, len(self.market_community.order_book._bids))

    def test_create_bid(self):
        # Test for create bid
        self.assertRaises(RuntimeError, self.market_community.create_bid, 20, 'DUM2', 100, 'DUM2', 0.0)
        self.assertRaises(RuntimeError, self.market_community.create_bid, 20, 'NOTEXIST', 100, 'DUM2', 0.0)
        self.assertRaises(RuntimeError, self.market_community.create_bid, 20, 'DUM2', 100, 'NOTEXIST', 0.0)
        self.assertTrue(self.market_community.create_bid(20, 'DUM1', 100, 'DUM2', 3600))
        self.assertEquals(0, len(self.market_community.order_book._asks))
        self.assertEquals(1, len(self.market_community.order_book._bids))

    def test_on_bid(self):
        # Test for on bid
        meta = self.market_community.get_meta_message(u"bid")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            payload=self.bid.to_network() + (Ttl.default(), "127.0.0.1", 1234)
        )
        self.market_community.on_bid([message])
        self.assertEquals(0, len(self.market_community.order_book._asks))
        self.assertEquals(1, len(self.market_community.order_book._bids))

    def test_check_history(self):
        # Test for check history
        self.assertTrue(self.market_community.check_history(self.ask))
        self.assertFalse(self.market_community.check_history(self.ask))

    def test_on_proposed_trade(self):  # TODO: Add assertions to test
        # Test for on proposed trade
        self.market_community.update_ip(TraderId(self.market_community.mid), ('2.2.2.2', 2))
        destination, payload = self.proposed_trade.to_network()
        payload += ("127.0.0.1", 1234)
        candidate = Candidate(self.market_community.lookup_ip(destination), False)
        meta = self.market_community.get_meta_message(u"proposed-trade")
        message = meta.impl(
            authentication=(self.market_community.my_member,),
            distribution=(self.market_community.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )
        self.market_community.on_proposed_trade([message])

if __name__ == '__main__':
    unittest.main()
