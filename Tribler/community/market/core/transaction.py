from Tribler.community.market.core.incremental_manager import IncrementalManager
from message import TraderId, Message, MessageId, MessageNumber
from order import OrderId, OrderNumber
from price import Price
from quantity import Quantity
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

    def __init__(self, transaction_id, partner_trader_id, price, quantity, order_id, timestamp):
        """
        :param transaction_id: An transaction id to identify the order
        :param partner_trader_id: The trader id from the peer that is traded with
        :param price: A price to indicate for which amount to sell or buy
        :param quantity: A quantity to indicate how much to sell or buy
        :param order_id: The id of your order for this transaction
        :param timestamp: A timestamp when the transaction was created
        :type transaction_id: TransactionId
        :type partner_trader_id: TraderId
        :type price: Price
        :type quantity: Quantity
        :type order_id: OrderId
        :type timestamp: Timestamp
        """
        super(Transaction, self).__init__()

        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(partner_trader_id, TraderId), type(partner_trader_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)
        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(timestamp, Timestamp), type(timestamp)

        self._transaction_id = transaction_id
        self._partner_trader_id = partner_trader_id
        self._price = price
        self._quantity = quantity
        self._order_id = order_id
        self._timestamp = timestamp
        self._payments = {}

        self.sent_wallet_info = False
        self.received_wallet_info = False
        self.incoming_address = None
        self.outgoing_address = None
        self.partner_incoming_address = None
        self.partner_outgoing_address = None

        self._payment_list = []
        self._current_payment = 0

    def determine_payments(self, min_unit_price, min_unit_quantity):
        self._payment_list = IncrementalManager.determine_incremental_payments_list(self._price, self._quantity,
                                                                                    min_unit_price, min_unit_quantity)

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

        return cls(transaction_id, accepted_trade.recipient_order_id.trader_id, accepted_trade.price,
                   accepted_trade.quantity, accepted_trade.order_id, accepted_trade.timestamp)

    @property
    def transaction_id(self):
        """
        :rtype: TransactionId
        """
        return self._transaction_id

    @property
    def partner_trader_id(self):
        """
        :rtype: TraderId
        """
        return self._partner_trader_id

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
    def order_id(self):
        """
        Return the id of your order
        :rtype: OrderId
        """
        return self._order_id

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp

    def add_payment(self, payment):
        self._payments[payment.message_id] = payment

    def has_payment(self, message_id):
        return self._payments.has_key(message_id)

    def next_payment(self):
        if self._current_payment < len(self._payment_list):
            payment = self._payment_list[self._current_payment]
            self._current_payment += 1
            return payment
        else:
            return -1, -1

    def is_payment_complete(self):
        return len(self._payments.keys()) >= len(self._payment_list) * 2

    def to_dictionary(self):
        """
        Return a dictionary with a representation of this transaction.
        """
        return {
            "trader_id": str(self.transaction_id.trader_id),
            "partner_trader_id": str(self.partner_trader_id),
            "transaction_number": str(self.transaction_id.transaction_number),
            "price": float(self.price),
            "price_type": self.price.wallet_id,
            "quantity": float(self.total_quantity),
            "quantity_type": self.total_quantity.wallet_id,
            "timestamp": str(self.timestamp),
            "payment_complete": self.is_payment_complete()
        }


class StartTransaction(Message):
    """Class for representing a message to indicate the start of a payment set"""

    def __init__(self, message_id, transaction_id, order_id, recipient_order_id, price, quantity, timestamp):
        """
        :param message_id: A message id to identify the message
        :param transaction_id: A transaction id to identify the transaction
        :param order_id: My order id
        :param recipient_order_id: The order id of the recipient of this message
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp when the transaction was created
        :type message_id: MessageId
        :type transaction_id: TransactionId
        :type order_id: OrderId
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        """
        super(StartTransaction, self).__init__(message_id, timestamp)

        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(recipient_order_id, OrderId), type(order_id)
        assert isinstance(price, Price), type(price)
        assert isinstance(quantity, Quantity), type(quantity)

        self._transaction_id = transaction_id
        self._order_id = order_id
        self._recipient_order_id = recipient_order_id
        self._price = price
        self._quantity = quantity

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

    @property
    def recipient_order_id(self):
        """
        :rtype: OrderId
        """
        return self._recipient_order_id

    @property
    def price(self):
        """
        :return: The price
        :rtype: Price
        """
        return self._price

    @property
    def quantity(self):
        """
        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a start transaction message from the network

        :param data: StartTransactionPayload
        :return: Restored start transaction
        :rtype: StartTransaction
        """
        assert hasattr(data, 'trader_id'), isinstance(data.trader_id, TraderId)
        assert hasattr(data, 'message_number'), isinstance(data.message_number, MessageNumber)
        assert hasattr(data, 'transaction_trader_id'), isinstance(data.transaction_trader_id, TraderId)
        assert hasattr(data, 'transaction_number'), isinstance(data.transaction_number, TransactionNumber)
        assert hasattr(data, 'order_trader_id'), isinstance(data.order_trader_id, TraderId)
        assert hasattr(data, 'order_number'), isinstance(data.order_number, OrderNumber)
        assert hasattr(data, 'recipient_trader_id'), isinstance(data.recipient_trader_id, TraderId)
        assert hasattr(data, 'recipient_order_number'), isinstance(data.recipient_order_number, OrderNumber)
        assert hasattr(data, 'price'), isinstance(data.price, Price)
        assert hasattr(data, 'quantity'), isinstance(data.quantity, Quantity)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            MessageId(data.trader_id, data.message_number),
            TransactionId(data.transaction_trader_id, data.transaction_number),
            OrderId(data.order_trader_id, data.order_number),
            OrderId(data.recipient_trader_id, data.recipient_order_number),
            data.price,
            data.quantity,
            data.timestamp
        )

    def to_network(self):
        """
        Return network representation of the start transaction message
        """
        return (
            self._message_id.trader_id,
            self._message_id.message_number,
            self._transaction_id.trader_id,
            self._transaction_id.transaction_number,
            self._order_id.trader_id,
            self._order_id.order_number,
            self._recipient_order_id.trader_id,
            self._recipient_order_id.order_number,
            self._price,
            self._quantity,
            self._timestamp,
        )
