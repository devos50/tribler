from base64 import b64encode

from twisted.internet.defer import succeed

from Tribler.community.market.wallet.wallet import Wallet, InsufficientFunds
from Tribler.dispersy.message import DelayPacketByMissingMember


class MultichainWallet(Wallet):
    """
    This class is responsible for handling your wallet of MultiChain credits.
    """

    def __init__(self, mc_community):
        super(MultichainWallet, self).__init__()

        self.mc_community = mc_community
        self.created = True
        self.check_negative_balance = True

    def get_identifier(self):
        return 'MC'

    def create_wallet(self, *args, **kwargs):
        pass

    def get_balance(self):
        total = self.mc_community.persistence.get_total(self.mc_community._public_key)
        return {'total_up': total[0], 'total_down': total[1], 'net': total[0] - total[1]}

    def transfer(self, quantity, candidate):
        if self.check_negative_balance and self.get_balance()['net'] < quantity:
            raise InsufficientFunds()

        # Send the block
        if not candidate.get_member():
            return self.wait_for_intro_of_candidate(candidate).addCallback(
                lambda _: self.send_signature(candidate, quantity))
        else:
            try:
                return self.send_signature(candidate, quantity)
            except DelayPacketByMissingMember:
                return self.wait_for_intro_of_candidate(candidate).addCallback(
                    lambda _: self.send_signature(candidate, quantity))

    def send_signature(self, candidate, quantity):
        self.mc_community.publish_signature_request_message(candidate, 0, int(quantity))
        latest_block = self.mc_community.persistence.get_latest_block(self.mc_community._public_key)

        return succeed(latest_block.previous_hash_requester)

    def wait_for_intro_of_candidate(self, candidate):
        self._logger.info("Sending introduction request in multichain to candidate %s", candidate)
        self.mc_community.add_discovered_candidate(candidate)
        new_candidate = self.mc_community.get_candidate(candidate.sock_addr)
        self.mc_community.create_introduction_request(new_candidate, False)
        return self.mc_community.wait_for_intro_of_candidate(new_candidate)

    def monitor_transaction(self, block_hash):
        """
        Monitor an incoming transaction with a specific hash.
        """
        return self.mc_community.wait_for_signature_request(str(block_hash))

    def get_address(self):
        return b64encode(self.mc_community._public_key)

    def get_transactions(self):
        # TODO(Martijn): implement this
        return []

    def min_unit(self):
        return 1
