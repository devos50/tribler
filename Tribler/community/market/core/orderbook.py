from __future__ import absolute_import

import logging
import time
from binascii import unhexlify

from twisted.internet import reactor
from twisted.internet.defer import fail
from twisted.internet.task import deferLater
from twisted.python.failure import Failure

from Tribler.community.market.core.assetpair import AssetPair
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.side import Side
from Tribler.community.market.core.tick import Ask, Bid
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.pyipv8.ipv8.taskmanager import TaskManager
from Tribler.pyipv8.ipv8.util import old_round


class OrderBook(TaskManager):
    """
    OrderBook is used for searching through all the orders and giving an indication to the user of what other offers
    are out there.
    """

    def __init__(self):
        super(OrderBook, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self._bids = Side()
        self._asks = Side()
        self.completed_orders = set()

    def timeout_ask(self, order_id):
        ask = self.get_ask(order_id).tick
        self.remove_tick(order_id)
        return ask

    def timeout_bid(self, order_id):
        bid = self.get_bid(order_id).tick
        self.remove_tick(order_id)
        return bid

    def on_timeout_error(self, _):
        pass

    def on_invalid_tick_insert(self, _):
        self._logger.warning("Invalid tick inserted in order book.")

    def insert_ask(self, ask):
        """
        :type ask: Ask
        """
        if not self._asks.tick_exists(ask.order_id) and ask.order_id not in self.completed_orders and ask.is_valid():
            self._asks.insert_tick(ask)
            timeout_delay = int(ask.timestamp) + int(ask.timeout) * 1000 - int(old_round(time.time() * 1000))
            task = deferLater(reactor, timeout_delay, self.timeout_ask, ask.order_id)
            self.register_task("ask_%s_timeout" % ask.order_id, task)
            return task.addErrback(self.on_timeout_error)
        return fail(Failure(RuntimeError("ask invalid"))).addErrback(self.on_invalid_tick_insert)

    def remove_ask(self, order_id):
        """
        :type order_id: OrderId
        """
        if self._asks.tick_exists(order_id):
            self.cancel_pending_task("ask_%s_timeout" % order_id)
            self._asks.remove_tick(order_id)

    def insert_bid(self, bid):
        """
        :type bid: Bid
        """
        if not self._bids.tick_exists(bid.order_id) and bid.order_id not in self.completed_orders and bid.is_valid():
            self._bids.insert_tick(bid)
            timeout_delay = int(bid.timestamp) + int(bid.timeout) * 1000 - int(old_round(time.time() * 1000))
            task = deferLater(reactor, timeout_delay, self.timeout_bid, bid.order_id)
            self.register_task("bid_%s_timeout" % bid.order_id, task)
            return task.addErrback(self.on_timeout_error)
        return fail(Failure(RuntimeError("bid invalid"))).addErrback(self.on_invalid_tick_insert)

    def remove_bid(self, order_id):
        """
        :type order_id: OrderId
        """
        if self._bids.tick_exists(order_id):
            self.cancel_pending_task("bid_%s_timeout" % order_id)
            self._bids.remove_tick(order_id)

    def update_ticks(self, order_id1, order_id2, traded_quantity, trade_id, unreserve=True):
        """
        Update ticks according to a TrustChain block containing the status of the ask/bid orders.
        """
        self._logger.debug("Updating ticks in order book: %s and %s (traded quantity: %s), u? %s",
                           str(order_id1), str(order_id2), str(traded_quantity), unreserve)

        # Update ticks
        for order_id in [order_id1, order_id2]:
            tick_exists = self.tick_exists(order_id)
            if tick_exists:
                tick = self.get_tick(order_id)
                if trade_id in tick.trades:
                    if trade_id not in tick.unreserved_trades and unreserve:
                        tick.release_for_matching(traded_quantity)
                        tick.unreserved_trades.add(trade_id)
                    continue  # We already updated this tick
                tick.traded += traded_quantity
                tick.trades.add(trade_id)
                if unreserve:
                    tick.release_for_matching(traded_quantity)
                    tick.unreserved_trades.add(trade_id)
                if tick.traded >= tick.assets.first.amount:  # We completed the trade
                    self.remove_tick(tick.order_id)
                    self.completed_orders.add(tick.order_id)

    def tick_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the tick exists, False otherwise
        :rtype: bool
        """
        is_ask = self._asks.tick_exists(order_id)
        is_bid = self._bids.tick_exists(order_id)

        return is_ask or is_bid

    def get_ask(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :rtype: TickEntry
        """
        return self._asks.get_tick(order_id)

    def get_bid(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :rtype: TickEntry
        """
        return self._bids.get_tick(order_id)

    def get_tick(self, order_id):
        """
        Return a tick with the specified order id.
        :param order_id: The order id to search for
        :type order_id: OrderId
        :rtype: TickEntry
        """
        return self._bids.get_tick(order_id) or self._asks.get_tick(order_id)

    def ask_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the ask exists, False otherwise
        :rtype: bool
        """
        return self._asks.tick_exists(order_id)

    def bid_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the bid exists, False otherwise
        :rtype: bool
        """
        return self._bids.tick_exists(order_id)

    def remove_tick(self, order_id):
        """
        :type order_id: OrderId
        """
        self._logger.debug("Removing tick %s from order book", order_id)

        self.remove_ask(order_id)
        self.remove_bid(order_id)

    @property
    def asks(self):
        """
        Return the asks side
        :rtype: Side
        """
        return self._asks

    @property
    def bids(self):
        """
        Return the bids side
        :rtype: Side
        """
        return self._bids

    def get_bid_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price an ask needs to have to make a trade
        :rtype: Price
        """
        return self._bids.get_max_price(price_wallet_id, quantity_wallet_id)

    def get_ask_price(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price a bid needs to have to make a trade
        :rtype: Price
        """
        return self._asks.get_min_price(price_wallet_id, quantity_wallet_id)

    def get_bid_ask_spread(self, price_wallet_id, quantity_wallet_id):
        """
        Return the spread between the bid and the ask price
        :rtype: Price
        """
        spread = self.get_ask_price(price_wallet_id, quantity_wallet_id).amount - \
                 self.get_bid_price(price_wallet_id, quantity_wallet_id).amount
        return Price(spread, price_wallet_id, quantity_wallet_id)

    def bid_side_depth(self, price):
        """
        Return the depth of the price level with the given price on the bid side

        :param price: The price for the price level
        :type price: Price
        :return: The depth at that price level
        :rtype: Quantity
        """
        return self._bids.get_price_level(price).depth

    def ask_side_depth(self, price):
        """
        Return the depth of the price level with the given price on the ask side

        :param price: The price for the price level
        :type price: Price
        :return: The depth at that price level
        :rtype: Quantity
        """
        return self._asks.get_price_level(price).depth

    def get_bid_side_depth_profile(self, price_wallet_id, quantity_wallet_id):
        """
        format: [(<price>, <depth>), (<price>, <depth>), ...]

        :return: The depth profile
        :rtype: list
        """
        profile = []
        for price_level in self._bids.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
            profile.append((price_level.price, price_level.depth))
        return profile

    def get_ask_side_depth_profile(self, price_wallet_id, quantity_wallet_id):
        """
        format: [(<price>, <depth>), (<price>, <depth>), ...]

        :return: The depth profile
        :rtype: list
        """
        profile = []
        for price_level in self._asks.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
            profile.append((price_level.price, price_level.depth))
        return profile

    def get_bid_price_level(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price level that an ask has to match to make a trade
        :rtype: PriceLevel
        """
        return self._bids.get_max_price_list(price_wallet_id, quantity_wallet_id)

    def get_ask_price_level(self, price_wallet_id, quantity_wallet_id):
        """
        Return the price level that a bid has to match to make a trade
        :rtype: PriceLevel
        """
        return self._asks.get_min_price_list(price_wallet_id, quantity_wallet_id)

    def get_order_ids(self):
        """
        Return all IDs of the orders in the orderbook, both asks and bids.

        :rtype: [OrderId]
        """
        return self.get_bid_ids() + self.get_ask_ids()

    def get_ask_ids(self):
        ids = []

        for price_wallet_id, quantity_wallet_id in self.asks.get_price_level_list_wallets():
            for price_level in self.asks.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
                for ask in price_level:
                    ids.append(ask.tick.order_id)

        return ids

    def get_bid_ids(self):
        ids = []

        for price_wallet_id, quantity_wallet_id in self.bids.get_price_level_list_wallets():
            for price_level in self.bids.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
                for bid in price_level:
                    ids.append(bid.tick.order_id)

        return ids

    def __str__(self):
        res_str = ''
        res_str += "------ Bids -------\n"
        for price_wallet_id, quantity_wallet_id in self.bids.get_price_level_list_wallets():
            for price_level in self._bids.get_price_level_list(price_wallet_id, quantity_wallet_id).items(reverse=True):
                res_str += '%s' % price_level
        res_str += "\n------ Asks -------\n"
        for price_wallet_id, quantity_wallet_id in self.asks.get_price_level_list_wallets():
            for price_level in self._asks.get_price_level_list(price_wallet_id, quantity_wallet_id).items():
                res_str += '%s' % price_level
        res_str += "\n"
        return res_str

    def cancel_all_pending_tasks(self):
        super(OrderBook, self).cancel_all_pending_tasks()
        for order_id in self.get_order_ids():
            self.get_tick(order_id).cancel_all_pending_tasks()


class DatabaseOrderBook(OrderBook):
    """
    This class adds support for a persistency backend to store ticks.
    For now, it only provides methods to save all ticks to the database or to restore all ticks from the database.
    """
    def __init__(self, database):
        super(DatabaseOrderBook, self).__init__()
        self.database = database

    def save_to_database(self):
        """
        Write all ticks to the database
        """
        self.database.delete_all_ticks()
        for order_id in self.get_order_ids():
            tick = self.get_tick(order_id)
            if tick.is_valid():
                self.database.add_tick(tick.tick)

    def restore_from_database(self):
        """
        Restore ticks from the database
        """
        for tick in self.database.get_ticks():
            if not self.tick_exists(tick.order_id) and tick.is_valid():
                self.insert_ask(tick) if tick.is_ask() else self.insert_bid(tick)
