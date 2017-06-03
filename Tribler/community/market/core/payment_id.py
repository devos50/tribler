class PaymentId(object):
    """Used for having a validated instance of a payment id that we can monitor."""

    def __init__(self, payment_id):
        """
        :param payment_id: String representation of the id of the payment
        :type payment_id: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(PaymentId, self).__init__()

        if not isinstance(payment_id, str):
            raise ValueError("Payment id must be a string")

        self._payment_id = payment_id

    def __str__(self):
        return "%s" % self._payment_id

    def __eq__(self, other):
        if not isinstance(other, PaymentId):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._payment_id == other._payment_id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._payment_id)

