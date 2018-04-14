import random

from Tribler.community.market.core.message import TraderId, MessageNumber, Message, MessageId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.price import Price
from Tribler.community.market.core.quantity import Quantity
from Tribler.community.market.core.timestamp import Timestamp


class Trade(Message):
    """Abstract message class used for communicating with other nodes to find a trading partner"""

    def __init__(self, message_id, order_id, recipient_order_id, proposal_id, timestamp):
        """
        Don't use this method directly, use one of the class methods.

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param proposal_id: The ID of the trade proposal
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type proposal_id: int
        :type timestamp: Timestamp
        """
        super(Trade, self).__init__(message_id, timestamp)

        assert isinstance(order_id, OrderId), type(order_id)
        assert isinstance(recipient_order_id, OrderId), type(recipient_order_id)
        assert isinstance(proposal_id, int), type(proposal_id)

        self._order_id = order_id
        self._recipient_order_id = recipient_order_id
        self._proposal_id = proposal_id

    @classmethod
    def propose(cls, message_id, order_id, recipient_order_id, latitude, longitude, quantity, timestamp):
        """
        Propose a trade to another node

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type timestamp: Timestamp
        :return: A proposed trade
        :rtype: ProposedTrade
        """
        return ProposedTrade(
            message_id,
            order_id,
            recipient_order_id,
            random.randint(0, 100000000),
            latitude,
            longitude,
            quantity,
            timestamp
        )

    @classmethod
    def decline(cls, message_id, timestamp, proposed_trade, decline_reason):
        """
        Decline a trade from another node

        :param message_id: A message id to identify the trade
        :param timestamp: A timestamp when the trade was declined
        :param proposed_trade: A proposed trade that needs to be declined
        :param decline_reason: A reason for declining this trade
        :type message_id: MessageId
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :type decline_reason: int
        :return: A declined trade
        :rtype: DeclinedTrade
        """
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)
        assert isinstance(decline_reason, int), type(decline_reason)

        return DeclinedTrade(
            message_id,
            proposed_trade.recipient_order_id,
            proposed_trade.order_id,
            proposed_trade.proposal_id,
            timestamp,
            decline_reason
        )

    @classmethod
    def counter(cls, message_id, quantity, timestamp, proposed_trade):
        """
        Counter a trade from another node

        :param message_id: A message id to identify the trade
        :param quantity: The quantity to use for the counter offer
        :param timestamp: A timestamp when the trade was countered
        :param proposed_trade: A proposed trade that needs to be countered
        :type message_id: MessageId
        :type quantity: Quantity
        :type timestamp: Timestamp
        :type proposed_trade: ProposedTrade
        :return: A counter trade
        :rtype: CounterTrade
        """
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)

        return CounterTrade(
            message_id,
            proposed_trade.recipient_order_id,
            proposed_trade.order_id,
            proposed_trade.proposal_id,
            proposed_trade.price,
            quantity,
            timestamp
        )

    @property
    def order_id(self):
        """
        :return: The order id
        :rtype: OrderId
        """
        return self._order_id

    @property
    def recipient_order_id(self):
        """
        :return: The order id
        :rtype: OrderId
        """
        return self._recipient_order_id

    @property
    def proposal_id(self):
        """
        :return: The proposal id
        :rtype: int
        """
        return self._proposal_id

    def to_network(self):
        return NotImplemented


