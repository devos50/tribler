import unittest

from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Tick, Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp


class TickTestSuite(unittest.TestCase):
    """Tick test cases."""

    def setUp(self):
        # Object creation
        self.timestamp_now = Timestamp.now()
        self.tick = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                         OrderId(TraderId('0'), OrderNumber(1)), Price(63400, 'BTC'), Quantity(30, 'MC'),
                         Timeout(30), self.timestamp_now, True)
        self.tick2 = Tick(MessageId(TraderId('0'), MessageNumber('message_number')),
                          OrderId(TraderId('0'), OrderNumber(2)), Price(63400, 'BTC'), Quantity(30, 'MC'),
                          Timeout(0.0), Timestamp(0.0), False)
        self.order_ask = Order(OrderId(TraderId('0'), OrderNumber(2)), Price(63400, 'BTC'),
                               Quantity(30, 'MC'), Timeout(0.0), Timestamp(0.0), True)
        self.order_bid = Order(OrderId(TraderId('0'), OrderNumber(2)), Price(63400, 'BTC'),
                               Quantity(30, 'MC'), Timeout(0.0), Timestamp(0.0), False)

    def test_is_ask(self):
        # Test 'is ask' function
        self.assertTrue(self.tick.is_ask())
        self.assertFalse(self.tick2.is_ask())

    def test_is_valid(self):
        # Test for is valid
        self.assertTrue(self.tick.is_valid())
        self.assertFalse(self.tick2.is_valid())

    def test_to_network(self):
        # Test for to network
        self.assertEquals((TraderId('0'), MessageNumber('message_number'), OrderNumber(1),
                           Price(63400, 'BTC'), Quantity(30, 'MC'), self.tick.timeout, self.tick.timestamp),
                          self.tick.to_network())

    def test_quantity_setter(self):
        # Test for quantity setter
        self.tick.quantity = Quantity(60, 'MC')
        self.assertEqual(Quantity(60, 'MC'), self.tick.quantity)

    def test_from_order_ask(self):
        # Test for from order
        ask = Tick.from_order(self.order_ask, MessageId(TraderId('0'), MessageNumber('message_number')))
        self.assertIsInstance(ask, Ask)
        self.assertEqual(self.tick2.price, ask.price)
        self.assertEqual(self.tick2.quantity, ask.quantity)
        self.assertEqual(self.tick2.timestamp, ask.timestamp)
        self.assertEqual(self.tick2.order_id, ask.order_id)
        self.assertEqual(self.tick2.message_id, ask.message_id)

    def test_from_order_bid(self):
        # Test for from order
        bid = Tick.from_order(self.order_bid, MessageId(TraderId('0'), MessageNumber('message_number')))
        self.assertIsInstance(bid, Bid)
        self.assertEqual(self.tick2.price, bid.price)
        self.assertEqual(self.tick2.quantity, bid.quantity)
        self.assertEqual(self.tick2.timestamp, bid.timestamp)
        self.assertEqual(self.tick2.order_id, bid.order_id)
        self.assertEqual(self.tick2.message_id, bid.message_id)

    def test_to_dictionary(self):
        """
        Test the to dictionary method of a tick
        """
        self.assertDictEqual(self.tick.to_dictionary(), {
            "trader_id": '0',
            "message_id": "0.message_number",
            "order_number": 1,
            "price": 63400.0,
            "price_type": "BTC",
            "quantity": 30.0,
            "quantity_type": "MC",
            "timeout": 30.0,
            "timestamp": float(self.timestamp_now),
        })


class AskTestSuite(unittest.TestCase):
    """Ask test cases."""

    def test_from_network(self):
        # Test for from network
        now = Timestamp.now()
        data = Ask.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                         "order_number": OrderNumber(1),
                                                         "message_number": MessageNumber('message_number'),
                                                         "price": Price(63400, 'BTC'),
                                                         "quantity": Quantity(30, 'MC'),
                                                         "timeout": Timeout(30),
                                                         "timestamp": now}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(Price(63400, 'BTC'), data.price)
        self.assertEquals(Quantity(30, 'MC'), data.quantity)
        self.assertEquals(float(Timeout(30)), float(data.timeout))
        self.assertEquals(now, data.timestamp)


class BidTestSuite(unittest.TestCase):
    """Bid test cases."""

    def test_from_network(self):
        # Test for from network
        now = Timestamp.now()
        data = Bid.from_network(type('Data', (object,), {"trader_id": TraderId('0'),
                                                         "order_number": OrderNumber(2),
                                                         "message_number": MessageNumber('message_number'),
                                                         "price": Price(63400, 'BTC'),
                                                         "quantity": Quantity(40, 'MC'),
                                                         "timeout": Timeout(30),
                                                         "timestamp": now}))

        self.assertEquals(MessageId(TraderId('0'), MessageNumber('message_number')), data.message_id)
        self.assertEquals(Price(63400, 'BTC'), data.price)
        self.assertEquals(Quantity(40, 'MC'), data.quantity)
        self.assertEquals(float(Timeout(30)), float(data.timeout))
        self.assertEquals(now, data.timestamp)


if __name__ == '__main__':
    unittest.main()
