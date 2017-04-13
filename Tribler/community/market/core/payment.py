from Tribler.community.market.core.payment_id import PaymentId
from bitcoin_address import BitcoinAddress
from message import MessageId, Message, TraderId, MessageNumber
from price import Price
from quantity import Quantity
from timestamp import Timestamp
from transaction import TransactionNumber, TransactionId


class Payment(Message):
    """Class representing a payment."""

    def __init__(self, message_id, transaction_id, transferee_quantity, transferee_price,
                 address_from, address_to, payment_id, timestamp):
        assert isinstance(transaction_id, TransactionId), type(transaction_id)
        assert isinstance(transferee_quantity, Quantity), type(transferee_quantity)
        assert isinstance(transferee_price, Price), type(transferee_price)
        assert isinstance(address_from, str), type(address_from)
        assert isinstance(address_to, str), type(address_to)
        assert isinstance(payment_id, PaymentId), type(payment_id)

        super(Payment, self).__init__(message_id, timestamp)
        self._transaction_id = transaction_id
        self._transferee_quantity = transferee_quantity
        self._transferee_price = transferee_price
        self._address_from = address_from
        self._address_to = address_to
        self._payment_id = payment_id

    @property
    def transaction_id(self):
        return self._transaction_id

    @property
    def transferee_quantity(self):
        return self._transferee_quantity

    @property
    def transferee_price(self):
        return self._transferee_price

    @property
    def address_from(self):
        return self._address_from

    @property
    def address_to(self):
        return self._address_to

    @property
    def payment_id(self):
        return self._payment_id

    @classmethod
    def from_network(cls, data):
        """
        Restore a payment from the network

        :param data: PaymentPayload
        :return: Restored payment
        :rtype: Payment
        """
        assert hasattr(data, 'trader_id'), isinstance(data.trader_id, TraderId)
        assert hasattr(data, 'message_number'), isinstance(data.message_number, MessageNumber)
        assert hasattr(data, 'transaction_trader_id'), isinstance(data.transaction_trader_id, TraderId)
        assert hasattr(data, 'transaction_number'), isinstance(data.transaction_number, TransactionNumber)
        assert hasattr(data, 'transferee_quantity'), isinstance(data.transferee_quantity, Quantity)
        assert hasattr(data, 'transferee_price'), isinstance(data.transferee_price, Price)
        assert hasattr(data, 'address_from'), isinstance(data.address_from, str)
        assert hasattr(data, 'address_to'), isinstance(data.address_to, str)
        assert hasattr(data, 'payment_id'), isinstance(data.payment_id, PaymentId)
        assert hasattr(data, 'timestamp'), isinstance(data.timestamp, Timestamp)

        return cls(
            MessageId(data.trader_id, data.message_number),
            TransactionId(data.transaction_trader_id, data.transaction_number),
            data.transferee_quantity,
            data.transferee_price,
            data.address_from,
            data.address_to,
            data.payment_id,
            data.timestamp,
        )

    def to_network(self):
        """
        Return network representation of the multi chain payment
        """
        return (
            self._message_id.trader_id,
            self._message_id.message_number,
            self._transaction_id.trader_id,
            self._transaction_id.transaction_number,
            self._transferee_quantity,
            self._transferee_price,
            self._address_from,
            self._address_to,
            self._payment_id,
            self._timestamp,
        )
