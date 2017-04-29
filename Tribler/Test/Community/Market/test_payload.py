import unittest

from Tribler.community.market.core.message import TraderId, MessageNumber
from Tribler.community.market.core.order import OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionNumber
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.payload import AcceptedTradePayload, DeclinedTradePayload, TradePayload, \
    OfferPayload, StartTransactionPayload, PaymentPayload
from Tribler.community.market.ttl import Ttl
from Tribler.dispersy.meta import MetaObject


class AcceptedTradePayloadTestSuite(unittest.TestCase):
    """Accepted trade payload test cases."""

    def setUp(self):
        # Object creation
        self.accepted_trade_payload = AcceptedTradePayload.Implementation(MetaObject(), TraderId('0'),
                                                                          MessageNumber('message_number'),
                                                                          OrderNumber(1), TraderId('1'),
                                                                          OrderNumber(2),
                                                                          Price(63400, 'BTC'), Quantity(30, 'MC'),
                                                                          Timestamp(1462224447.117), Ttl(2),
                                                                          '192.168.1.1', 1234)

    def test_properties(self):
        # Test for properties
        self.assertEquals(Price(63400, 'BTC'), self.accepted_trade_payload.price)
        self.assertEquals(Quantity(30, 'MC'), self.accepted_trade_payload.quantity)
        self.assertEquals(MessageNumber('message_number'), self.accepted_trade_payload.message_number)
        self.assertEquals(OrderNumber(1), self.accepted_trade_payload.order_number)
        self.assertEquals(OrderNumber(2), self.accepted_trade_payload.recipient_order_number)
        self.assertEquals(TraderId('1'), self.accepted_trade_payload.recipient_trader_id)
        self.assertEquals(Timestamp(1462224447.117), self.accepted_trade_payload.timestamp)
        self.assertEquals(2, int(self.accepted_trade_payload.ttl))
        self.assertEquals(TraderId('0'), self.accepted_trade_payload.trader_id)


class DeclinedTradePayloadTestSuite(unittest.TestCase):
    """Declined trade payload test cases."""

    def setUp(self):
        # Object creation
        self.declined_trade_payload = DeclinedTradePayload.Implementation(MetaObject(), TraderId('0'),
                                                                          MessageNumber('message_number'),
                                                                          OrderNumber(1), TraderId('1'),
                                                                          OrderNumber(2),
                                                                          Timestamp(1462224447.117))

    def test_properties(self):
        # Test for properties
        self.assertEquals(MessageNumber('message_number'), self.declined_trade_payload.message_number)
        self.assertEquals(OrderNumber(1), self.declined_trade_payload.order_number)
        self.assertEquals(OrderNumber(2), self.declined_trade_payload.recipient_order_number)
        self.assertEquals(TraderId('1'), self.declined_trade_payload.recipient_trader_id)
        self.assertEquals(Timestamp(1462224447.117), self.declined_trade_payload.timestamp)
        self.assertEquals(TraderId('0'), self.declined_trade_payload.trader_id)


class ProposedTradePayloadTestSuite(unittest.TestCase):
    """Proposed trade payload test cases."""

    def setUp(self):
        # Object creation
        self.proposed_trade_payload = TradePayload.Implementation(MetaObject(), TraderId('0'),
                                                                  MessageNumber('message_number'),
                                                                  OrderNumber(1), TraderId('1'),
                                                                  OrderNumber(2),
                                                                  Price(63400, 'BTC'), Quantity(30, 'MC'),
                                                                  Timestamp(1462224447.117), '192.168.1.1', 1234)

    def test_properties(self):
        # Test for properties
        self.assertEquals(Price(63400, 'BTC'), self.proposed_trade_payload.price)
        self.assertEquals(Quantity(30, 'MC'), self.proposed_trade_payload.quantity)
        self.assertEquals(MessageNumber('message_number'), self.proposed_trade_payload.message_number)
        self.assertEquals(OrderNumber(1), self.proposed_trade_payload.order_number)
        self.assertEquals(OrderNumber(2), self.proposed_trade_payload.recipient_order_number)
        self.assertEquals(TraderId('1'), self.proposed_trade_payload.recipient_trader_id)
        self.assertEquals(Timestamp(1462224447.117), self.proposed_trade_payload.timestamp)
        self.assertEquals(TraderId('0'), self.proposed_trade_payload.trader_id)


class OfferPayloadTestSuite(unittest.TestCase):
    """Offer payload test cases."""

    def setUp(self):
        # Object creation
        self.offer_payload = OfferPayload.Implementation(MetaObject(), TraderId('0'), MessageNumber('message_number'),
                                                         OrderNumber(1), Price(63400, 'BTC'),
                                                         Quantity(30, 'MC'), Timeout(1470004447.117),
                                                         Timestamp(1462224447.117), Ttl(2), "1.1.1.1", 1)

    def test_properties(self):
        # Test for properties
        self.assertEquals(Price(63400, 'BTC'), self.offer_payload.price)
        self.assertEquals(Quantity(30, 'MC'), self.offer_payload.quantity)
        self.assertEquals(MessageNumber('message_number'), self.offer_payload.message_number)
        self.assertEquals(OrderNumber(1), self.offer_payload.order_number)
        self.assertEquals(1470004447.117, float(self.offer_payload.timeout))
        self.assertEquals(Timestamp(1462224447.117), self.offer_payload.timestamp)
        self.assertEquals(2, int(self.offer_payload.ttl))
        self.assertEquals(TraderId('0'), self.offer_payload.trader_id)
        self.assertEquals(1, self.offer_payload.address.port)
        self.assertEquals("1.1.1.1", self.offer_payload.address.ip)


class StartTransactionPayloadTestSuite(unittest.TestCase):
    """Start tranasaction payload test cases."""

    def setUp(self):
        # Object creation
        self.start_transaction_payload = StartTransactionPayload.Implementation(MetaObject(), TraderId('0'),
                                                                                MessageNumber('1'), TraderId('2'),
                                                                                TransactionNumber(2), TraderId('2'),
                                                                                OrderNumber(3), TraderId('0'),
                                                                                OrderNumber(4), Price(2, 'BTC'),
                                                                                Quantity(3, 'MC'), Timestamp(0.0))

    def test_properties(self):
        # Test for properties
        self.assertEquals(MessageNumber('1'), self.start_transaction_payload.message_number)
        self.assertEquals(TransactionNumber(2), self.start_transaction_payload.transaction_number)
        self.assertEquals(Timestamp(0.0), self.start_transaction_payload.timestamp)


class PaymentPayloadTestSuite(unittest.TestCase):
    """Payment payload test cases."""

    def setUp(self):
        # Object creation
        self.payment_payload = PaymentPayload.Implementation(MetaObject(), TraderId('0'),
                                                                            MessageNumber('1'),
                                                                            TraderId('2'),
                                                                            TransactionNumber(2),
                                                                            Quantity(20, 'MC'),
                                                                            Price(10, 'BTC'),
                                                                            WalletAddress('a'),
                                                                            WalletAddress('b'),
                                                                            PaymentId('3'),
                                                                            Timestamp(0.0))

    def test_properties(self):
        # Test for properties
        self.assertEquals(MessageNumber('1'), self.payment_payload.message_number)
        self.assertEquals(TransactionNumber(2), self.payment_payload.transaction_number)
        self.assertEquals(10, int(self.payment_payload.transferee_price))
        self.assertEquals('3', str(self.payment_payload.payment_id))
        self.assertEquals(Timestamp(0.0), self.payment_payload.timestamp)


if __name__ == '__main__':
    unittest.main()
