from Tribler.community.tradechain.database import TradeChainDB


class ReputationManager(object):

    def __init__(self, blocks):
        self.blocks = blocks

    def compute(self, own_public_key):
        """
        Compute the reputation based on the data in the TradeChain database.
        """
        raise NotImplementedError()
