from Tribler.community.market.wallet import ASSET_MAP


class Quantity(object):
    """Quantity is used for having a consistent comparable and usable class."""

    def __init__(self, quantity, wallet_id):
        """
        :param quantity: float representation of a quantity that is positive or zero
        :param wallet_id: Identifier of the wallet type of this price
        :type quantity: float
        :type wallet_id: str
        :raises ValueError: Thrown when one of the arguments are invalid
        """
        super(Quantity, self).__init__()

        if not isinstance(quantity, (int, float)):
            raise ValueError("Quantity must be an int or a float")

        if quantity < 0:
            raise ValueError("Quantity must be positive or zero")

        if not isinstance(wallet_id, str):
            raise ValueError("Wallet id must be a string")

        self._quantity = quantity
        self._wallet_id = wallet_id

    @property
    def wallet_id(self):
        """
        :rtype: str
        """
        return self._wallet_id

    @property
    def int_wallet_id(self):
        """
        :rtype: int
        """
        return ASSET_MAP[self._wallet_id]

    def __int__(self):
        return int(self._quantity)

    def __float__(self):
        return float(self._quantity)

    def __str__(self):
        return "%f %s" % (self._quantity, self.wallet_id)

    def __add__(self, other):
        if isinstance(other, Quantity) and self.wallet_id == other.wallet_id:
            return Quantity(self._quantity + other._quantity, self._wallet_id)
        else:
            return NotImplemented

    def __iadd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, Quantity) and self.wallet_id == other.wallet_id:
            return Quantity(self._quantity - other._quantity, self._wallet_id)
        else:
            return NotImplemented

    def __isub__(self, other):
        return self.__sub__(other)

    def __lt__(self, other):
        if isinstance(other, Quantity) and self.wallet_id == other.wallet_id:
            return self._quantity < other._quantity
        else:
            return NotImplemented

    def __le__(self, other):
        if isinstance(other, Quantity) and self.wallet_id == other.wallet_id:
            return self._quantity <= other._quantity
        else:
            return NotImplemented

    def __eq__(self, other):
        if not isinstance(other, Quantity) or not self.wallet_id == other.wallet_id:
            return NotImplemented
        elif self is other:
            return True
        else:
            return self._quantity == other._quantity

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        if isinstance(other, Quantity) and self.wallet_id == other.wallet_id:
            return self._quantity > other._quantity
        else:
            return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Quantity) and self.wallet_id == other.wallet_id:
            return self._quantity >= other._quantity
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self._quantity)
