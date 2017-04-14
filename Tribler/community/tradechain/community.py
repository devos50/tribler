"""
The TradeChain Community is the first step in an incremental approach in building a new reputation system.
This reputation system builds a tamper proof interaction history contained in a chain data-structure.
Every node has a chain and these chains intertwine by blocks shared by chains.
"""
import logging
import base64
from twisted.internet.defer import inlineCallbacks, Deferred

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.community import Community
from Tribler.dispersy.message import Message, DelayPacketByMissingMember
from Tribler.dispersy.conversion import DefaultConversion

from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.community.tradechain.block import TradeChainBlock, ValidationResult, GENESIS_SEQ, UNKNOWN_SEQ
from Tribler.community.tradechain.payload import HalfBlockPayload, CrawlRequestPayload
from Tribler.community.tradechain.database import TradeChainDB
from Tribler.community.tradechain.conversion import TradeChainConversion

HALF_BLOCK = u"half_block"
CRAWL = u"crawl"
MIN_TRANSACTION_SIZE = 1024*1024


class TradeChainCommunity(Community):
    """
    Community for reputation based on TradeChain tamper proof interaction history.
    """

    def __init__(self, *args, **kwargs):
        super(TradeChainCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.persistence = TradeChainDB(self.dispersy.working_directory)

        self.expected_intro_responses = {}

        self.logger.debug("The tradechain community started with Public Key: %s",
                          self.my_member.public_key.encode("hex"))

    @classmethod
    def get_master_members(cls, dispersy):
        master_key = "3081a7301006072a8648ce3d020106052b810400270381920004016ca22eca84f88c8cd2df03f95bb9f5534081ac" \
                     "83ee306fedb2d36c44e766afecc62732f45e153cf419bd4ab54744a692b5d459cbd12b5cc1a90b58f87a8c3d8d57" \
                     "0c9c0d6094a506f5432b4c8b640d2f2d72fef14f41781924248d9ce91a616741571424b73a430ed2b416bcdb69cd" \
                     "d4766b459ef804c43aa6cbfdc1e1a17411a3d9fd1e2774ee1b744e26cf2dee87"
        return [dispersy.get_member(public_key=master_key.decode("HEX"))]

    def initialize(self, tribler_session=None):
        super(TradeChainCommunity, self).initialize()

    def initiate_meta_messages(self):
        """
        Setup all message that can be received by this community and the super classes.
        :return: list of meta messages.
        """
        return super(TradeChainCommunity, self).initiate_meta_messages() + [
            Message(self, HALF_BLOCK,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    HalfBlockPayload(),
                    self._generic_timeline_check,
                    self.received_half_block),
            Message(self, CRAWL,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlRequestPayload(),
                    self._generic_timeline_check,
                    self.received_crawl_request)]

    def initiate_conversions(self):
        return [DefaultConversion(self), TradeChainConversion(self)]

    def send_block(self, candidate, block):
        self.logger.debug("Sending block to %s (%s)", candidate.get_member().public_key.encode("hex")[-8:], block)
        message = self.get_meta_message(HALF_BLOCK).impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(block,))
        try:
            self.dispersy.store_update_forward([message], False, False, True)
        except DelayPacketByMissingMember:
            self.logger.warn("Missing member in TradeChain community to send signature request to")

    def on_introduction_response(self, messages):
        super(TradeChainCommunity, self).on_introduction_response(messages)
        for message in messages:
            if message.candidate.sock_addr in self.expected_intro_responses:
                self.expected_intro_responses[message.candidate.sock_addr].callback(None)
                del self.expected_intro_responses[message.candidate.sock_addr]

    def wait_for_intro_of_candidate(self, candidate):
        """
        Returns a Deferred that fires when we receive an introduction response from a given candidate.
        """
        response_deferred = Deferred()
        self.expected_intro_responses[candidate.sock_addr] = response_deferred
        return response_deferred

    def sign_block(self, candidate, asset1_type=None, asset1_amount=None,
                   asset2_type=None, asset2_amount=None, linked=None):
        """
        Create, sign, persist and send a block signed message
        :param candidate: The peer with whom you have interacted, as a dispersy candidate
        :param asset1_type: The type of asset 1 (string)
        :param asset1_amount: The amount of asset 2 (string)
        :param asset2_type: The type of asset 2 (string)
        :param asset2_amount: The amount of asset 2 (string)
        """

        # NOTE to the future: This method reads from the database, increments and then writes back. If in some future
        # this method is allowed to execute in parallel, be sure to lock from before .create upto after .add_block
        assert asset1_type is None and asset1_amount is None and asset2_type is None and asset2_amount is None \
               and linked is not None or asset1_type is not None and asset1_amount is not None \
               and asset2_type is not None and asset2_amount is not None and linked is None, \
            "Either provide a linked block or asset types/amounts, not both"
        assert linked is None or linked.link_public_key == self.my_member.public_key, \
            "Cannot counter sign block not addressed to me"
        assert linked is None or linked.link_sequence_number == UNKNOWN_SEQ, \
            "Cannot counter sign block that is not a request"

        if candidate.get_member():
            if linked is None:
                block = TradeChainBlock.create(self.persistence, self.my_member.public_key)
                block.asset1_type = asset1_type
                block.asset1_amount = asset1_amount
                block.asset2_type = asset2_type
                block.asset2_amount = asset2_amount
                block.link_public_key = candidate.get_member().public_key
            else:
                block = TradeChainBlock.create(self.persistence, self.my_member.public_key, linked)
            block.sign(self.my_member.private_key)
            validation = block.validate(self.persistence)
            self.logger.info("Signed block to %s (%s) validation result %s",
                             candidate.get_member().public_key.encode("hex")[-8:], block, validation)
            if validation[0] != ValidationResult.partial_next and validation[0] != ValidationResult.valid:
                self.logger.error("Signed block did not validate?!")
            else:
                self.persistence.add_block(block)
                self.send_block(candidate, block)
        else:
            self.logger.warn("Candidate %s has no associated member?! Unable to sign block.", candidate)

    def received_half_block(self, messages):
        """
        We've received a half block, either because we sent a SIGNED message to some one or we are crawling
        :param messages The half block messages
        """
        self.logger.debug("Received %d half block messages.", len(messages))
        for message in messages:
            blk = message.payload.block
            validation = blk.validate(self.persistence)
            self.logger.debug("Block validation result %s, %s, (%s)", validation[0], validation[1], blk)
            if validation[0] == ValidationResult.invalid:
                continue
            elif not self.persistence.contains(blk):
                self.persistence.add_block(blk)
            else:
                self.logger.debug("Received already known block (%s)", blk)

            # Is this a request, addressed to us, and have we not signed it already?
            if blk.link_sequence_number != UNKNOWN_SEQ or \
                    blk.link_public_key != self.my_member.public_key or \
                    self.persistence.get_linked(blk) is not None:
                continue

            self.logger.info("Received request block addressed to us (%s)", blk)

            # TODO(Martijn): only sign if we have done this transaction in the market!

            # It is important that the request matches up with its previous block, gaps cannot be tolerated at
            # this point. We already dropped invalids, so here we delay this message if the result is partial,
            # partial_previous or no-info. We send a crawl request to the requester to (hopefully) close the gap
            if validation[0] == ValidationResult.partial_previous or validation[0] == ValidationResult.partial or \
                    validation[0] == ValidationResult.no_info:
                # Note that this code does not cover the scenario where we obtain this block indirectly.

                # Are we already waiting for this crawl to happen?
                # For example: it's taking longer than 5 secs or the block message reached us twice via different paths
                if self.is_pending_task_active("crawl_%s" % blk.hash):
                    continue

                self.send_crawl_request(message.candidate, max(GENESIS_SEQ, blk.sequence_number - 5))

                # Make sure we get called again after a while. Note that the cleanup task on pend will prevent
                # us from waiting on the peer forever,
                self.register_task("crawl_%s" % blk.hash, reactor.callLater(5.0, self.received_half_block, [message]))
            else:
                self.sign_block(message.candidate, None, None, None, None, blk)

    def send_crawl_request(self, candidate, sequence_number=None):
        sq = sequence_number
        if sequence_number is None:
            blk = self.persistence.get_latest(candidate.get_member().public_key)
            sq = blk.sequence_number if blk else GENESIS_SEQ
        sq = max(GENESIS_SEQ, sq)
        self.logger.info("Requesting crawl of node %s:%d", candidate.get_member().public_key.encode("hex")[-8:], sq)
        message = self.get_meta_message(CRAWL).impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(sq,))
        self.dispersy.store_update_forward([message], False, False, True)

    def received_crawl_request(self, messages):
        self.logger.debug("Received %d crawl messages.", len(messages))
        for message in messages:
            self.logger.info("Received crawl request from node %s for sequence number %d",
                             message.candidate.get_member().public_key.encode("hex")[-8:],
                             message.payload.requested_sequence_number)
            blocks = self.persistence.crawl(self.my_member.public_key, message.payload.requested_sequence_number)
            count = len(blocks)
            for blk in blocks:
                self.send_block(message.candidate, blk)
            self.logger.info("Sent %d blocks", count)

    @blocking_call_on_reactor_thread
    def get_statistics(self, public_key=None):
        """
        Returns a dictionary with some statistics regarding the local tradechain database
        :returns a dictionary with statistics
        """
        if public_key is None:
            public_key = self.my_member.public_key
        latest_block = self.persistence.get_latest(public_key)
        statistics = dict()
        statistics["id"] = public_key.encode("hex")
        interacts = self.persistence.get_num_unique_interactors(public_key)
        statistics["peers_that_pk_helped"] = interacts[0] if interacts[0] is not None else 0
        statistics["peers_that_helped_pk"] = interacts[1] if interacts[1] is not None else 0
        if latest_block:
            statistics["total_blocks"] = latest_block.sequence_number
            statistics["total_up"] = latest_block.total_up
            statistics["total_down"] = latest_block.total_down
            statistics["latest_block"] = dict(latest_block)
        else:
            statistics["total_blocks"] = 0
            statistics["total_up"] = 0
            statistics["total_down"] = 0
        return statistics

    @inlineCallbacks
    def unload_community(self):
        self.logger.debug("Unloading the TradeChain Community.")
        yield super(TradeChainCommunity, self).unload_community()
        # Close the persistence layer
        self.persistence.close()


class TradeChainCommunityCrawler(TradeChainCommunity):
    """
    Extended TradeChainCommunity that also crawls other TradeChainCommunities.
    It requests the chains of other TradeChains.
    """

    # Time the crawler waits between crawling a new candidate.
    CrawlerDelay = 5.0

    def on_introduction_response(self, messages):
        super(TradeChainCommunityCrawler, self).on_introduction_response(messages)
        for message in messages:
            self.send_crawl_request(message.candidate)

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(self.CrawlerDelay, now=False)
