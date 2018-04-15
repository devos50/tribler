import time

from Tribler.community.market.core.message import TraderId, MessageNumber, MessageId, Message
from Tribler.community.market.core.order import OrderId, OrderNumber, Order
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.pyipv8.ipv8.attestation.trustchain.block import GENESIS_HASH


class Tick(object):
    """
    Abstract tick class for representing a order on another node. This tick is replicating the order sitting on
    the node it belongs to.
    """
    TIME_TOLERANCE = 10  # A small tolerance for the timestamp, to account for network delays

    def __init__(self, order_id, latitude, longitude, quantity, timeout, timestamp, is_ask, block_hash=GENESIS_HASH):
        """
        Don't use this class directly, use one of the class methods

        :param order_id: A order id to identify the order this tick represents
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param timeout: A timeout when this tick is going to expire
        :param timestamp: A timestamp when the tick was created
        :param is_ask: A bool to indicate if this tick is an ask
        :param block_hash: The hash of the block that created this tick
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type is_ask: bool
        :type block_hash: str
        """
        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(latitude, float), type(latitude)
        assert isinstance(longitude, float), type(longitude)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)
        assert isinstance(timestamp, Timestamp), type(timestamp)
        assert isinstance(is_ask, bool), type(is_ask)
        assert isinstance(block_hash, str), type(block_hash)

        self._order_id = order_id
        self._latitude = latitude
        self._longitude = longitude
        self._quantity = quantity
        self._timeout = timeout
        self._timestamp = timestamp
        self._is_ask = is_ask
        self._block_hash = block_hash

    @classmethod
    def from_database(cls, data):
        trader_id, order_number, price, price_type, quantity, quantity_type, timeout, timestamp,\
        is_ask, block_hash = data

        tick_cls = Ask if is_ask else Bid
        order_id = OrderId(TraderId(str(trader_id)), OrderNumber(order_number))
        return tick_cls(order_id, Price(price, str(price_type)), Quantity(quantity, str(quantity_type)),
                        Timeout(timeout), Timestamp(timestamp), block_hash=str(block_hash))

    def to_database(self):
        return (unicode(self.order_id.trader_id), int(self.order_id.order_number), float(self.price),
                unicode(self.price.wallet_id), float(self.quantity), unicode(self.quantity.wallet_id),
                float(self.timeout), float(self.timestamp), self.is_ask(), buffer(self.block_hash))

    @classmethod
    def from_order(cls, order):
        """
        Create a tick from an order

        :param order: The order that this tick represents
        :return: The created tick
        :rtype: Tick
        """
        assert isinstance(order, Order), type(order)

        if order.is_ask():
            return Ask(order.order_id, order.latitude, order.longitude, order.total_quantity - order.traded_quantity,
                       order.timeout, order.timestamp)
        else:
            return Bid(order.order_id, order.latitude, order.longitude, order.total_quantity - order.traded_quantity,
                       order.timeout, order.timestamp)

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._order_id

    @property
    def latitude(self):
        """
        :rtype: float
        """
        return self._latitude

    @property
    def longitude(self):
        """
        :rtype: float
        """
        return self._longitude

    @property
    def quantity(self):
        """
        :rtype: Quantity
        """
        return self._quantity

    @quantity.setter
    def quantity(self, quantity):
        """
        :param quantity: The new quantity
        :type quantity: Quantity
        """
        assert isinstance(quantity, Quantity), type(quantity)
        self._quantity = quantity

    @property
    def timeout(self):
        """
        Return when the tick is going to expire
        :rtype: Timeout
        """
        return self._timeout

    @property
    def timestamp(self):
        """
        Return the timestamp of the order
        :rtype: Timestamp
        """
        return self._timestamp

    def is_ask(self):
        """
        :return: True if this tick is an ask, False otherwise
        :rtype: bool
        """
        return self._is_ask

    @property
    def block_hash(self):
        """
        Return the hash of the associated block
        :rtype str
        """
        return self._block_hash

    @block_hash.setter
    def block_hash(self, new_hash):
        """
        :param new_hash: The new block hash
        :type new_hash: str
        """
        assert isinstance(new_hash, str), type(new_hash)
        self._block_hash = new_hash

    def is_valid(self):
        """
        :return: True if valid, False otherwise
        :rtype: bool
        """
        return not self._timeout.is_timed_out(self._timestamp) and \
            time.time() >= float(self.timestamp) - self.TIME_TOLERANCE

    def to_network(self, message_id):
        """
        Return network representation of the tick
        """
        return (
            MessageId(self._order_id.trader_id, message_id.message_number),
            self._timestamp,
            self._order_id.order_number,
            self._latitude,
            self._longitude,
            self._quantity,
            self._timeout,
        )

    def to_block_dict(self):
        """
        Return a block dictionary representation of the tick, will be stored on the TradeChain
        """
        return {
            "trader_id": str(self.order_id.trader_id),
            "order_number": int(self.order_id.order_number),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "quantity": float(self.quantity),
            "quantity_type": self.quantity.wallet_id,
            "timeout": float(self.timeout),
            "timestamp": float(self.timestamp),
            "is_ask": self.is_ask()
        }

    def to_dictionary(self):
        """
        Return a dictionary with a representation of this tick.
        """
        return {
            "trader_id": str(self.order_id.trader_id),
            "order_number": int(self.order_id.order_number),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "quantity": float(self.quantity),
            "quantity_type": self.quantity.wallet_id,
            "timeout": float(self.timeout),
            "timestamp": float(self.timestamp),
            "block_hash": self.block_hash.encode('hex')
        }

    def __str__(self):
        """
        Return the string representation of this tick.
        """
        return "<%s La: %f, Ln: %f, Q: %s, O: %s>" % \
               (self.__class__.__name__, self.latitude, self.longitude, str(self.quantity), str(self.order_id))


