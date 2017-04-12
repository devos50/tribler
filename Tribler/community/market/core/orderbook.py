import logging
from collections import deque

import time

from twisted.internet import reactor
from twisted.internet.defer import fail
from twisted.internet.task import deferLater
from twisted.python.failure import Failure

from Tribler.dispersy.taskmanager import TaskManager
from message import Message
from message_repository import MessageRepository
from order import OrderId
from price import Price
from quantity import Quantity
from side import Side
from tick import Tick, Ask, Bid
from timestamp import Timestamp
from trade import Trade, AcceptedTrade


class OrderBook(TaskManager):
    """
    OrderBook is used for searching through all the orders and giving an indication to the user of what other offers
    are out there.
    """

    def __init__(self, message_repository):
        super(OrderBook, self).__init__()
        self._logger = logging.getLogger(self.__class__.__name__)

        assert isinstance(message_repository, MessageRepository), type(message_repository)

        self.message_repository = message_repository
        self._trades = deque(maxlen=100)  # List of trades with a limit of 100
        self._bids = Side()
        self._asks = Side()
        self._last_message = None  # The last message processed by this order book
        self._last_timestamp = Timestamp(0.0)  # The time at which the last message was processed

    def _process_message(self, message):
        """
        Process a message that is passed to this order book
        """
        assert isinstance(message, Message), type(message)

        if message.timestamp > self._last_timestamp:
            self._last_timestamp = message.timestamp
        self._last_message = message

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

    def insert_ask(self, ask):
        """
        :type ask: Ask
        """
        assert isinstance(ask, Ask), type(ask)

        self._process_message(ask)

        if not self._asks.tick_exists(ask.order_id) and ask.is_valid():
            self._asks.insert_tick(ask)
            timeout_delay = float(ask.timestamp) + float(ask.timeout) - time.time()
            task = deferLater(reactor, timeout_delay, self.timeout_ask, ask.order_id)
            self.register_task("ask_%s_timeout" % ask.order_id, task)
            return task.addErrback(self.on_timeout_error)
        return fail(Failure(RuntimeError("ask invalid")))

    def remove_ask(self, order_id):
        """
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

        if self._asks.tick_exists(order_id):
            self.cancel_pending_task("ask_%s_timeout" % order_id)
            self._asks.remove_tick(order_id)

    def insert_bid(self, bid):
        """
        :type bid: Bid
        """
        assert isinstance(bid, Bid), type(bid)

        self._process_message(bid)

        if not self._bids.tick_exists(bid.order_id) and bid.is_valid():
            self._bids.insert_tick(bid)
            timeout_delay = float(bid.timestamp) + float(bid.timeout) - time.time()
            task = deferLater(reactor, timeout_delay, self.timeout_bid, bid.order_id)
            self.register_task("bid_%s_timeout" % bid.order_id, task)
            return task.addErrback(self.on_timeout_error)
        return fail(Failure(RuntimeError("bid invalid")))

    def remove_bid(self, order_id):
        """
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

        if self._bids.tick_exists(order_id):
            self.cancel_pending_task("bid_%s_timeout" % order_id)
            self._bids.remove_tick(order_id)

    def trade_tick(self, order_id, recipient_order_id, quantity):
        """
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type quantity: Quantity
        """
        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(recipient_order_id, OrderId), type(recipient_order_id)
        assert isinstance(quantity, Quantity), type(quantity)
        self._logger.debug("Trading tick in order book for own order %s vs order %s",
                           str(order_id), str(recipient_order_id))

        if self.bid_exists(order_id):
            tick = self.get_bid(order_id)
            tick.quantity -= quantity
            if tick.quantity == Quantity(0, quantity.wallet_id):
                self.remove_tick(tick.order_id)
        if self.ask_exists(order_id):
            tick = self.get_ask(order_id)
            tick.quantity -= quantity
            if tick.quantity == Quantity(0, quantity.wallet_id):
                self.remove_tick(tick.order_id)
        if self.bid_exists(recipient_order_id):
            tick = self.get_bid(recipient_order_id)
            tick.quantity -= quantity
            if tick.quantity == Quantity(0, quantity.wallet_id):
                self.remove_tick(tick.order_id)
        if self.ask_exists(recipient_order_id):
            tick = self.get_ask(recipient_order_id)
            tick.quantity -= quantity
            if tick.quantity == Quantity(0, quantity.wallet_id):
                self.remove_tick(tick.order_id)

    def insert_trade(self, trade):
        """
        :type trade: Trade
        """
        assert isinstance(trade, Trade), type(trade)

        self._process_message(trade)

        self._trades.appendleft(trade)

    def tick_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the tick exists, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)

        is_ask = self._asks.tick_exists(order_id)
        is_bid = self._bids.tick_exists(order_id)

        return is_ask or is_bid

    def get_ask(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :rtype: TickEntry
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._asks.get_tick(order_id)

    def get_bid(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :rtype: TickEntry
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._bids.get_tick(order_id)

    def ask_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the ask exists, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._asks.tick_exists(order_id)

    def bid_exists(self, order_id):
        """
        :param order_id: The order id to search for
        :type order_id: OrderId
        :return: True if the bid exists, False otherwise
        :rtype: bool
        """
        assert isinstance(order_id, OrderId), type(order_id)

        return self._bids.tick_exists(order_id)

    def remove_tick(self, order_id):
        """
        :type order_id: OrderId
        """
        assert isinstance(order_id, OrderId), type(order_id)

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

    @property
    def bid_price(self):
        """
        Return the price an ask needs to have to make a trade
        :rtype: Price
        """
        return self._bids.max_price

    @property
    def ask_price(self):
        """
        Return the price a bid needs to have to make a trade
        :rtype: Price
        """
        return self._asks.min_price

    @property
    def bid_ask_spread(self):
        """
        Return the spread between the bid and the ask price
        :rtype: Price
        """
        return self.ask_price - self.bid_price

    @property
    def mid_price(self):
        """
        Return the price in between the bid and the ask price
        :rtype: Price
        """
        return Price((int(self.ask_price) + int(self.bid_price)) / 2)

    def bid_side_depth(self, price):
        """
        Return the depth of the price level with the given price on the bid side

        :param price: The price for the price level
        :type price: Price
        :return: The depth at that price level
        :rtype: Quantity
        """
        assert isinstance(price, Price), type(price)
        return self._bids.get_price_level(price).depth

    def ask_side_depth(self, price):
        """
        Return the depth of the price level with the given price on the ask side

        :param price: The price for the price level
        :type price: Price
        :return: The depth at that price level
        :rtype: Quantity
        """
        assert isinstance(price, Price), type(price)
        return self._asks.get_price_level(price).depth

    @property
    def bid_side_depth_profile(self):
        """
        format: [(<price>, <depth>), (<price>, <depth>), ...]

        :return: The depth profile
        :rtype: list
        """
        profile = []
        for key, value in self._bids._price_level_list.items():
            profile.append((key, value.depth))
        return profile

    @property
    def ask_side_depth_profile(self):
        """
        format: [(<price>, <depth>), (<price>, <depth>), ...]

        :return: The depth profile
        :rtype: list
        """
        profile = []
        for key, value in self._asks._price_level_list.items():
            profile.append((key, value.depth))
        return profile

    def bid_relative_price(self, price):
        """
        :param price: The price to be relative to
        :type price: Price
        :return: The relative price
        :rtype: Price
        """
        assert isinstance(price, Price), type(price)
        return self.bid_price - price

    def ask_relative_price(self, price):
        """
        :param price: The price to be relative to
        :type price: Price
        :return: The relative price
        :rtype: Price
        """
        assert isinstance(price, Price), type(price)
        return self.ask_price - price

    def relative_tick_price(self, tick):
        """
        :param tick: The tick with the price to be relative to
        :type tick: Tick
        :return: The relative price
        :rtype: Price
        """
        assert isinstance(tick, Tick), type(tick)

        if tick.is_ask():
            return self.ask_relative_price(tick.price)
        else:
            return self.bid_relative_price(tick.price)

    @property
    def bid_price_level(self):
        """
        Return the price level that an ask has to match to make a trade
        :rtype: PriceLevel
        """
        return self._bids.max_price_list

    @property
    def ask_price_level(self):
        """
        Return the price level that a bid has to match to make a trade
        :rtype: PriceLevel
        """
        return self._asks.min_price_list

    def get_order_ids(self):
        """
        Return all IDs of the orders in the orderbook, both asks and bids. The returned list is sorted.

        :rtype: [OrderId]
        """
        ids = []

        for _, price_level in self.asks.price_level_list.items():
            for ask in price_level:
                ids.append(ask.tick.order_id)

        for _, price_level in self.bids.price_level_list.items():
            for bid in price_level:
                ids.append(bid.tick.order_id)

        return sorted(ids)

    def __str__(self):
        from cStringIO import StringIO

        tempfile = StringIO()
        tempfile.write("------ Bids -------\n")
        if self._bids is not None and len(self._bids) > 0:
            for key, value in self._bids._price_level_list.items(reverse=True):
                tempfile.write('%s' % value)
        tempfile.write("\n------ Asks -------\n")
        if self._asks is not None and len(self._asks) > 0:
            for key, value in self._asks._price_level_list.items():
                tempfile.write('%s' % value)
        tempfile.write("\n------ Trades ------\n")
        if self._trades is not None and len(self._trades) > 0:
            num = 0
            for entry in self._trades:
                if num < 5:
                    tempfile.write(
                        str(entry.quantity) + " @ " + str(entry.price) + " (" + str(entry.timestamp) + ")\n")
                    num += 1
                else:
                    break
        tempfile.write("\n")
        return tempfile.getvalue()
