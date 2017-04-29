import os

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.database import MarketDB
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestDatabase(AbstractServer):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield super(TestDatabase, self).setUp(annotate=annotate)

        path = os.path.join(self.getStateDir(), 'sqlite')
        if not os.path.exists(path):
            os.makedirs(path)

        self.database = MarketDB(self.getStateDir())

        self.order_id1 = OrderId(TraderId('3'), OrderNumber(4))
        self.order1 = Order(self.order_id1, Price(5, 'EUR'), Quantity(6, 'BTC'), Timeout(3600), Timestamp.now(), True)

    @blocking_call_on_reactor_thread
    def test_add_get_order(self):
        """
        Test the insertion and retrieval of an order in the database
        """
        self.database.add_order(self.order1)
        orders = self.database.get_all_orders()
        self.assertEqual(len(orders), 1)

    @blocking_call_on_reactor_thread
    def test_get_specific_order(self):
        """
        Test the retrieval of a specific order
        """
        order_id = OrderId(TraderId('3'), OrderNumber(4))
        self.assertIsNone(self.database.get_order(order_id))
        self.database.add_order(self.order1)
        self.assertIsNotNone(self.database.get_order(order_id))

    @blocking_call_on_reactor_thread
    def test_delete_order(self):
        """
        Test the deletion of an order from the database
        """
        self.database.add_order(self.order1)
        self.assertEqual(len(self.database.get_all_orders()), 1)
        self.database.delete_order(self.order_id1)
        self.assertEqual(len(self.database.get_all_orders()), 0)

    @blocking_call_on_reactor_thread
    def test_get_next_order_number(self):
        """
        Test the retrieval of the next order number from the database
        """
        self.assertEqual(self.database.get_next_order_number(), 1)
        self.database.add_order(self.order1)
        self.assertEqual(self.database.get_next_order_number(), 5)

    @blocking_call_on_reactor_thread
    def test_add_get_trader_identity(self):
        """
        Test the addition and retrieval of a trader identity
        """
        self.database.add_trader_identity("a", "123", 1234)
        self.database.add_trader_identity("b", "124", 1235)
        traders = self.database.get_traders()
        self.assertEqual(len(traders), 2)
        self.assertEqual(traders, [("a", "123", 1234), ("b", "124", 1235)])