class ProposedTrade(Trade):
    """
    A proposed trade is send when a node whats to make a trade with another node. This trade cannot be made
    instantly because this node does not know if the tick from the other node is still available. Because of that a
    proposed trade is send first.
    """

    def __init__(self, message_id, order_id, recipient_order_id, proposal_id, latitude, longitude, quantity, timestamp):
        """
        Don't use this method directly, use the class methods from Trade or use the from_network

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param proposal_id: The ID of the trade proposal
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type proposal_id: int
        :type quantity: Quantity
        :type timestamp: Timestamp
        """
        super(ProposedTrade, self).__init__(message_id, order_id, recipient_order_id, proposal_id, timestamp)

        assert isinstance(latitude, float), type(latitude)
        assert isinstance(longitude, float), type(longitude)
        assert isinstance(quantity, Quantity), type(quantity)

        self._latitude = latitude
        self._longitude = longitude
        self._quantity = quantity

    @classmethod
    def from_network(cls, data):
        """
        Restore a proposed trade from the network

        :param data: TradePayload
        :return: Restored proposed trade
        :rtype: ProposedTrade
        """
        return cls(
            data.message_id,
            OrderId(data.trader_id, data.order_number),
            data.recipient_order_id,
            data.proposal_id,
            data.latitude,
            data.longitude,
            data.quantity,
            data.timestamp
        )

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
        :return: The quantity
        :rtype: Quantity
        """
        return self._quantity

    def to_network(self):
        """
        Return network representation of a proposed trade
        """
        return (
            MessageId(self._order_id.trader_id, self._message_id.message_number),
            self._timestamp,
            self._order_id.order_number,
            self._recipient_order_id,
            self._proposal_id,
            self._latitude,
            self._longitude,
            self._quantity,
        )


class CounterTrade(ProposedTrade):
    """
    Counter trades are send as a response to a proposed trade. If after receiving the order to be trade for
    is not fully available anymore, a counter offer is made with the quantity that is still left. This was
    done to insure that trades were made quickly and efficiently.
    """

    def __init__(self, message_id, order_id, recipient_order_id, proposal_id, price, quantity, timestamp):
        """
        Don't use this method directly, use one of the class methods of Trade or use from_network

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the traded party
        :param proposal_id: The ID of the trade proposal
        :param price: A price for the trade
        :param quantity: A quantity to be traded
        :param timestamp: A timestamp wen this trade was created
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type proposal_id: int
        :type price: Price
        :type quantity: Quantity
        :type timestamp: Timestamp
        """
        super(CounterTrade, self).__init__(message_id, order_id, recipient_order_id,
                                           proposal_id, price, quantity, timestamp)

    @classmethod
    def from_network(cls, data):
        """
        Restore a counter trade from the network

        :param data: TradePayload
        :return: Restored counter trade
        :rtype: CounterTrade
        """
        return cls(
            data.message_id,
            OrderId(data.trader_id, data.order_number),
            data.recipient_order_id,
            data.proposal_id,
            data.price,
            data.quantity,
            data.timestamp
        )

    def to_network(self):
        """
        Return network representation of a counter trade
        """
        return (
            self._message_id,
            self._timestamp,
            self._order_id.order_number,
            self._recipient_order_id,
            self._proposal_id,
            self._price,
            self._quantity,
        )


class DeclinedTrade(Trade):
    """
    Declined trades are send as a response to a proposed trade or a counter trade. When a proposed trade has come in
    and there is no possibility to make a counter offer a declined trade is send to indicate the is no possibility
    to make a trade. When a counter trade has been received, there is a check for seeing if the trade was reserved,
    if the trade was not reserved then a declined trade is send.
    """

    def __init__(self, message_id, order_id, recipient_order_id, proposal_id, timestamp, decline_reason):
        """
        Don't use this method directly, use one of the class methods from Trade or the from_network

        :param message_id: A message id to identify the trade
        :param order_id: A order id to identify the order
        :param recipient_order_id: A order id to identify the order
        :param proposal_id: The ID of the trade proposal
        :param timestamp: A timestamp wen this trade was created
        :param decline_reason: A reason for declining this trade
        :type message_id: MessageId
        :type order_id: OrderId
        :type recipient_order_id: OrderId
        :type proposal_id: int
        :type timestamp: Timestamp
        :type decline_reason: int
        """
        super(DeclinedTrade, self).__init__(message_id, order_id, recipient_order_id, proposal_id, timestamp)

        self._decline_reason = decline_reason

    @property
    def decline_reason(self):
        """
        :return: The reason why this match is declined
        :rtype: int
        """
        return self._decline_reason

    @classmethod
    def from_network(cls, data):
        """
        Restore a declined trade from the network

        :param data: DeclinedTradePayload
        :return: Restored declined trade
        :rtype: DeclinedTrade
        """
        return cls(
            data.message_id,
            OrderId(data.trader_id, data.order_number),
            data.recipient_order_id,
            data.proposal_id,
            data.timestamp,
            data.decline_reason
        )

    def to_network(self):
        """
        Return network representation of a declined trade
        """
        return (
            self._message_id,
            self._timestamp,
            self._order_id.order_number,
            self._recipient_order_id,
            self._proposal_id,
            self._decline_reason
        )
