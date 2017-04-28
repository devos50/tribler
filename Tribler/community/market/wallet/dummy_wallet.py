import string
from random import choice

from twisted.internet import reactor
from twisted.internet.defer import succeed
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
        return succeed({'total': self.balance})

    def transfer(self, quantity, candidate):
        def on_balance(balance):
            if balance['total'] < quantity:
                raise InsufficientFunds()

            self.balance -= quantity
            return succeed(str(quantity))

        return self.get_balance().addCallback(on_balance)

    def monitor_transaction(self, transaction_id):
        """
        Monitor an incoming transaction with a specific ID.
        """
        def on_transaction_done():
            self.balance -= float(transaction_id)  # txid = amount of money transferred

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
