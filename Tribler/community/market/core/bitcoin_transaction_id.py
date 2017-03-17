class BitcoinTransactionId(object):
    """Used for having a validated instance of a bitcoin address that we can easily check if it still valid."""

    def __init__(self, transaction_id):
        """
        :param transaction_id: String representation of a bitcoin transaction id
        :type transaction_id: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(BitcoinTransactionId, self).__init__()

        if not isinstance(transaction_id, str):
            raise ValueError("Bitcoin transaction id must be a string")

        self._transaction_id = transaction_id

    def __str__(self):
        return "%s" % self._transaction_id
