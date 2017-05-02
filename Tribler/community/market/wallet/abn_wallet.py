from twisted.internet import reactor
from twisted.internet.defer import succeed, Deferred, fail, inlineCallbacks, returnValue
from twisted.internet.task import deferLater, LoopingCall

from Tribler.community.market.wallet.wallet import Wallet, InsufficientFunds
from Tribler.internetofmoney.Managers.ABN.ABNManager import ABNManager


class ABNWallet(Wallet):
    """
    This class manages an ABN AMRO wallet.
    """

    def __init__(self, input_handler, cache_dir='.'):
        super(ABNWallet, self).__init__()

        self.abn_manager = ABNManager(cache_dir=cache_dir)
        self.abn_manager.input_handler = lambda required_input: input_handler(required_input,
                                                                              bank_name=self.get_name())

        self.created = False
        # Check whether we have logged in once
        if 'identification_code' in self.abn_manager.persistent_storage:
            self.created = True

    def get_name(self):
        return 'ABN'

    def get_identifier(self):
        return 'ABN'

    def create_wallet(self, *args, **kwargs):
        return self.abn_manager.register()

    def get_balance(self):
        if not self.created:
            return succeed({
                'available': 0,
                'pending': 0,
                'currency': '-'
            })
        return self.abn_manager.get_balance()

    @inlineCallbacks
    def transfer(self, quantity, address):
        rand_transaction_id = self.generate_txid()
        balance = yield self.get_balance()
        if balance['available'] < quantity:
            returnValue(fail(InsufficientFunds()))
        else:
            _ = yield self.abn_manager.perform_payment(quantity, address, rand_transaction_id)
            returnValue(rand_transaction_id)

    def monitor_transaction(self, transaction_id):
        """
        Monitor an incoming transaction with a specific id.
        """
        print "will monitor for %s" % transaction_id
        monitor_deferred = Deferred()

        def monitor_loop():
            def on_transactions(transactions):
                for transaction in transactions:
                    print "DESCRIPTION of %s: %s" % (transaction['id'], transaction['description'])
                    if transaction_id in transaction['description']:
                        monitor_deferred.callback(None)
                        monitor_lc.stop()
            return self.get_transactions().addCallback(on_transactions)

        monitor_lc = LoopingCall(monitor_loop)
        monitor_lc.start(5)

        return monitor_deferred

    def get_address(self):
        if not self.created:
            return ''
        return str(self.abn_manager.persistent_storage['account_number'])

    def get_transactions(self):
        return self.abn_manager.get_transactions()

    def min_unit(self):
        return 0.01
