from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.conversion import MarketConversion
from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.payload import OfferPayload, OfferSyncPayload, AcceptedTradePayload, DeclinedTradePayload
from Tribler.community.market.ttl import Ttl
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMarketConversion(AbstractTestCommunity):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestMarketConversion, self).setUp(annotate=annotate)
        self.market_community = MarketCommunity(self.dispersy, self.master_member, self.member)
        self.market_community.initialize()
        self.conversion = MarketConversion(self.market_community)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        # Don't unload_community() as it never got registered in dispersy on the first place.
        self.market_community.cancel_all_pending_tasks()
        self.market_community = None
        yield super(TestMarketConversion, self).tearDown(annotate=annotate)

    def test_encode_decode_offer(self):
        """
        Test encoding and decoding of an offer
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"ask")

        offer_payload = OfferPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'), OrderNumber(4),
                                                    Price(5, 'BTC'), Quantity(6, 'MC'), Timeout(3600), Timestamp.now(),
                                                    Ttl(3), "1.2.3.4", 1234)
        message.payload = offer_payload
        packet, = self.conversion._encode_offer(message)
        self.assertTrue(packet)

        meta_msg = self.market_community.get_meta_message(u"ask")
        msg = MockObject()
        msg.meta = meta_msg
        offset, decoded = self.conversion._decode_offer(msg, 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.price, Price(5, 'BTC'))
        self.assertEqual(int(decoded.ttl), 3)

    def test_encode_decode_offer_sync(self):
        """
        Test encoding and decoding of an offer sync
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"offer-sync")

        offer_payload = OfferSyncPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'), OrderNumber(4),
                                                        Price(5, 'BTC'), Quantity(6, 'MC'), Timeout(3600),
                                                        Timestamp.now(), Ttl(3), "1.2.3.4", 1234, True)
        message.payload = offer_payload
        packet, = self.conversion._encode_offer_sync(message)
        self.assertTrue(packet)

        meta_msg = self.market_community.get_meta_message(u"offer-sync")
        msg = MockObject()
        msg.meta = meta_msg
        offset, decoded = self.conversion._decode_offer_sync(msg, 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.price, Price(5, 'BTC'))
        self.assertEqual(int(decoded.ttl), 3)
        self.assertTrue(decoded.is_ask)

    def test_encode_decode_accepted_trade(self):
        """
        Test encoding and decoding of an accepted trade
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"accepted-trade")

        trade_payload = AcceptedTradePayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                            OrderNumber(4), TraderId('def'), OrderNumber(5),
                                                            Price(6, 'BTC'), Quantity(6, 'MC'), Timestamp.now(), Ttl(4),
                                                            "1.2.3.4", 1234)
        message.payload = trade_payload
        packet, = self.conversion._encode_accepted_trade(message)
        self.assertTrue(packet)

        meta_msg = self.market_community.get_meta_message(u"accepted-trade")
        msg = MockObject()
        msg.meta = meta_msg
        offset, decoded = self.conversion._decode_accepted_trade(msg, 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.price, Price(6, 'BTC'))
        self.assertEqual(int(decoded.ttl), 4)
        self.assertEqual(decoded.recipient_trader_id, TraderId('def'))

    def test_encode_decode_declined_trade(self):
        """
        Test encoding and decoding of an declined trade
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"declined-trade")

        trade_payload = DeclinedTradePayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                            OrderNumber(4), TraderId('def'), OrderNumber(5),
                                                            Timestamp.now())
        message.payload = trade_payload
        packet, = self.conversion._encode_declined_trade(message)
        self.assertTrue(packet)

        meta_msg = self.market_community.get_meta_message(u"declined-trade")
        msg = MockObject()
        msg.meta = meta_msg
        offset, decoded = self.conversion._decode_declined_trade(msg, 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.recipient_trader_id, TraderId('def'))
