from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Utilities.encoding import encode
from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.conversion import MarketConversion
from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionNumber
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.payload import OfferPayload, OfferSyncPayload, AcceptedTradePayload, DeclinedTradePayload, \
    MarketIntroPayload, WalletInfoPayload, TransactionPayload, PaymentPayload, StartTransactionPayload
from Tribler.community.market.ttl import Ttl
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.meta import MetaObject
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

    def get_placeholder_msg(self, meta_name):
        """
        Return a placeholder message with a specific meta name
        """
        meta_msg = self.market_community.get_meta_message(meta_name)
        msg = MockObject()
        msg.meta = meta_msg
        return msg

    def test_decode_payload(self):
        """
        Test decoding of a payload
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"accepted-trade")

        trade_payload = AcceptedTradePayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                            OrderNumber(4), TraderId('def'), OrderNumber(5),
                                                            Price(6, 'BTC'), Quantity(6, 'MC'), Timestamp.now(), Ttl(4),
                                                            "1.2.3.4", 1234)
        message.payload = trade_payload

        packet = encode((3.14, 100))
        placeholder = self.get_placeholder_msg(u"accepted-trade")
        self.assertRaises(DropPacket, self.conversion._decode_payload, placeholder, 0, packet, [Price])
        self.assertRaises(DropPacket, self.conversion._decode_payload, placeholder, 0, "a2zz", [Price])

    def test_encode_decode_intro_request(self):
        """
        Test encoding and decoding of an introduction request
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"dispersy-introduction-request")

        bloomfilter = BloomFilter(0.005, 30, prefix=' ')
        intro_payload = MarketIntroPayload.Implementation(meta_msg, ("127.0.0.1", 1324), ("127.0.0.1", 1234),
                                                          ("127.0.0.1", 1234), True, u"public", None, 3, bloomfilter)
        message.payload = intro_payload
        packet_str = ''.join(self.conversion._encode_introduction_request(message))
        self.assertTrue(packet_str)

        placeholder = self.get_placeholder_msg(u"dispersy-introduction-request")
        offset, decoded = self.conversion._decode_introduction_request(placeholder, 0, packet_str)
        self.assertTrue(decoded)

        self.assertRaises(DropPacket, self.conversion._decode_introduction_request, placeholder, 0, 'abc')
        self.assertRaises(DropPacket, self.conversion._decode_introduction_request, placeholder, 0, packet_str + 'b')

        # Add a malformed bloomfilter
        intro_payload = MarketIntroPayload.Implementation(meta_msg, ("127.0.0.1", 1324), ("127.0.0.1", 1234),
                                                          ("127.0.0.1", 1234), True, u"public", None, 3, None)
        message.payload = intro_payload
        packet_str = ''.join(self.conversion._encode_introduction_request(message))
        self.assertRaises(DropPacket, self.conversion._decode_introduction_request, placeholder, 0, packet_str + 'a')

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

        offset, decoded = self.conversion._decode_offer(self.get_placeholder_msg(u"ask"), 0, packet)

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

        offset, decoded = self.conversion._decode_offer_sync(self.get_placeholder_msg(u"offer-sync"), 0, packet)

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

        offset, decoded = self.conversion._decode_accepted_trade(self.get_placeholder_msg(u"accepted-trade"), 0, packet)

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

        offset, decoded = self.conversion._decode_declined_trade(self.get_placeholder_msg(u"declined-trade"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.recipient_trader_id, TraderId('def'))

    def test_encode_decode_start_transaction(self):
        """
        Test encoding and decoding of a start transaction message
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"start-transaction")

        transaction_payload = StartTransactionPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                                     TraderId('def'), TransactionNumber(5),
                                                                     TraderId('def'),OrderNumber(3), TraderId('abc'),
                                                                     OrderNumber(4), Price(5, 'BTC'), Quantity(4, 'MC'),
                                                                     Timestamp.now())
        message.payload = transaction_payload
        packet, = self.conversion._encode_start_transaction(message)
        self.assertTrue(packet)

        offset, decoded = self.conversion._decode_start_transaction(
            self.get_placeholder_msg(u"start-transaction"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.transaction_trader_id, TraderId('def'))

    def test_encode_decode_transaction(self):
        """
        Test encoding and decoding of a transaction message
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"end-transaction")

        transaction_payload = TransactionPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                                TraderId('def'), TransactionNumber(5), Timestamp.now())
        message.payload = transaction_payload
        packet, = self.conversion._encode_transaction(message)
        self.assertTrue(packet)

        offset, decoded = self.conversion._decode_transaction(self.get_placeholder_msg(u"end-transaction"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.transaction_trader_id, TraderId('def'))

    def test_encode_decode_wallet_info(self):
        """
        Test encoding and decoding of wallet info
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"wallet-info")

        wallet_payload = WalletInfoPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                          TraderId('def'), TransactionNumber(5), WalletAddress('a'),
                                                          WalletAddress('b'), Timestamp.now())
        message.payload = wallet_payload
        packet, = self.conversion._encode_wallet_info(message)
        self.assertTrue(packet)

        offset, decoded = self.conversion._decode_wallet_info(self.get_placeholder_msg(u"wallet-info"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.transaction_trader_id, TraderId('def'))

    def test_encode_decode_payment(self):
        """
        Test encoding and decoding of a payment
        """
        message = MockObject()
        meta_msg = self.market_community.get_meta_message(u"payment")

        payment_payload = PaymentPayload.Implementation(meta_msg, TraderId('abc'), MessageNumber('3'),
                                                        TraderId('def'), TransactionNumber(5), Quantity(5, 'MC'),
                                                        Price(6, 'BTC'), WalletAddress('a'),
                                                        WalletAddress('b'), PaymentId('abc'), Timestamp.now())
        message.payload = payment_payload
        packet, = self.conversion._encode_payment(message)
        self.assertTrue(packet)

        offset, decoded = self.conversion._decode_payment(self.get_placeholder_msg(u"payment"), 0, packet)

        self.assertTrue(decoded)
        self.assertEqual(decoded.trader_id, TraderId('abc'))
        self.assertEqual(decoded.transaction_trader_id, TraderId('def'))
        self.assertEqual(decoded.payment_id, PaymentId('abc'))
