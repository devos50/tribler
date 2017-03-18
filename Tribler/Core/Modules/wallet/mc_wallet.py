from base64 import b64encode

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.task import deferLater

from Tribler.Core.Modules.wallet.wallet import Wallet, InsufficientFunds
from Tribler.community.multichain.community import MultiChainCommunity


class MultichainWallet(Wallet):
    """
    This class is responsible for handling your wallet of MultiChain credits.
    """

    def __init__(self, session):
        super(MultichainWallet, self).__init__()

        self.session = session
        self.created = True

    def get_multichain_community(self):
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, MultiChainCommunity):
                return community

    def get_identifier(self):
        return 'mc'

    def create_wallet(self, *args, **kwargs):
        pass

    def get_balance(self):
        total = self.get_multichain_community().persistence.get_total(self.get_multichain_community()._public_key)

        #TODO(Martijn): fake the balance for now
        return {'total_up': 101000, 'total_down': 1000, 'net': 100000}

        if total == (-1, -1):
            return 0
        else:
            return int(max(0, total[0] - total[1]) / 2)

    def transfer(self, quantity, candidate):
        if self.get_balance()['net'] >= quantity:
            mb_quantity = quantity * 1024 * 1024
            self.get_multichain_community().schedule_block(candidate, 0, mb_quantity)
        else:
            raise InsufficientFunds()

    def monitor_transaction(self, mc_address, amount):
        """
        Monitor an incoming transaction. Returns a deferred that fires when we receive a signature request that matches
        the address and amount.
        """
        monitor_deferred = Deferred()
        # TODO(Martijn): hard-coded confirmation of transaction!
        deferLater(reactor, 2, lambda: monitor_deferred.callback(None))
        return monitor_deferred

    def get_address(self):
        return b64encode(self.get_multichain_community()._public_key)

    def get_transactions(self):
        # TODO(Martijn): implement this
        return []
