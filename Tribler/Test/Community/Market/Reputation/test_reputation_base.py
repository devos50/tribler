import os

from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.tradechain.block import TradeChainBlock
from Tribler.community.tradechain.database import TradeChainDB


class TestReputationBase(AbstractServer):
    """
    This class contains various utility methods to add transactions to the TradeChain.
    """

    def setUp(self, annotate=True):
        super(TestReputationBase, self).setUp(annotate=annotate)

        os.mkdir(os.path.join(self.session_base_dir, 'sqlite'))
        self.tradechain_db = TradeChainDB(self.session_base_dir)

    def insert_transaction(self, pubkey1, pubkey2, asset1_type, asset1_amount, asset2_type, asset2_amount):
        latest_block1 = self.tradechain_db.get_latest(pubkey1)
        latest_block2 = self.tradechain_db.get_latest(pubkey2)

        block = TradeChainBlock()
        block.public_key = pubkey1
        if latest_block1:
            block.sequence_number = latest_block1.sequence_number + 1

        block.link_public_key = pubkey2
        if latest_block2:
            block.link_sequence_number = latest_block2.sequence_number + 1

        block.asset1_type = asset1_type
        block.asset1_amount = asset1_amount
        block.asset2_type = asset2_type
        block.asset2_amount = asset2_amount

        self.tradechain_db.add_block(block)
