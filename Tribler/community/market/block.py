from __future__ import absolute_import

from six import binary_type, integer_types

from Tribler.community.market import MAX_ORDER_TIMEOUT
from Tribler.pyipv8.ipv8.attestation.trustchain.block import TrustChainBlock


class MarketBlock(TrustChainBlock):
    """
    This class represents a block in the market community.
    It contains various utility methods to verify validity within the context of the market.
    """

    @staticmethod
    def has_fields(needles, haystack):
        for needle in needles:
            if needle not in haystack:
                return False
        return True

    @staticmethod
    def has_required_types(types, container):
        for key, required_type in types:
            if not isinstance(container[key], required_type):
                return False
        return True

    @staticmethod
    def is_valid_asset_pair(assets_dict, amount_positive=True):
        if b'first' not in assets_dict or b'second' not in assets_dict:
            return False
        if b'amount' not in assets_dict[b'first'] or b'type' not in assets_dict[b'first']:
            return False
        if b'amount' not in assets_dict[b'second'] or b'type' not in assets_dict[b'second']:
            return False

        if not MarketBlock.has_required_types([(b'amount', integer_types), (b'type', binary_type)],
                                              assets_dict[b'first']):
            return False
        if not MarketBlock.has_required_types([(b'amount', integer_types), (b'type', binary_type)],
                                              assets_dict[b'second']):
            return False

        if assets_dict[b'first'][b'amount'].bit_length() > 63 or assets_dict[b'second'][b'amount'].bit_length() > 63:
            return False

        if amount_positive and (assets_dict[b'first'][b'amount'] <= 0 or assets_dict[b'second'][b'amount'] <= 0):
            return False

        return True

    @staticmethod
    def is_valid_trader_id(trader_id):
        if len(trader_id) != 40:
            return False

        try:
            int(trader_id, 16)
        except ValueError:  # Not a hexadecimal
            return False
        return True

    @staticmethod
    def is_valid_tick(tick):
        """
        Verify whether a dictionary that contains a tick, is valid.
        """
        required_fields = [b'trader_id', b'order_number', b'assets', b'timeout', b'timestamp', b'traded']
        if not MarketBlock.has_fields(required_fields, tick):
            return False

        required_types = [(b'trader_id', binary_type), (b'order_number', int), (b'assets', dict), (b'timestamp', float),
                          (b'timeout', int)]

        if not MarketBlock.is_valid_trader_id(tick[b'trader_id']):
            return False
        if not MarketBlock.is_valid_asset_pair(tick[b'assets']):
            return False
        if not MarketBlock.has_required_types(required_types, tick):
            return False
        if tick[b'timeout'] < 0 or tick[b'timeout'] > MAX_ORDER_TIMEOUT:
            return False

        return True

    @staticmethod
    def is_valid_tx(tx):
        """
        Verify whether a dictionary that contains a transaction, is valid.
        """
        required_fields = [b'trader_id', b'order_number', b'partner_trader_id', b'partner_order_number',
                           b'transaction_number', b'assets', b'transferred', b'timestamp', b'payment_complete',
                           b'status']
        if not MarketBlock.has_fields(required_fields, tx):
            return False
        if len(tx) != len(required_fields):
            return False

        required_types = [(b'trader_id', binary_type), (b'order_number', int), (b'partner_trader_id', binary_type),
                          (b'partner_order_number', int), (b'transaction_number', int), (b'assets', dict),
                          (b'transferred', dict), (b'timestamp', float), (b'payment_complete', bool),
                          (b'status', binary_type)]

        if not MarketBlock.is_valid_trader_id(tx[b'trader_id']) or not \
                MarketBlock.is_valid_trader_id(tx[b'partner_trader_id']):
            return False
        if not MarketBlock.is_valid_asset_pair(tx[b'assets']):
            return False
        if not MarketBlock.is_valid_asset_pair(tx[b'transferred'], amount_positive=False):
            return False
        if not MarketBlock.has_required_types(required_types, tx):
            return False

        return True

    @staticmethod
    def is_valid_payment(payment):
        """
        Verify whether a dictionary that contains a payment, is valid.
        """
        required_fields = [b'trader_id', b'transaction_number', b'transferred', b'payment_id', b'address_from',
                           b'address_to', b'timestamp', b'success']
        if not MarketBlock.has_fields(required_fields, payment):
            return False
        if len(payment) != len(required_fields):
            return False

        required_types = [(b'trader_id', binary_type), (b'transaction_number', int), (b'transferred', dict),
                          (b'payment_id', binary_type), (b'address_from', binary_type), (b'address_to', binary_type),
                          (b'timestamp', float), (b'success', bool)]
        if not MarketBlock.is_valid_trader_id(payment[b'trader_id']):
            return False
        if not MarketBlock.has_required_types(required_types, payment):
            return False

        return True

    def is_valid_tick_block(self):
        """
        Verify whether an incoming block with the tick type is valid.
        """
        if self.type != b"ask" and self.type != b"bid":
            return False
        if not MarketBlock.has_fields([b'tick'], self.transaction):
            return False
        if not MarketBlock.is_valid_tick(self.transaction[b'tick']):
            return False

        return True

    def is_valid_cancel_block(self):
        """
        Verify whether an incoming block with cancel type is valid.
        """
        if self.type != b"cancel_order":
            return False

        if not MarketBlock.has_fields([b'trader_id', b'order_number'], self.transaction):
            return False

        required_types = [(b'trader_id', binary_type), (b'order_number', int)]
        if not MarketBlock.has_required_types(required_types, self.transaction):
            return False

        return True

    def is_valid_tx_init_done_block(self):
        """
        Verify whether an incoming block with tx_init/tx_done type is valid.
        """
        if self.type != b"tx_init" and self.type != b"tx_done":
            return False

        if not MarketBlock.has_fields([b'ask', b'bid', b'tx'], self.transaction):
            return False

        if not MarketBlock.is_valid_tick(self.transaction[b'ask']):
            return False
        if not MarketBlock.is_valid_tick(self.transaction[b'bid']):
            return False
        if not MarketBlock.is_valid_tx(self.transaction[b'tx']):
            return False

        return True

    def is_valid_tx_payment_block(self):
        """
        Verify whether an incoming block with tx_payment type is valid.
        """
        if self.type != b"tx_payment":
            return False

        if not MarketBlock.has_fields([b'payment'], self.transaction):
            return False
        if not MarketBlock.is_valid_payment(self.transaction[b'payment']):
            return False

        return True
