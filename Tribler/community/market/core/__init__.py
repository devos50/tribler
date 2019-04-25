class DeclinedTradeReason(object):
    ORDER_COMPLETED = 0
    ORDER_EXPIRED = 1
    ORDER_RESERVED = 2
    ORDER_INVALID = 3
    ORDER_CANCELLED = 4
    UNACCEPTABLE_PRICE = 5
    OTHER = 6


class DeclineMatchReason(object):
    ORDER_COMPLETED = 0
    OTHER_ORDER_COMPLETED = 1
    OTHER_ORDER_CANCELLED = 2
    OTHER = 3
