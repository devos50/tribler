from twisted.internet import reactor
from twisted.internet.defer import succeed
from twisted.internet.task import deferLater

from Tribler.community.market.wallet.wallet import Wallet, InsufficientFunds
from Tribler.internetofmoney.Managers.PayPal.PayPalManager import PayPalManager


class PayPalWallet(Wallet):
    """
    This class manages a PayPal wallet.
    """

    def __init__(self, input_handler, cache_dir='.'):
        super(PayPalWallet, self).__init__()

        self.paypal_manager = PayPalManager(cache_dir=cache_dir)
        self.paypal_manager.input_handler = input_handler

        self.created = False
        # Check whether we have logged in once
        if 'password' in self.paypal_manager.persistent_storage and 'email' in self.paypal_manager.persistent_storage:
            self.created = True

    def get_name(self):
        return 'PayPal'

    def get_identifier(self):
        return 'PP'

    def create_wallet(self, *args, **kwargs):
        # Creating a PayPal wallet is equivalent to logging in
        return self.paypal_manager.login()

    def get_balance(self):
        if not self.created:
            return succeed({
                'available': {'amount': 0, 'currency': 'EUR'},
                'pending': {'amount': 0, 'currency': 'EUR'},
                'total': {'amount': 0, 'currency': 'EUR'},
            })
        return self.paypal_manager.get_balance()

    def transfer(self, quantity, address):
        if self.get_balance()['total'] < quantity:
            raise InsufficientFunds()

        return self.paypal_manager.perform_payment(quantity, address, None)

    def monitor_transaction(self, amount):
        """
        Monitor an incoming transaction with a specific amount.
        """
        def on_transaction_done():
            self.balance -= amount

        return deferLater(reactor, 1, on_transaction_done)

    def get_address(self):
        if not self.created:
            return None
        return self.paypal_manager.persistent_storage['email']

    def get_transactions(self):
        # TODO(Martijn): implement this
        return []

    def min_unit(self):
        return 0.01
