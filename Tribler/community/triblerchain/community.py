from Tribler.pyipv8.ipv8.deprecated.payload import IntroductionResponsePayload

from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.community.triblerchain.database import TriblerChainDB
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.util import blocking_call_on_reactor_thread

MIN_TRANSACTION_SIZE = 1024 * 1024


class TriblerChainCommunity(TrustChainCommunity):
    """
    Community for reputation based on TrustChain tamper proof interaction history.
    """
    BLOCK_CLASS = TriblerChainBlock
    DB_CLASS = TriblerChainDB
    master_peer = Peer("3081a7301006072a8648ce3d020106052b81040027038192000405c66d3deddb1721787a247b2285118c06ce9fb"
                       "20ebd3546969fa2f4811fa92426637423d3bac1510f92b33e2ff5a785bf54eb3b28d29a77d557011d7d5241243c"
                       "9c89c987cd049404c4024999e1505fa96e1d6668234bde28a666d458d67251d17ff45185515a28967ddcf50503c"
                       "304750ae114f9bc857a79c03da1a9c9215ea07c91f166f24b6cfd1cf72309044fbd".decode('hex'))

    def __init__(self, *args, **kwargs):
        self.tribler_session = kwargs.pop('tribler_session', None)
        super(TriblerChainCommunity, self).__init__(*args, **kwargs)

    def should_sign(self, block):
        """
        Return whether we should sign a given block. For the TriblerChain, we only sign a block when we receive bytes.
        In our current design, only the person that should pay bytes to others initiates a signing request.
        This is true when considering payouts in the tunnels and when buying bytes on the market.
        """
        return block.transaction["down"] >= MIN_TRANSACTION_SIZE

    @blocking_call_on_reactor_thread
    def get_statistics(self, public_key=None):
        """
        Returns a dictionary with some statistics regarding the local trustchain database
        :returns a dictionary with statistics
        """
        if public_key is None:
            public_key = self.my_peer.public_key.key_to_bin()
        latest_block = self.persistence.get_latest(public_key)
        statistics = dict()
        statistics["id"] = public_key.encode("hex")
        interacts = self.persistence.get_num_unique_interactors(public_key)
        statistics["peers_that_pk_helped"] = interacts[0] if interacts[0] is not None else 0
        statistics["peers_that_helped_pk"] = interacts[1] if interacts[1] is not None else 0
        if latest_block:
            statistics["total_blocks"] = latest_block.sequence_number
            statistics["total_up"] = latest_block.transaction["total_up"]
            statistics["total_down"] = latest_block.transaction["total_down"]
            statistics["latest_block"] = dict(latest_block)

            # Set up/down
            statistics["latest_block"]["up"] = latest_block.transaction["up"]
            statistics["latest_block"]["down"] = latest_block.transaction["down"]
        else:
            statistics["total_blocks"] = 0
            statistics["total_up"] = 0
            statistics["total_down"] = 0
        return statistics

    def get_bandwidth_tokens(self, peer=None):
        """
        Get the bandwidth tokens for another peer.
        Currently this is just the difference in the amount of MBs exchanged with them.

        :param member: the peer we interacted with
        :type member: Peer
        :return: the amount of bandwidth tokens for this peer
        :rtype: int
        """
        if peer is None:
            peer = self.my_peer

        block = self.persistence.get_latest(peer.public_key.key_to_bin())
        if block:
            return block.transaction['total_up'] - block.transaction['total_down']

        return 0

    def bootstrap_new_identity(self, amount):
        """
        One-way payment channel.
        Create a new temporary identity, and transfer funds to the new identity.
        A different party can then take the result and do a transfer from the temporary identity to itself
        """

        # Create new identity for the temporary identity
        crypto = ECCrypto()
        tmp_peer = Peer(crypto.generate_key(u"curve25519"))

        # Create the transaction specification
        transaction = {
            'up': 0, 'down': amount
        }

        # Create the two half blocks that form the transaction
        local_half_block = TriblerChainBlock.create(transaction, self.persistence, self.my_peer.public_key.key_to_bin(),
                                                    link_pk=tmp_peer.public_key.key_to_bin())
        local_half_block.sign(self.my_peer.key)
        tmp_half_block = TriblerChainBlock.create(transaction, self.persistence, tmp_peer.public_key.key_to_bin(),
                                                  link=local_half_block, link_pk=self.my_peer.public_key.key_to_bin())
        tmp_half_block.sign(tmp_peer.key)

        self.persistence.add_block(local_half_block)
        self.persistence.add_block(tmp_half_block)

        # Create the bootstrapped identity format
        block = {'block_hash': tmp_half_block.hash.encode('base64'),
                 'sequence_number': tmp_half_block.sequence_number}

        result = {'private_key': tmp_peer.key.key_to_bin().encode('base64'),
                  'transaction': {'up': amount, 'down': 0}, 'block': block}
        return result
