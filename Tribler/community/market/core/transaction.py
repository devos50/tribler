from decimal import Decimal

from Tribler.community.market.core.wallet_address import WalletAddress
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
        :type transaction_number: int
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(TransactionNumber, self).__init__()

        if not isinstance(transaction_number, int):
            raise ValueError("Transaction number must be an integer")

        self._transaction_number = transaction_number

    def __int__(self):
        return self._transaction_number

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
        self._transferred_price = Price(0, price.wallet_id)
        self._quantity = quantity
        self._transferred_quantity = Quantity(0, quantity.wallet_id)
        self._order_id = order_id
        self._timestamp = timestamp

        self.sent_wallet_info = False
        self.received_wallet_info = False
        self.incoming_address = None
        self.outgoing_address = None
        self.partner_incoming_address = None
        self.partner_outgoing_address = None

        self._payments = []
        self._current_payment = 0

    @classmethod
    def from_database(cls, data, payments):
        """
        Create a Transaction object based on information in the database.
        """
        transaction_id = TransactionId(TraderId(str(data[0])), TransactionNumber(data[2]))
        transaction = cls(transaction_id, TraderId(str(data[1])), Price(data[5], str(data[6])),
                          Quantity(data[8], str(data[9])), OrderId(TraderId(str(data[3])), OrderNumber(data[4])),
                          Timestamp(float(data[11])))

        transaction._transferred_price = Price(data[7], str(data[6]))
        transaction._transferred_quantity = Quantity(data[10], str(data[9]))
        transaction.sent_wallet_info = data[12]
        transaction.received_wallet_info = data[13]
        transaction.incoming_address = WalletAddress(str(data[14]))
        transaction.outgoing_address = WalletAddress(str(data[15]))
        transaction.partner_incoming_address = WalletAddress(str(data[16]))
        transaction.partner_outgoing_address = WalletAddress(str(data[17]))
        transaction._payments = payments

        return transaction

    def to_database(self):
        """
        Returns a database representation of a Transaction object.
        :rtype: tuple
        """
        return (unicode(self.transaction_id.trader_id), unicode(self.partner_trader_id),
                int(self.transaction_id.transaction_number), unicode(self.order_id.trader_id),
                int(self.order_id.order_number), float(self.price), unicode(self.price.wallet_id),
                float(self.transferred_price), float(self.total_quantity), unicode(self.total_quantity.wallet_id),
                float(self.transferred_quantity), float(self.timestamp), self.sent_wallet_info,
                self.received_wallet_info, unicode(self.incoming_address), unicode(self.outgoing_address),
                unicode(self.partner_incoming_address), unicode(self.partner_outgoing_address))

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
    def transferred_price(self):
        """
        :rtype: Price
        """
        return self._transferred_price

    @property
    def total_quantity(self):
        """
        :rtype: Quantity
        """
        return self._quantity

    @property
    def transferred_quantity(self):
        """
        :rtype: Quantity
        """
        return self._transferred_quantity

    @property
    def order_id(self):
        """
        Return the id of your order
        :rtype: OrderId
        """
        return self._order_id

    @property
    def payments(self):
        """
        :rtype: [Payment]
        """
        return self._payments

    @property
    def timestamp(self):
        """
        :rtype: Timestamp
        """
        return self._timestamp

    @staticmethod
    def unitize(amount, min_unit):
        """
        Return an a amount that is a multiple of min_unit.
        """
        if Decimal(str(amount)) % Decimal(str(min_unit)) == Decimal(0):
            return amount

        return (int(amount / min_unit) + 1) * min_unit

    def add_payment(self, payment):
        self._transferred_quantity += payment.transferee_quantity
        self._transferred_price += payment.transferee_price
        self._payments.append(payment)

    def last_payment(self, is_ask):
        for payment in reversed(self._payments):
            if is_ask and float(payment.transferee_quantity) > 0:
                return payment
            elif not is_ask and float(payment.transferee_price) > 0:
                return payment
        return None

    def next_payment(self, order_is_ask, min_unit):
        last_payment = self.last_payment(not order_is_ask)
        if not last_payment:
            # Just return the lowest unit possible
            return Quantity(min_unit, self.total_quantity.wallet_id) if order_is_ask else \
                Price(min_unit, self.price.wallet_id)

        # We determine the percentage of the last payment of the total amount
        if order_is_ask:
            if self.transferred_price >= self.price:  # Complete the trade
                return self.total_quantity - self.transferred_quantity

            percentage = float(last_payment.transferee_price) / float(self.price)
            transfer_amount = Transaction.unitize(float(percentage * float(self.total_quantity)), min_unit) * 2
            if transfer_amount < min_unit:
                transfer_amount = min_unit
            elif transfer_amount > float(self.total_quantity - self.transferred_quantity):
                transfer_amount = float(self.total_quantity - self.transferred_quantity)
            return Quantity(transfer_amount, self.total_quantity.wallet_id)
        else:
            if self.transferred_quantity >= self.total_quantity:  # Complete the trade
                return self.price - self.transferred_price

            percentage = float(last_payment.transferee_quantity) / float(self.total_quantity)
            transfer_amount = Transaction.unitize(float(percentage * float(self.price)), min_unit) * 2
            if transfer_amount < min_unit:
                transfer_amount = min_unit
            elif transfer_amount > float(self.price - self.transferred_price):
                transfer_amount = float(self.price - self.transferred_price)
            return Price(transfer_amount, self.price.wallet_id)

    def is_payment_complete(self):
        return self.transferred_price >= self.price and self.transferred_quantity >= self.total_quantity

    def to_dictionary(self):
        """
        Return a dictionary with a representation of this transaction.
        """
        return {
            "trader_id": str(self.transaction_id.trader_id),
            "order_number": int(self.order_id.order_number),
            "partner_trader_id": str(self.partner_trader_id),
            "transaction_number": int(self.transaction_id.transaction_number),
            "price": float(self.price),
            "price_type": self.price.wallet_id,
            "transferred_price": float(self.transferred_price),
            "quantity": float(self.total_quantity),
            "quantity_type": self.total_quantity.wallet_id,
            "transferred_quantity": float(self.transferred_quantity),
            "timestamp": float(self.timestamp),
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
