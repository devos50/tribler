from order import OrderId
from message import TraderId, Message, MessageId
from price import Price
from quantity import Quantity
from timeout import Timeout
from timestamp import Timestamp
from trade import AcceptedTrade


class TransactionNumber(object):
    """Used for having a validated instance of a transaction number that we can easily check if it still valid."""

    def __init__(self, transaction_number):
        """
        :type transaction_number: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(TransactionNumber, self).__init__()

        if not isinstance(transaction_number, str):
            raise ValueError("Transaction number must be a string")

        self._transaction_number = transaction_number

    def __str__(self):
        return "%s" % self._transaction_number

    def __eq__(self, other):
        if not isinstance(other, TransactionNumber):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._transaction_number == \
                   other._transaction_number

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._transaction_number)


class TransactionId(object):
    """Used for having a validated instance of a transaction id that we can easily check if it still valid."""

    def __init__(self, trader_id, transaction_number):
        """
        :param trader_id: The trader id who created the order
        :param transaction_number: The number of the transaction created
        :type trader_id: TraderId
        :type transaction_number: TransactionNumber
        """
        super(TransactionId, self).__init__()

        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(transaction_number, TransactionNumber), type(transaction_number)

        self._trader_id = trader_id
        self._transaction_number = transaction_number

    @property
    def trader_id(self):
        """
        :rtype: TraderId
        """
        return self._trader_id

    @property
    def transaction_number(self):
        """
        :rtype: TransactionNumber
        """
        return self._transaction_number

    def __str__(self):
        """
        format: <trader_id>.<transaction_number>
        """
        return "%s.%s" % (self._trader_id, self._transaction_number)

    def __eq__(self, other):
        if not isinstance(other, TransactionId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return (self._trader_id, self._transaction_number) == \
                   (other._trader_id, other._transaction_number)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self._trader_id, self._transaction_number))


class Transaction(object):
    """Class for representing a transaction between two nodes"""

    def __init__(self, transaction_id, price, quantity, timeout, timestamp):
        """
        :param transaction_id: An transaction id to identify the order
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param timeout: A timeout when this transaction is going to expire
        :param timestamp: A timestamp when the transaction was created
        :type transaction_id: TransactionId
        :type price: Price
        :type quantity: Quantity
        :type timeout: Timeout
        :type timestamp: Timestamp
        """
        super(Transaction, self).__init__()

        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(timeout, Timeout), type(timeout)
        assert isinstance(timestamp, Timestamp), type(timestamp)

        self._transaction_id = transaction_id
        self._price = price
        self._quantity = quantity
        self._timeout = timeout
        self._timestamp = timestamp
        self._payments = {}

    @classmethod
    def from_accepted_trade(cls, accepted_trade, transaction_id):
        """
        :param accepted_trade: The accepted trade to create the transaction for
        :param transaction_id: The transaction id to use for this transaction
        :type accepted_trade: AcceptedTrade
        :type transaction_id: TransactionId
        :return: The created transaction
        :rtype: Transaction
        """
        assert isinstance(accepted_trade, AcceptedTrade), type(accepted_trade)
        assert isinstance(transaction_id, TransactionId), type(transaction_id)

        return cls(transaction_id, accepted_trade.price, accepted_trade.quantity, Timeout(float('inf')),
                   accepted_trade.timestamp)

    @property
    def transaction_id(self):
        """
        :rtype: TransactionId
        """
        return self._transaction_id

    @property
    def price(self):
        """
        :rtype: Price
        """
        return self._price

    @property
    def total_quantity(self):
        """
        :rtype: Quantity
        """
        return self._quantity

    @property
    def timeout(self):
        """
        Return when the transaction is going to expire
        :rtype: Timeout
        """
        return self._timeout

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp


class StartTransaction(Message):
    """Class for representing a message to indicate the start of a payment set"""

    def __init__(self, message_id, transaction_id, order_id, timestamp):
        """
        :param message_id: A message id to identify the message
        :param transaction_id: A transaction id to identify the transaction
        :param order_id: An order id to identify the order
        :param timestamp: A timestamp when the transaction was created
        :type message_id: MessageId
        :type transaction_id: TransactionId
        :type order_id: OrderId
        :type timestamp: Timestamp
        """
        super(StartTransaction, self).__init__(message_id, timestamp)

        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(order_id, OrderId), type(order_id)

        self._transaction_id = transaction_id
        self._order_id = order_id

    @property
    def transaction_id(self):
        """
        :rtype: TransactionId
        """
        return self._transaction_id

    @property
    def order_id(self):
        """
        :rtype: OrderId
        """
        return self._order_id

    @classmethod
    def from_network(cls, data):
        """
        Restore a start transaction message from the network

        :param data: object with (message_id, transaction_id, timestamp) properties
        :return: Restored start transaction
        :rtype: StartTransaction
        """
        assert hasattr(data, 'message_id'), isinstance(data.message_id, MessageId)
        assert hasattr(data, 'transaction_id'), isinstance(data.transaction_id, TransactionId)
        assert hasattr(data, 'order_id'), isinstance(data.order_id, OrderId)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            data.message_id,
            data.transaction_id,
            data.order_id,
            data.timestamp,
        )

    def to_network(self):
        """
        Return network representation of the start transaction message

        :return: tuple(<destination public identifiers>),tuple(<message_id>, <transaction_id>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            self._message_id,
            self._transaction_id,
            self._timestamp,
        )


class EndTransaction(Message):
    """Class for representing a message to indicate the completion of a successful payment set """

    def __init__(self, message_id, transaction_id, timestamp):
        """
        :param message_id: A message id to identify the message
        :param transaction_id: An transaction id to identify the order
        :param timestamp: A timestamp when the transaction was created
        :type message_id: MessageId
        :type transaction_id: TransactionId
        :type timestamp: Timestamp
        """
        super(EndTransaction, self).__init__(message_id, timestamp)

        assert isinstance(transaction_id, TransactionId), type(transaction_id)

        self._transaction_id = transaction_id

    @property
    def transaction_id(self):
        """
        :rtype: TransactionId
        """
        return self._transaction_id

    @classmethod
    def from_network(cls, data):
        """
        Restore a end transaction message from the network

        :param data: object with (message_id, transaction_id, timestamp) properties
        :return: Restored end transaction
        :rtype: EndTransaction
        """
        assert hasattr(data, 'message_id'), isinstance(data.message_id, MessageId)
        assert hasattr(data, 'transaction_id'), isinstance(data.transaction_id, TransactionId)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            data.message_id,
            data.transaction_id,
            data.timestamp,
        )

    def to_network(self):
        """
        Return network representation of the end transaction message

        :return: tuple(<destination public identifiers>),tuple(<message_id>, <transaction_id>, <timestamp>)
        :rtype: tuple, tuple
        """
        return tuple(), (
            self._message_id,
            self._transaction_id,
            self._timestamp,
        )