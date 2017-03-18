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
        return {'total_up': total[0], 'total_down': total[1], 'net': total[0] - total[1]}

    def transfer(self, quantity, candidate):
        if self.get_balance()['net'] >= quantity:
            mb_quantity = quantity * 1024 * 1024
            self.get_multichain_community().schedule_block(candidate, 0, mb_quantity)
        else:
            raise InsufficientFunds()

    def monitor_transaction(self, mc_member, amount):
        """
        Monitor an incoming transaction. Returns a deferred that fires when we receive a signature request that matches
        the address and amount.
        """
        return self.get_multichain_community().wait_for_signature_request_of_member(mc_member, 0, amount)

    def get_address(self):
        return b64encode(self.get_multichain_community()._public_key)

    def get_transactions(self):
        # TODO(Martijn): implement this
        return []
