from __future__ import absolute_import

from Tribler.community.market.core.assetamount import AssetAmount
from Tribler.community.market.core.message import Message, TraderId
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.transaction import TransactionId, TransactionNumber
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.pyipv8.ipv8.database import database_blob


class Payment(Message):
    """Class representing a payment."""

    def __init__(self, trader_id, transaction_id, transferred_assets, address_from, address_to, payment_id,
                 timestamp, success):
        super(Payment, self).__init__(trader_id, timestamp)
        self._transaction_id = transaction_id
        self._transferred_assets = transferred_assets
        self._address_from = address_from
        self._address_to = address_to
        self._payment_id = payment_id
        self._success = success

    @classmethod
    def from_database(cls, data):
        """
        Create a Payment object based on information in the database.
        """
        (trader_id, transaction_trader_id, transaction_number, payment_id, transferred_amount, transferred_id,
         address_from, address_to, timestamp, success) = data

        transaction_id = TransactionId(TraderId(bytes(transaction_trader_id)), TransactionNumber(transaction_number))
        return cls(TraderId(bytes(trader_id)), transaction_id, AssetAmount(transferred_amount, bytes(transferred_id)),
                   WalletAddress(bytes(address_from)), WalletAddress(bytes(address_to)), PaymentId(bytes(payment_id)),
                   Timestamp(float(timestamp)), bool(success))

    def to_database(self):
        """
        Returns a database representation of a Payment object.
        :rtype: tuple
        """
        return (database_blob(bytes(self.trader_id)), database_blob(bytes(self.transaction_id.trader_id)),
                int(self.transaction_id.transaction_number), database_blob(bytes(self.payment_id)),
                self.transferred_assets.amount, database_blob(bytes(self.transferred_assets.asset_id)),
                database_blob(bytes(self.address_from)), database_blob(bytes(self.address_to)),
                float(self.timestamp), self.success)

    @property
    def transaction_id(self):
        return self._transaction_id

    @property
    def transferred_assets(self):
        return self._transferred_assets

    @property
    def address_from(self):
        return self._address_from

    @property
    def address_to(self):
        return self._address_to

    @property
    def payment_id(self):
        return self._payment_id

    @property
    def success(self):
        return self._success

    @classmethod
    def from_network(cls, data):
        """
        Restore a payment from the network

        :param data: PaymentPayload
        :return: Restored payment
        :rtype: Payment
        """
        return cls(
            data.trader_id,
            data.transaction_id,
            data.transferred_assets,
            data.address_from,
            data.address_to,
            data.payment_id,
            data.timestamp,
            data.success
        )

    def to_network(self):
        """
        Return network representation of the multi chain payment
        """
        return (
            self._trader_id,
            self._timestamp,
            self._transaction_id,
            self._transferred_assets,
            self._address_from,
            self._address_to,
            self._payment_id,
            self._success
        )

    def to_dictionary(self):
        return {
            b"trader_id": bytes(self.transaction_id.trader_id),
            b"transaction_number": int(self.transaction_id.transaction_number),
            b"transferred": self.transferred_assets.to_dictionary(),
            b"payment_id": bytes(self.payment_id),
            b"address_from": bytes(self.address_from),
            b"address_to": bytes(self.address_to),
            b"timestamp": float(self.timestamp),
            b"success": self.success
        }
