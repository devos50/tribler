from __future__ import absolute_import

import os

import six

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import Order, OrderId, OrderNumber
from Tribler.community.market.core.tick import Tick
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.database import LATEST_DB_VERSION, MarketDB


class TestDatabase(AbstractServer):

    @inlineCallbacks
    def setUp(self):
        yield super(TestDatabase, self).setUp()

        path = os.path.join(self.getStateDir(), 'sqlite')
        if not os.path.exists(path):
            os.makedirs(path)

        self.database = MarketDB(self.getStateDir(), 'market')

        self.order_id1 = OrderId(TraderId(b'3' * 20), OrderNumber(4))
        self.order_id2 = OrderId(TraderId(b'4' * 20), OrderNumber(5))
        self.order1 = Order(self.order_id1, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                            Timeout(3600), Timestamp.now(), True)
        self.order2 = Order(self.order_id2, AssetPair(AssetAmount(5, 'BTC'), AssetAmount(6, 'EUR')),
                            Timeout(3600), Timestamp.now(), False)
        self.order2.reserve_quantity_for_tick(OrderId(TraderId(b'3' * 20), OrderNumber(4)), 3)

    def test_add_get_order(self):
        """
        Test the insertion and retrieval of an order in the database
        """
        self.database.add_order(self.order1)
        self.database.add_order(self.order2)
        orders = self.database.get_all_orders()
        self.assertEqual(len(orders), 2)

    def test_get_specific_order(self):
        """
        Test the retrieval of a specific order
        """
        order_id = OrderId(TraderId(b'3' * 20), OrderNumber(4))
        self.assertIsNone(self.database.get_order(order_id))
        self.database.add_order(self.order1)
        self.assertIsNotNone(self.database.get_order(order_id))

    def test_delete_order(self):
        """
        Test the deletion of an order from the database
        """
        self.database.add_order(self.order1)
        self.assertEqual(len(self.database.get_all_orders()), 1)
        self.database.delete_order(self.order_id1)
        self.assertEqual(len(self.database.get_all_orders()), 0)

    def test_get_next_order_number(self):
        """
        Test the retrieval of the next order number from the database
        """
        self.assertEqual(self.database.get_next_order_number(), 1)
        self.database.add_order(self.order1)
        self.assertEqual(self.database.get_next_order_number(), 5)

    def test_add_delete_reserved_ticks(self):
        """
        Test the retrieval, addition and deletion of reserved ticks in the database
        """
        self.database.add_reserved_tick(self.order_id1, self.order_id2, self.order1.total_quantity)
        self.assertEqual(len(self.database.get_reserved_ticks(self.order_id1)), 1)
        self.database.delete_reserved_ticks(self.order_id1)
        self.assertEqual(len(self.database.get_reserved_ticks(self.order_id1)), 0)

    def test_add_remove_tick(self):
        """
        Test addition, retrieval and deletion of ticks in the database
        """
        ask = Tick.from_order(self.order1)
        self.database.add_tick(ask)
        bid = Tick.from_order(self.order2)
        self.database.add_tick(bid)

        self.assertEqual(len(self.database.get_ticks()), 2)

        self.database.delete_all_ticks()
        self.assertEqual(len(self.database.get_ticks()), 0)

    def test_check_database(self):
        """
        Test the check of the database
        """
        self.assertEqual(self.database.check_database(six.text_type(LATEST_DB_VERSION)), LATEST_DB_VERSION)

    def test_get_upgrade_script(self):
        """
        Test fetching the upgrade script of the database
        """
        self.assertTrue(self.database.get_upgrade_script(1))

    def test_db_upgrade(self):
        self.database.execute(u"DROP TABLE orders;")
        self.database.execute(u"DROP TABLE ticks;")
        self.database.execute(u"CREATE TABLE orders(x INTEGER PRIMARY KEY ASC);")
        self.database.execute(u"CREATE TABLE ticks(x INTEGER PRIMARY KEY ASC);")
        self.assertEqual(self.database.check_database(u"1"), 4)