class Ask(Tick):
    """Represents an ask from a order located on another node."""

    def __init__(self, order_id, latitude, longitude, quantity, timeout, timestamp, block_hash=GENESIS_HASH):
        """
        :param order_id: A order id to identify the order this tick represents
        :param quantity: The quantity that needs to be sold
        :param timeout: A timeout for the ask
        :param timestamp: A timestamp for when the ask was created
        :param block_hash: The hash of the block that created this tick
        :type order_id: OrderId
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type block_hash: str
        """
        super(Ask, self).__init__(order_id, latitude, longitude, quantity, timeout, timestamp, True, block_hash=block_hash)

    @classmethod
    def from_block(cls, block):
        """
        Restore an ask from a TradeChain block

        :param data: TradeChainBlock
        :return: Restored ask
        :rtype: Ask
        """
        tx_dict = block.transaction["tick"]
        return cls(
            OrderId(TraderId(tx_dict["trader_id"]), OrderNumber(tx_dict["order_number"])),
            tx_dict["latitude"], tx_dict["longitude"],
            Quantity(tx_dict["quantity"], tx_dict["quantity_type"]),
            Timeout(tx_dict["timeout"]),
            Timestamp(tx_dict["timestamp"]),
            block_hash=block.hash
        )


class Bid(Tick):
    """Represents a bid from a order located on another node."""

    def __init__(self, order_id, latitude, longitude, quantity, timeout, timestamp, block_hash=GENESIS_HASH):
        """
        :param order_id: A order id to identify the order this tick represents
        :param quantity: The quantity that you want to buy
        :param timeout: A timeout for the bid
        :param timestamp: A timestamp for when the bid was created
        :param block_hash: The hash of the block that created this tick
        :type order_id: OrderId
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        :type block_hash: str
        """
        super(Bid, self).__init__(order_id, latitude, longitude, quantity, timeout, timestamp, False, block_hash=block_hash)

    @classmethod
    def from_block(cls, block):
        """
        Restore a bid from a TradeChain block

        :param data: TradeChainBlock
        :return: Restored bid
        :rtype: Bid
        """
        tx_dict = block.transaction["tick"]
        return cls(
            OrderId(TraderId(tx_dict["trader_id"]), OrderNumber(tx_dict["order_number"])),
            tx_dict["latitude"], tx_dict["longitude"],
            Quantity(tx_dict["quantity"], tx_dict["quantity_type"]),
            Timeout(tx_dict["timeout"]),
            Timestamp(tx_dict["timestamp"]),
            block_hash=block.hash
        )
