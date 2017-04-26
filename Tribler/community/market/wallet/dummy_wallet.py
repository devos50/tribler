import string
from random import choice

from twisted.internet import reactor
from twisted.internet.task import deferLater

from Tribler.community.market.wallet.wallet import Wallet, InsufficientFunds


class BaseDummyWallet(Wallet):
    """
    This is a dummy wallet that is primarily used for testing purposes
    """

    def __init__(self):
        super(BaseDummyWallet, self).__init__()

        self.balance = 1000
        self.created = True
        self.address = ''.join([choice(string.lowercase) for i in xrange(10)])

    def get_identifier(self):
        return 'DUM'

    def create_wallet(self, *args, **kwargs):
        pass

    def get_balance(self):
        return {'total': self.balance}

    def transfer(self, quantity, candidate):
        if self.get_balance()['total'] < quantity:
            raise InsufficientFunds()

        self.balance -= quantity

    def monitor_transaction(self, amount):
        """
        Monitor an incoming transaction with a specific amount.
        """
        def on_transaction_done():
            self.balance -= amount

        return deferLater(reactor, 1, on_transaction_done)

    def get_address(self):
        return self.address

    def get_transactions(self):
        # TODO(Martijn): implement this
        return []

    def min_unit(self):
        return 1


class DummyWallet1(BaseDummyWallet):

    def get_name(self):
        return 'Dummy 1'

    def get_identifier(self):
        return 'DUM1'


class DummyWallet2(BaseDummyWallet):

    def get_name(self):
        return 'Dummy 2'

    def get_identifier(self):
        return 'DUM2'
