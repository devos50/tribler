"""
File containing the TradeChain Community.
"""
import logging
import base64
from twisted.internet.defer import inlineCallbacks, Deferred

from twisted.internet.task import LoopingCall
from Tribler.community.tradechain.conversion import split_function, TradeChainConversion, GENESIS_ID
from Tribler.community.tradechain.database import TradeChainDB, DatabaseBlock
from Tribler.community.tradechain.payload import SignaturePayload, CrawlRequestPayload, CrawlResponsePayload, \
    CrawlResumePayload
from Tribler.dispersy.authentication import DoubleMemberAuthentication, MemberAuthentication
from Tribler.dispersy.resolution import PublicResolution
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.destination import CandidateDestination
from Tribler.dispersy.community import Community
from Tribler.dispersy.message import Message, DelayPacketByMissingMember
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.util import blocking_call_on_reactor_thread

SIGNATURE = u"signature"
CRAWL_REQUEST = u"crawl_request"
CRAWL_RESPONSE = u"crawl_response"
CRAWL_RESUME = u"crawl_resume"


class TradeChainCommunity(Community):
    """
    Community for reputation based on TradeChain tamper proof interaction history.
    """

    def __init__(self, *args, **kwargs):
        super(TradeChainCommunity, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.notifier = None
        self._private_key = self.my_member.private_key
        self._public_key = self.my_member.public_key
        self.persistence = TradeChainDB(self.dispersy, self.dispersy.working_directory)
        self.logger.debug("The tradechain community started with Public Key: %s", base64.encodestring(self._public_key))

        self.expected_intro_responses = {}
        self.expected_sig_requests = {}

    def initialize(self, tribler_session=None):
        super(TradeChainCommunity, self).initialize()

    @classmethod
    def get_master_members(cls, dispersy):
        master_key = "3081a7301006072a8648ce3d020106052b810400270381920004016ca22eca84f88c8cd2df03f95bb9f5534081ac" \
                     "83ee306fedb2d36c44e766afecc62732f45e153cf419bd4ab54744a692b5d459cbd12b5cc1a90b58f87a8c3d8d57" \
                     "0c9c0d6094a506f5432b4c8b640d2f2d72fef14f41781924248d9ce91a616741571424b73a430ed2b416bcdb69cd" \
                     "d4766b459ef804c43aa6cbfdc1e1a17411a3d9fd1e2774ee1b744e26cf2dee87"
        master_key_hex = master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]

    def initiate_meta_messages(self):
        """
        Setup all message that can be received by this community and the super classes.
        :return: list of meta messages.
        """
        return super(TradeChainCommunity, self).initiate_meta_messages() + [
            Message(self, SIGNATURE,
                    DoubleMemberAuthentication(
                        allow_signature_func=self.allow_signature_request, split_payload_func=split_function),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    SignaturePayload(),
                    self._generic_timeline_check,
                    self.received_signature_response),
            Message(self, CRAWL_REQUEST,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlRequestPayload(),
                    self._generic_timeline_check,
                    self.received_crawl_request),
            Message(self, CRAWL_RESPONSE,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlResponsePayload(),
                    self._generic_timeline_check,
                    self.received_crawl_response),
            Message(self, CRAWL_RESUME,
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    CrawlResumePayload(),
                    self._generic_timeline_check,
                    self.received_crawl_resumption)]

    def initiate_conversions(self):
        return [DefaultConversion(self), TradeChainConversion(self)]

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

    def wait_for_signature_request_of_member(self, member, up, down):
        """
        Returns a Deferred that fires when we receive a signature from a given member with some amount to sign.
        Used in the market community so we can monitor transactions.
        """
        response_deferred = Deferred()
        self.expected_sig_requests[member.public_key] = response_deferred
        return response_deferred

    def schedule_block(self, candidate, asset1_type, asset1_amount, asset2_type, asset2_amount):
        """
        Schedule a block for the current outstanding amounts
        :param candidate: The peer with whom you have interacted, as a dispersy candidate
        :param asset1_type: The type of asset 1 (string)
        :param asset1_amount: The amount of asset 2 (string)
        :param asset2_type: The type of asset 2 (string)
        :param asset2_amount: The amount of asset 2 (string)
        """
        asset_type_map = {'BTC': 0, 'MC': 1}

        self.logger.info("TRADECHAIN: Schedule Block called. Candidate: %s" % candidate)
        self.add_discovered_candidate(candidate)
        if candidate and candidate.get_member():
            # Try to send the request
            try:
                self.publish_signature_request_message(candidate, asset_type_map[asset1_type], asset1_amount,
                                                       asset_type_map[asset2_type], asset2_amount)
            except DelayPacketByMissingMember:
                self.logger.warn("Missing member in TradeChain community to send signature request to")
        else:
            self.logger.warn(
                "No valid candidate found for: %s to request block from.", candidate)

    def publish_signature_request_message(self, candidate, asset1_type, asset1_amount, asset2_type, asset2_amount):
        """
        Creates and sends out a signed signature_request message
        Returns true upon success
        :param candidate: The candidate that the signature request will be sent to.
        :param asset1_type: The type of asset 1 (string)
        :param asset1_amount: The amount of asset 2 (string)
        :param asset2_type: The type of asset 2 (string)
        :param asset2_amount: The amount of asset 2 (string)
        return (bool) if request is sent.
        """
        message = self.create_signature_request_message(candidate, asset1_type, asset1_amount,
                                                        asset2_type, asset2_amount)
        self.create_signature_request(candidate, message, self.allow_signature_response)
        self.persist_signature_request(message)
        return True

    def create_signature_request_message(self, candidate, asset1_type, asset1_amount, asset2_type, asset2_amount):
        """
        Create a signature request message using the current time stamp.
        :param candidate: The candidate that the signature request will be sent to.
        :param asset1_type: The type of asset 1 (string)
        :param asset1_amount: The amount of asset 2 (string)
        :param asset2_type: The type of asset 2 (string)
        :param asset2_amount: The amount of asset 2 (string)
        :return: Signature_request message ready for distribution.
        """
        # Instantiate the data
        total_btc_requester, total_mc_requester = (5, 5)  # TODO(Martijn): always hardcoded for now!
        # Instantiate the personal information
        sequence_number_requester = self._get_next_sequence_number()
        previous_hash_requester = self._get_latest_hash()

        payload = (asset1_type, asset1_amount, asset2_type, asset2_amount, total_btc_requester, total_mc_requester,
                   sequence_number_requester, previous_hash_requester)
        meta = self.get_meta_message(SIGNATURE)

        message = meta.impl(authentication=([self.my_member, candidate.get_member()],),
                            distribution=(self.claim_global_time(),),
                            payload=payload)
        return message

    def allow_signature_request(self, message):
        """
        We've received a signature request message, we must either:
            a. Create and sign the response part of the message, send it back, and persist the block.
            b. Drop the message. (Future work: notify the sender of dropping)
            :param message The message containing the received signature request.
        """
        #self.logger.info("Received signature request for: [Up = " + str(message.payload.up) + "MB | Down = " +
        #                 str(message.payload.down) + " MB]")
        # TODO: This code always signs a request. Checks and rejects should be inserted here!
        # TODO: Like basic total_up == previous_total_up + block.up or more sophisticated chain checks.
        payload = message.payload

        # The up and down values are reversed for the responder.
        total_btc_responder, total_mc_responder = (5, 5)  # TODO(Martijn): always hardcoded for now!
        sequence_number_responder = self._get_next_sequence_number()
        previous_hash_responder = self._get_latest_hash()

        payload = (payload.asset1_type, payload.asset1_amount,
                   payload.asset2_type, payload.asset2_amount,
                   payload.total_btc_requester, payload.total_mc_requester,
                   payload.sequence_number_requester, payload.previous_hash_requester,
                   total_btc_responder, total_mc_responder,
                   sequence_number_responder, previous_hash_responder)

        meta = self.get_meta_message(SIGNATURE)

        message = meta.impl(authentication=(message.authentication.members, message.authentication.signatures),
                            distribution=(message.distribution.global_time,),
                            payload=payload)
        self.persist_signature_response(message)
        self.logger.info("Sending signature response.")

        request_member = message.authentication.signed_members[0][1].public_key
        if request_member in self.expected_sig_requests:
            self.expected_sig_requests[request_member].callback(None)
            del self.expected_sig_requests[request_member]

        return message

    def allow_signature_response(self, request, response, modified):
        """
        We've received a signature response message after sending a request, we must return either:
            a. True, if we accept this message
            b. False, if not (because of inconsistencies in the payload)
            :param request The original message as send by this node
            :param response The response message received
            :param modified (bool) True if the message was modified
        """
        if not response:
            self.logger.info("Timeout received for signature request.")
            return False
        else:
            # TODO: Check whether we are expecting a response
            self.logger.info("Signature response received. Modified: %s", modified)

            return (request.payload.sequence_number_requester == response.payload.sequence_number_requester and
                    request.payload.previous_hash_requester == response.payload.previous_hash_requester and modified)

    def received_signature_response(self, messages):
        """
        We've received a valid signature response and must process this message.
        :param messages The received, and validated signature response messages
        """
        self.logger.info("Valid %s signature response(s) received.", len(messages))
        for message in messages:
            self.update_signature_response(message)

    def persist_signature_response(self, message):
        """
        Persist the signature response message, when this node has not yet persisted the corresponding request block.
        A hash will be created from the message and this will be used as an unique identifier.
        :param message:
        """
        block = DatabaseBlock.from_signature_response_message(message)
        self.logger.info("Persisting sr: %s", base64.encodestring(block.hash_requester).strip())
        self.persistence.add_block(block)

    def update_signature_response(self, message):
        """
        Update the signature response message, when this node has already persisted the corresponding request block.
        A hash will be created from the message and this will be used as an unique identifier.
        :param message:
        """
        block = DatabaseBlock.from_signature_response_message(message)
        self.logger.info("Persisting sr: %s", base64.encodestring(block.hash_requester).strip())
        self.persistence.update_block_with_responder(block)

    def persist_signature_request(self, message):
        """
        Persist the signature request message as a block.
        The block will be updated when a response is received.
        :param message:
        """
        block = DatabaseBlock.from_signature_request_message(message)
        self.logger.info("Persisting sr: %s", base64.encodestring(block.hash_requester).strip())
        self.persistence.add_block(block)

    def send_crawl_request(self, candidate, sequence_number=None):
        if sequence_number is None:
            sequence_number = self.persistence.get_latest_sequence_number(candidate.get_member().public_key)
        self.logger.info("Crawler: Requesting crawl from node %s, from sequence number %d",
                         base64.encodestring(candidate.get_member().mid).strip(), sequence_number)
        meta = self.get_meta_message(CRAWL_REQUEST)
        message = meta.impl(authentication=(self.my_member,),
                            distribution=(self.claim_global_time(),),
                            destination=(candidate,),
                            payload=(sequence_number,))
        self.dispersy.store_update_forward([message], False, False, True)

    def received_crawl_request(self, messages):
        for message in messages:
            self.logger.info("Crawler: Received crawl request from node %s, from sequence number %d",
                             base64.encodestring(message.candidate.get_member().mid).strip(),
                              message.payload.requested_sequence_number)
            self.crawl_requested(message.candidate, message.payload.requested_sequence_number)

    def crawl_requested(self, candidate, sequence_number):
        blocks = self.persistence.get_blocks_since(self._public_key, sequence_number)
        if len(blocks) > 0:
            self.logger.debug("Crawler: Sending %d blocks", len(blocks))
            messages = [self.get_meta_message(CRAWL_RESPONSE)
                            .impl(authentication=(self.my_member,),
                                  distribution=(self.claim_global_time(),),
                                  destination=(candidate,),
                                  payload=block.to_payload()) for block in blocks]
            self.dispersy.store_update_forward(messages, False, False, True)
            if len(blocks) > 1:
                # we sent more than 1 block. Send a resumption token so the other side knows it should continue crawling
                # last_block = blocks[-1]
                # resumption_number = last_block.sequence_number_requster if
                # last_block.mid_requester == self._mid else last_block.sequence_number_responder
                message = self.get_meta_message(CRAWL_RESUME).impl(authentication=(self.my_member,),
                                                                   distribution=(self.claim_global_time(),),
                                                                   destination=(candidate,),
                                                                   # payload=(resumption_number))
                                                                   payload=())
                self.dispersy.store_update_forward([message], False, False, True)
        else:
            # This is slightly worrying since the last block should always be returned.
            # Or rather, the other side is requesting blocks starting from a point in the future.
            self.logger.info("Crawler: No blocks")

    def received_crawl_response(self, messages):
        self.logger.debug("Crawler: Valid %d block response(s) received.", len(messages))
        for message in messages:
            requester = self.dispersy.get_member(public_key=message.payload.public_key_requester)
            responder = self.dispersy.get_member(public_key=message.payload.public_key_responder)
            block = DatabaseBlock.from_block_response_message(message, requester, responder)
            # Create the hash of the message
            if not self.persistence.contains(block.hash_requester):
                self.logger.info("Crawler: Persisting sr: %s from ip (%s:%d)",
                                 base64.encodestring(block.hash_requester).strip(),
                                 message.candidate.sock_addr[0],
                                 message.candidate.sock_addr[1])
                self.persistence.add_block(block)
            else:
                self.logger.debug("Crawler: Received already known block")

    def received_crawl_resumption(self, messages):
        self.logger.info("Crawler: Valid %s crawl resumptions received.", len(messages))
        for message in messages:
            self.send_crawl_request(message.candidate)

    @blocking_call_on_reactor_thread
    def get_statistics(self):
        """
        Returns a dictionary with some statistics regarding the local tradechain database
        :returns a dictionary with statistics
        """
        statistics = dict()
        statistics["self_id"] = base64.encodestring(self._public_key).strip()
        statistics["self_total_blocks"] = self.persistence.get_latest_sequence_number(self._public_key)
        (statistics["self_total_up_mb"],
         statistics["self_total_down_mb"]) = self.persistence.get_total(self._public_key)
        (statistics["self_peers_helped"],
         statistics["self_peers_helped_you"]) = self.persistence.get_num_unique_interactors(self._public_key)
        latest_block = self.persistence.get_latest_block(self._public_key)
        if latest_block:
            statistics["latest_block_insert_time"] = str(latest_block.insert_time)
            statistics["latest_block_id"] = base64.encodestring(latest_block.hash_requester).strip()
            statistics["latest_block_requester_id"] = base64.encodestring(latest_block.public_key_requester).strip()
            statistics["latest_block_responder_id"] = base64.encodestring(latest_block.public_key_responder).strip()
            statistics["latest_block_up_mb"] = str(latest_block.up)
            statistics["latest_block_down_mb"] = str(latest_block.down)
        else:
            statistics["latest_block_insert_time"] = ""
            statistics["latest_block_id"] = ""
            statistics["latest_block_requester_id"] = ""
            statistics["latest_block_responder_id"] = ""
            statistics["latest_block_up_mb"] = ""
            statistics["latest_block_down_mb"] = ""
        return statistics

    def _get_next_total(self, up, down):
        """
        Returns the next total numbers of up and down incremented with the current interaction up and down metric.
        :param up: Up metric for the interaction.
        :param down: Down metric for the interaction.
        :return: (total_up (int), total_down (int)
        """
        total_up, total_down = self.persistence.get_total(self._public_key)
        return total_up + up, total_down + down

    def _get_next_sequence_number(self):
        return self.persistence.get_latest_sequence_number(self._public_key) + 1

    def _get_latest_hash(self):
        previous_hash = self.persistence.get_latest_hash(self._public_key)
        return previous_hash if previous_hash else GENESIS_ID

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
