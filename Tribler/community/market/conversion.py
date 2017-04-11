from struct import pack, unpack_from

from math import ceil

from Tribler.Core.Utilities.encoding import encode, decode
from Tribler.community.market.core.bitcoin_transaction_id import BitcoinTransactionId
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket
from core.bitcoin_address import BitcoinAddress
from core.message import TraderId, MessageNumber
from core.order import OrderNumber
from core.price import Price
from core.quantity import Quantity
from core.timeout import Timeout
from core.timestamp import Timestamp
from core.transaction import TransactionNumber, TransactionId
from ttl import Ttl


class MarketConversion(BinaryConversion):
    """Class that handles all encoding and decoding of Market messages."""

    def __init__(self, community):
        super(MarketConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"ask"),
                                 self._encode_offer, self._decode_offer)
        self.define_meta_message(chr(2), community.get_meta_message(u"bid"),
                                 self._encode_offer, self._decode_offer)
        self.define_meta_message(chr(3), community.get_meta_message(u"offer-sync"),
                                 self._encode_offer_sync, self._decode_offer_sync)
        self.define_meta_message(chr(4), community.get_meta_message(u"proposed-trade"),
                                 self._encode_proposed_trade, self._decode_proposed_trade)
        self.define_meta_message(chr(5), community.get_meta_message(u"accepted-trade"),
                                 self._encode_accepted_trade, self._decode_accepted_trade)
        self.define_meta_message(chr(6), community.get_meta_message(u"declined-trade"),
                                 self._encode_declined_trade, self._decode_declined_trade)
        self.define_meta_message(chr(7), community.get_meta_message(u"counter-trade"),
                                 self._encode_proposed_trade, self._decode_proposed_trade)
        self.define_meta_message(chr(8), community.get_meta_message(u"start-transaction"),
                                 self._encode_start_transaction, self._decode_start_transaction)
        self.define_meta_message(chr(9), community.get_meta_message(u"wallet-info"),
                                 self._encode_wallet_info, self._decode_wallet_info)
        self.define_meta_message(chr(10), community.get_meta_message(u"multi-chain-payment"),
                                 self._encode_multi_chain_payment, self._decode_multi_chain_payment)
        self.define_meta_message(chr(11), community.get_meta_message(u"bitcoin-payment"),
                                 self._encode_bitcoin_payment, self._decode_bitcoin_payment)
        self.define_meta_message(chr(12), community.get_meta_message(u"end-transaction"),
                                 self._encode_transaction, self._decode_transaction)

    def _encode_introduction_request(self, message):
        data = BinaryConversion._encode_introduction_request(self, message)

        if message.payload.orders_bloom_filter:
            data.extend((pack('!BH', message.payload.orders_bloom_filter.functions,
                              message.payload.orders_bloom_filter.size), message.payload.orders_bloom_filter.prefix,
                         message.payload.orders_bloom_filter.bytes))
        return data

    def _decode_introduction_request(self, placeholder, offset, data):
        offset, payload = BinaryConversion._decode_introduction_request(self, placeholder, offset, data)

        if len(data) > offset:
            if len(data) < offset + 5:
                raise DropPacket("Insufficient packet size")

            functions, size = unpack_from('!BH', data, offset)
            offset += 3

            prefix = data[offset]
            offset += 1

            if not 0 < functions:
                raise DropPacket("Invalid functions value")
            if not 0 < size:
                raise DropPacket("Invalid size value")
            if not size % 8 == 0:
                raise DropPacket("Invalid size value, must be a multiple of eight")

            length = int(ceil(size / 8))
            if not length == len(data) - offset:
                raise DropPacket("Invalid number of bytes available (irq) %d, %d, %d" % (length, len(data) - offset, size))

            orders_bloom_filter = BloomFilter(data[offset:offset + length], functions, prefix=prefix)
            offset += length

            payload.set_orders_bloom_filter(orders_bloom_filter)

        return offset, payload

    def _decode_payload(self, placeholder, offset, data, types):
        try:
            offset, payload = decode(data, offset)
        except ValueError:
            raise DropPacket("Unable to decode the payload")

        if not isinstance(payload, tuple):
            raise DropPacket("Invalid payload type")

        if not len(payload) == len(types):
            raise DropPacket("Invalid payload length")

        args = []
        for i, arg_type in enumerate(types):
            try:
                if arg_type == Price or arg_type == Quantity:
                    args.append(arg_type(payload[i]))
                elif arg_type == str or arg_type == int:
                    args.append(payload[i])
                else:
                    args.append(arg_type(payload[i]))
            except ValueError:
                raise DropPacket("Invalid '" + arg_type.__name__ + "' type")
        return offset, placeholder.meta.payload.implement(*args)

    def _encode_offer(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number), float(payload.price),
            float(payload.quantity), float(payload.timeout), float(payload.timestamp), int(payload.ttl),
            str(payload.address.ip), int(payload.address.port)
        ))
        return packet,

    def _decode_offer(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, Price, Quantity, Timeout, Timestamp, Ttl,
                                     str, int])

    def _encode_offer_sync(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number), float(payload.price),
            float(payload.quantity), float(payload.timeout), float(payload.timestamp), int(payload.ttl),
            str(payload.address.ip), int(payload.address.port), bool(payload.is_ask)
        ))
        return packet,

    def _decode_offer_sync(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, Price, Quantity, Timeout, Timestamp, Ttl,
                                     str, int, bool])

    def _encode_proposed_trade(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number),
            str(payload.recipient_trader_id), str(payload.recipient_order_number), float(payload.price),
            float(payload.quantity), float(payload.timestamp), str(payload.address.ip), int(payload.address.port)
        ))
        return packet,

    def _decode_proposed_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, Price, Quantity,
                                     Timestamp, str, int])

    def _encode_accepted_trade(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number),
            str(payload.recipient_trader_id), str(payload.recipient_order_number), float(payload.price),
            float(payload.quantity), float(payload.timestamp), int(payload.ttl),
            str(payload.address.ip), int(payload.address.port)
        ))
        return packet,

    def _decode_accepted_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, Price, Quantity,
                                     Timestamp, Ttl, str, int])

    def _encode_declined_trade(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.order_number),
            str(payload.recipient_trader_id), str(payload.recipient_order_number), float(payload.timestamp)
        ))
        return packet,

    def _decode_declined_trade(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, OrderNumber, TraderId, OrderNumber, Timestamp])

    def _encode_start_transaction(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), str(payload.order_trader_id), str(payload.order_number),
            str(payload.recipient_trader_id), str(payload.recipient_order_number),
            float(payload.price), float(payload.quantity), float(payload.timestamp)
        ))
        return packet,

    def _decode_start_transaction(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, TraderId, OrderNumber,
                                     TraderId, OrderNumber, Price, Quantity, Timestamp])

    def _encode_transaction(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), float(payload.timestamp)
        ))
        return packet,

    def _decode_transaction(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, Timestamp])

    def _encode_wallet_info(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), str(payload.incoming_address), str(payload.outgoing_address),
            float(payload.timestamp)
        ))
        return packet,

    def _decode_wallet_info(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, str, str, Timestamp])

    def _encode_multi_chain_payment(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), float(payload.transferor_quantity),
            float(payload.transferee_price), float(payload.timestamp)
        ))
        return packet,

    def _decode_multi_chain_payment(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, Quantity, Price, Timestamp])

    def _encode_bitcoin_payment(self, message):
        payload = message.payload
        packet = encode((
            str(payload.trader_id), str(payload.message_number), str(payload.transaction_trader_id),
            str(payload.transaction_number), float(payload.price), str(payload.txid), float(payload.timestamp)
        ))
        return packet,

    def _decode_bitcoin_payment(self, placeholder, offset, data):
        return self._decode_payload(placeholder, offset, data,
                                    [TraderId, MessageNumber, TraderId, TransactionNumber, Price,
                                     BitcoinTransactionId, Timestamp])
