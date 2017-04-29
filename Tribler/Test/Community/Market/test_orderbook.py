import unittest

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId
from Tribler.community.market.core.message_repository import MemoryMessageRepository
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.orderbook import OrderBook
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import Trade



class OrderBookTestSuite(AbstractServer):
    """OrderBook test cases."""

    def setUp(self, annotate=True):
        super(OrderBookTestSuite, self).setUp(annotate=annotate)
        # Object creation
        self.ask = Ask(MessageId(TraderId('0'), MessageNumber('message_number')),
                       OrderId(TraderId('0'), OrderNumber(1)), Price(100, 'BTC'), Quantity(30, 'MC'),
                       Timeout(1462224447.117), Timestamp(1462224447.117))
        self.ask2 = Ask(MessageId(TraderId('1'), MessageNumber('message_number')),
                        OrderId(TraderId('1'), OrderNumber(1)), Price(400, 'BTC'), Quantity(30, 'MC'),
                        Timeout(1462224447.117), Timestamp(1462224447.117))
        self.bid = Bid(MessageId(TraderId('2'), MessageNumber('message_number')),
                       OrderId(TraderId('2'), OrderNumber(1)), Price(200, 'BTC'), Quantity(30, 'MC'),
                       Timeout(1462224447.117), Timestamp(1462224447.117))
        self.bid2 = Bid(MessageId(TraderId('3'), MessageNumber('message_number')),
                        OrderId(TraderId('3'), OrderNumber(1)), Price(300, 'BTC'), Quantity(30, 'MC'),
                        Timeout(1462224447.117), Timestamp(1462224447.117))
        self.trade = Trade.propose(MessageId(TraderId('0'), MessageNumber('message_number')),
                                   OrderId(TraderId('0'), OrderNumber(1)),
                                   OrderId(TraderId('0'), OrderNumber(1)), Price(100, 'BTC'),
                                   Quantity(30, 'MC'), Timestamp(1462224447.117))
        self.order_book = OrderBook(MemoryMessageRepository('0'))

    def tearDown(self, annotate=True):
        self.order_book.cancel_all_pending_tasks()
        super(OrderBookTestSuite, self).tearDown(annotate=annotate)

    def test_ask_insertion(self):
        # Test for ask insertion
        self.order_book.insert_ask(self.ask2)
        self.assertTrue(self.order_book.tick_exists(self.ask2.order_id))
        self.assertTrue(self.order_book.ask_exists(self.ask2.order_id))
        self.assertFalse(self.order_book.bid_exists(self.ask2.order_id))
        self.assertEquals(self.ask2, self.order_book.get_ask(self.ask2.order_id)._tick)

    def test_ask_removal(self):
        # Test for ask removal
        self.order_book.insert_ask(self.ask2)
        self.assertTrue(self.order_book.tick_exists(self.ask2.order_id))
        self.order_book.remove_ask(self.ask2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.ask2.order_id))

    def test_bid_insertion(self):
        # Test for bid insertion
        self.order_book.insert_bid(self.bid2)
        self.assertTrue(self.order_book.tick_exists(self.bid2.order_id))
        self.assertTrue(self.order_book.bid_exists(self.bid2.order_id))
        self.assertFalse(self.order_book.ask_exists(self.bid2.order_id))
        self.assertEquals(self.bid2, self.order_book.get_bid(self.bid2.order_id)._tick)

    def test_bid_removal(self):
        # Test for bid removal
        self.order_book.insert_bid(self.bid2)
        self.assertTrue(self.order_book.tick_exists(self.bid2.order_id))
        self.order_book.remove_bid(self.bid2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.bid2.order_id))

    def test_trade_insertion(self):
        # Test for trade insertion
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)

    def test_properties(self):
        # Test for properties
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Price(350, 'BTC'), self.order_book.mid_price)
        self.assertEquals(Price(100, 'BTC'), self.order_book.bid_ask_spread)

    def test_tick_price(self):
        # Test for tick price
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Price(300, 'BTC'), self.order_book.relative_tick_price(self.ask))
        self.assertEquals(Price(100, 'BTC'), self.order_book.relative_tick_price(self.bid))

    def test_bid_ask_price_level(self):
        self.order_book.insert_ask(self.ask)
        self.assertEquals('30.000000 MC\t@\t100.000000 BTC\n', str(self.order_book.ask_price_level))

    def test_bid_price_level(self):
        # Test for tick price
        self.order_book.insert_bid(self.bid2)
        self.assertEquals('30.000000 MC\t@\t300.000000 BTC\n', str(self.order_book.bid_price_level))

    def test_ask_side_depth(self):
        # Test for ask side depth
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_ask(self.ask2)
        self.assertEquals(Quantity(30, 'MC'), self.order_book.ask_side_depth(Price(100, 'BTC')))
        self.assertEquals([(Price(100, 'BTC'), Quantity(30, 'MC')), (Price(400, 'BTC'), Quantity(30, 'MC'))],
                          self.order_book.ask_side_depth_profile)

    def test_bid_side_depth(self):
        # Test for bid side depth
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_bid(self.bid2)
        self.assertEquals(Quantity(30, 'MC'), self.order_book.bid_side_depth(Price(300, 'BTC')))
        self.assertEquals([(Price(200, 'BTC'), Quantity(30, 'MC')), (Price(300, 'BTC'), Quantity(30, 'MC'))],
                          self.order_book.bid_side_depth_profile)

    def test_remove_tick(self):
        # Test for tick removal
        self.order_book.insert_ask(self.ask2)
        self.order_book.insert_bid(self.bid2)
        self.order_book.remove_tick(self.ask2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.ask2.order_id))
        self.order_book.remove_tick(self.bid2.order_id)
        self.assertFalse(self.order_book.tick_exists(self.bid2.order_id))

    def test_str(self):
        # Test for order book string representation
        self.order_book.insert_ask(self.ask)
        self.order_book.insert_bid(self.bid)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)
        self.order_book.insert_trade(self.trade)

        self.assertEquals('------ Bids -------\n'
                          '30.000000 MC\t@\t200.000000 BTC\n\n'
                          '------ Asks -------\n'
                          '30.000000 MC\t@\t100.000000 BTC\n\n'
                          '------ Trades ------\n'
                          '30.000000 MC @ 100.000000 BTC (2016-05-02 23:27:27.117000)\n'
                          '30.000000 MC @ 100.000000 BTC (2016-05-02 23:27:27.117000)\n'
                          '30.000000 MC @ 100.000000 BTC (2016-05-02 23:27:27.117000)\n'
                          '30.000000 MC @ 100.000000 BTC (2016-05-02 23:27:27.117000)\n'
                          '30.000000 MC @ 100.000000 BTC (2016-05-02 23:27:27.117000)\n\n', str(self.order_book))


if __name__ == '__main__':
    unittest.main()
