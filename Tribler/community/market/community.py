from __future__ import absolute_import

import logging
import random
from binascii import hexlify, unhexlify
from math import radians, sin, asin, sqrt, cos

from twisted.internet import reactor
from twisted.internet.defer import Deferred, fail, inlineCallbacks, succeed
from twisted.internet.task import LoopingCall

from Tribler.Core.simpledefs import NTFY_MARKET_ON_ASK, NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID,\
    NTFY_MARKET_ON_BID_TIMEOUT
from Tribler.Core.simpledefs import NTFY_UPDATE
from Tribler.community.market import MAX_ORDER_TIMEOUT
from Tribler.community.market.core import DeclineMatchReason, DeclinedTradeReason
from Tribler.community.market.core.match_queue import MatchPriorityQueue
from Tribler.community.market.core.matching_engine import MatchingEngine, PriceTimeStrategy, TaxiStrategy
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.order import OrderId, OrderNumber
from Tribler.community.market.core.order_manager import OrderManager
from Tribler.community.market.core.order_repository import DatabaseOrderRepository, MemoryOrderRepository
from Tribler.community.market.core.orderbook import DatabaseOrderBook, OrderBook
from Tribler.community.market.core.tick import Ask, Bid, Tick
from Tribler.community.market.core.timeout import Timeout
from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.trade import CounterTrade, DeclinedTrade, ProposedTrade, Trade, StartTrade
from Tribler.community.market.database import MarketDB
from Tribler.community.market.payload import DeclineMatchPayload, DeclineTradePayload, InfoPayload, \
    MatchPayload, OrderbookSyncPayload, \
    PingPongPayload, TradePayload, OrderPayload, CancelOrderPayload, CompletedTradePayload
from Tribler.community.market.settings import MatchingSettings, SYNC_POLICY_NONE, SYNC_POLICY_NEIGHBOURS, \
    DISSEMINATION_POLICY_NEIGHBOURS, DISSEMINATION_POLICY_RANDOM
from Tribler.pyipv8.ipv8.community import Community, lazy_wrapper
from Tribler.pyipv8.ipv8.messaging.bloomfilter import BloomFilter
from Tribler.pyipv8.ipv8.messaging.payload_headers import BinMemberAuthenticationPayload
from Tribler.pyipv8.ipv8.messaging.payload_headers import GlobalTimeDistributionPayload
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.requestcache import NumberCache, RandomNumberCache, RequestCache


# Message definitions
MSG_CANCEL_ORDER = 5
MSG_ORDER = 6
MSG_MATCH = 7
MSG_MATCH_ACCEPT = 8
MSG_MATCH_DECLINE = 9
MSG_PROPOSED_TRADE = 10
MSG_DECLINED_TRADE = 11
MSG_COUNTER_TRADE = 12
MSG_START_TRADE = 13
MSG_BOOK_SYNC = 19
MSG_PING = 20
MSG_PONG = 21
MSG_MATCHED_TRADE_COMPLETE = 22
MSG_COMPLETE_TRADE = 23


class MatchCache(NumberCache):
    """
    This cache keeps track of incoming match messages for a specific order.
    """

    def __init__(self, community, order):
        super(MatchCache, self).__init__(community.request_cache, u"match", int(order.order_id.order_number))
        self.community = community
        self.order = order
        self.matches = {}
        self.schedule_task = None
        self.schedule_task_done = False
        self.outstanding_request = None
        self.received_responses_ids = set()
        self.queue = MatchPriorityQueue(self.order)
        self.tries = {}  # Keep track of the number of tries

    @property
    def timeout_delay(self):
        return 7200.0

    def haversine(self, lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371 # Radius of earth in kilometers. Use 3956 for miles
        return c * r

    def add_match(self, match_payload):
        """
        Add a match to the queue.
        """
        if self.order.status != "open":
            self._logger.info("Ignoring match payload, order %s not open anymore", self.order.order_id)
            return

        other_order_id = OrderId(match_payload.trader_id, match_payload.order_number)
        if other_order_id not in self.matches:
            self.matches[other_order_id] = []

        # We do not want to add the match twice
        exists = False
        for match_payload in self.matches[other_order_id]:
            match_order_id = OrderId(match_payload.trader_id, match_payload.order_number)
            if match_order_id == other_order_id:
                exists = True
                break

        if not exists:
            self.matches[other_order_id].append(match_payload)

        if not self.queue.contains_order(other_order_id) and not (self.outstanding_request and self.outstanding_request[2] == other_order_id):
            distance = self.haversine(self.order.longitude, self.order.latitude, match_payload.longitude, match_payload.latitude)
            self._logger.debug("Adding match payload with own order id %s and other id %s to queue (distance: %f)",
                               self.order.order_id, other_order_id, distance)
            self.queue.insert(0, distance, other_order_id)

        if not self.schedule_task:
            # Schedule a timer
            self._logger.info("Scheduling batch match of order %s" % str(self.order.order_id))
            self.schedule_task = reactor.callLater(self.community.settings.match_window, self.start_process_matches)
        elif self.schedule_task_done and not self.outstanding_request:
            # If we are currently not processing anything and the schedule task is done, process the matches
            self.process_match()

    def start_process_matches(self):
        """
        Start processing the batch of matches.
        """
        self.schedule_task_done = True
        self._logger.info("Processing incoming matches for order %s", self.order.order_id)

        # It could be that the order has already been completed while waiting - we should let the matchmaker know
        if self.order.status != "open":
            self._logger.info("Order %s is already fulfilled - notifying matchmakers", self.order.order_id)
            for _, matches in self.matches.iteritems():
                for match_payload in matches:
                    # Send a declined trade back
                    other_order_id = OrderId(match_payload.trader_id, match_payload.order_number)
                    self.community.send_decline_match_message(self.order, other_order_id,
                                                              match_payload.matchmaker_trader_id,
                                                              DeclineMatchReason.ORDER_COMPLETED)
            self.matches = {}
            return

        self.process_match()

    def haversine(self, lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371 # Radius of earth in kilometers. Use 3956 for miles
        return c * r

    def process_match(self):
        """
        Process the first eligible match. First, we sort the list based on price.
        """
        item = self.queue.delete()
        if not item:
            self._logger.info("Done with processsing match queue for order %s!", self.order.order_id)
        else:
            retries, _, other_order_id = item
            self.outstanding_request = item
            if retries == 0:
                delay = 0
            else:
                delay = random.uniform(0.5, 1)
            reactor.callLater(delay, self.community.accept_match_and_propose, self.order, other_order_id)

    def received_decline_trade(self, other_order_id, decline_reason):
        """
        The counterparty refused to trade - update the cache accordingly.
        """
        self.received_responses_ids.add(other_order_id)
        if decline_reason == DeclinedTradeReason.ORDER_COMPLETED and other_order_id in self.matches:
            # Let the matchmakers know that the order is complete
            for match_payload in self.matches[other_order_id]:
                self.community.send_decline_match_message(self.order,
                                                          other_order_id,
                                                          match_payload.matchmaker_trader_id,
                                                          DeclineMatchReason.OTHER_ORDER_COMPLETED)
        elif decline_reason == DeclinedTradeReason.ORDER_CANCELLED and other_order_id in self.matches:
            # Let the matchmakers know that the order is cancelled
            for match_payload in self.matches[other_order_id]:
                self.community.send_decline_match_message(self.order,
                                                          other_order_id,
                                                          match_payload.matchmaker_trader_id,
                                                          DeclineMatchReason.OTHER_ORDER_CANCELLED)
        elif decline_reason == DeclinedTradeReason.ADDRESS_LOOKUP_FAIL and other_order_id in self.matches:
            # Let the matchmakers know that the address resolution failed
            for match_payload in self.matches[other_order_id]:
                self.community.send_decline_match_message(self.order,
                                                          other_order_id,
                                                          match_payload.matchmaker_trader_id,
                                                          DeclineMatchReason.OTHER)
        elif decline_reason == DeclinedTradeReason.ORDER_RESERVED and self.outstanding_request:
            # Add it to the queue again
            self._logger.debug("Adding entry (%d, %s, %s) to matching queue again", *self.outstanding_request)
            self.queue.insert(self.outstanding_request[0] + 1, self.outstanding_request[1], self.outstanding_request[2])
        elif decline_reason == DeclinedTradeReason.NO_AVAILABLE_QUANTITY and self.outstanding_request:
            # Re-add the item to the queue, with the same priority
            self.queue.insert(self.outstanding_request[0], self.outstanding_request[1], self.outstanding_request[2])

        self.outstanding_request = None

        if self.order.status == "open":
            self.process_match()

    def remove_order(self, order_id):
        """
        Remove all entries from the queue that match the passed order id.
        """
        to_remove = []
        for item in self.queue.queue:
            if item[2] == order_id:
                to_remove.append(item)

        for item in to_remove:
            self.queue.queue.remove(item)

    def did_trade(self, trade, trade_id):
        """
        We just performed a trade with a counterparty.
        """
        self.outstanding_request = None
        other_order_id = trade.order_id
        if other_order_id not in self.matches:
            return

        self.received_responses_ids.add(other_order_id)

        for match_payload in self.matches[other_order_id]:
            self._logger.info("Sending transaction completed (order %s) to matchmaker %s", trade.order_id, match_payload.matchmaker_trader_id.as_hex())

            auth = BinMemberAuthenticationPayload(self.community.my_peer.public_key.key_to_bin()).to_pack_list()
            payload_content = trade.to_network() + (trade_id,)
            payload = CompletedTradePayload(*payload_content).to_pack_list()
            packet = self.community._ez_pack(self.community._prefix, MSG_MATCHED_TRADE_COMPLETE, [auth, payload])
            self.community.endpoint.send(self.community.lookup_ip(match_payload.matchmaker_trader_id), packet)

        if self.order.status == "open":
            self.process_match()


class ProposedTradeRequestCache(NumberCache):
    """
    This cache keeps track of outstanding proposed trade messages.
    """
    def __init__(self, community, proposed_trade):
        super(ProposedTradeRequestCache, self).__init__(community.request_cache, u"proposed-trade",
                                                        proposed_trade.proposal_id)
        self.community = community
        self.proposed_trade = proposed_trade

    @property
    def timeout_delay(self):
        return 2.0

    def on_timeout(self):
        # Just remove the reserved quantity from the order
        self._logger.info("Timeout of proposed trade with id %s", self.proposed_trade.proposal_id)
        order = self.community.order_manager.order_repository.find_by_id(self.proposed_trade.order_id)
        order.release_quantity_for_tick(self.proposed_trade.recipient_order_id, 1)
        self.community.order_manager.order_repository.update(order)

        # Let the match cache know about the timeout
        cache = self.community.request_cache.get(u"match", int(order.order_id.order_number))
        if cache:
            cache.received_decline_trade(self.proposed_trade.recipient_order_id, DeclinedTradeReason.OTHER)


class PingRequestCache(RandomNumberCache):
    """
    This request cache keeps track of outstanding ping messages to matchmakers.
    """
    TIMEOUT_DELAY = 5.0

    def __init__(self, community, request_deferred):
        super(PingRequestCache, self).__init__(community.request_cache, u"ping")
        self.request_deferred = request_deferred

    @property
    def timeout_delay(self):
        return PingRequestCache.TIMEOUT_DELAY

    def on_timeout(self):
        self.request_deferred.callback(False)


class MarketCommunity(Community):
    """
    Community for order matching and negotiation.
    """
    master_peer = Peer(unhexlify("4c69624e61434c504b3ab5bb7dc5a3a61de442585122b24c9f752469a212dc6d8ffa3d42bbf9c2f8d10"
                                 "ba569b270f615ef78aeff0547f38745d22af268037ad64935ee7c054b7921b23b"))
    DB_NAME = 'market'

    def __init__(self, *args, **kwargs):
        self.trading_engine = kwargs.pop('trading_engine')
        self.trading_engine.matching_community = self
        self.is_matchmaker = kwargs.pop('is_matchmaker', True)
        self.tribler_session = kwargs.pop('tribler_session', None)
        self.dht = kwargs.pop('dht', None)
        self.use_database = kwargs.pop('use_database', True)
        self.settings = MatchingSettings()
        db_working_dir = kwargs.pop('working_directory', '')

        Community.__init__(self, *args, **kwargs)

        self._use_main_thread = True  # Market community is unable to deal with thread pool message processing yet
        self.mid = self.my_peer.mid
        self.mid_register = {}
        self.order_book = None
        self.market_database = MarketDB(db_working_dir, self.DB_NAME)
        self.matching_engine = None
        self.use_local_address = False
        self.matching_enabled = True
        self.matchmakers = set()
        self.request_cache = RequestCache()
        self.cancelled_orders = set()  # Keep track of cancelled orders so we don't add them again to the orderbook.
        self.sync_lc = None
        self.sent_matches = set()
        self.new_orders_relayed = set()
        self.cancel_orders_relayed = set()
        self.complete_orders_relayed = set()

        self.num_received_cancel_orders = 0
        self.num_received_orders = 0
        self.num_received_match = 0
        self.num_received_match_decline = 0
        self.num_received_proposed_trade = 0
        self.num_received_declined_trade = 0
        self.num_received_counter_trade = 0
        self.num_received_complete_trade = 0

        self.fixed_broadcast_set = []  # Used if we need to broadcast to a fixed set of other peers

        if self.use_database:
            order_repository = DatabaseOrderRepository(self.mid, self.market_database)
        else:
            order_repository = MemoryOrderRepository(self.mid)

        self.order_manager = OrderManager(order_repository)

        if self.is_matchmaker:
            self.enable_matchmaker()
            self.set_sync_policy(self.settings.sync_policy)

        # Register messages
        self.decode_map.update({
            chr(MSG_CANCEL_ORDER): self.received_cancel_order,
            chr(MSG_ORDER): self.received_order,
            chr(MSG_MATCH): self.received_match,
            chr(MSG_MATCH_DECLINE): self.received_decline_match,
            chr(MSG_PROPOSED_TRADE): self.received_proposed_trade,
            chr(MSG_DECLINED_TRADE): self.received_decline_trade,
            chr(MSG_COUNTER_TRADE): self.received_counter_trade,
            chr(MSG_START_TRADE): self.received_start_trade,
            chr(MSG_BOOK_SYNC): self.received_orderbook_sync,
            chr(MSG_PING): self.received_ping,
            chr(MSG_PONG): self.received_pong,
            chr(MSG_MATCHED_TRADE_COMPLETE): self.received_matched_tx_complete,
            chr(MSG_COMPLETE_TRADE): self.received_trade_complete_broadcast
        })

        self.logger.info("Market community initialized with mid %s", hexlify(self.mid))

    def set_sync_policy(self, policy):
        """
        Set a specific sync policy.
        """
        self.settings.sync_policy = policy
        if policy == SYNC_POLICY_NONE:
            if self.sync_lc:
                self.sync_lc.stop()
                self.sync_lc = None
        elif policy == SYNC_POLICY_NEIGHBOURS:
            if not self.sync_lc:
                self.sync_lc = LoopingCall(self.sync_orderbook)

                # Do not start at the same time
                reactor.callLater(random.uniform(0, 10), self.sync_lc.start, self.settings.sync_interval)

    def sync_orderbook(self):
        """
        Sync the orderbook with another peer, according to a policy.
        """
        if not self.is_matchmaker:
            return

        sync_peer = None
        if self.fixed_broadcast_set:
            sync_peer = random.choice(list(self.fixed_broadcast_set))
        elif self.matchmakers:
            sync_peer = random.choice(list(self.matchmakers))

        if sync_peer and sync_peer.address not in self.network.blacklist:
            self.send_orderbook_sync(sync_peer)

    def get_address_for_trader(self, trader_id):
        """
        Fetch the address for a trader.
        If not available in the local storage, perform a DHT request to fetch the address of the peer with a
        specified trader ID.
        Return a Deferred that fires either with the address or None if the peer could not be found in the DHT.
        """
        if bytes(trader_id) == self.mid:
            return succeed(self.get_ipv8_address())
        address = self.lookup_ip(trader_id)
        if address:
            return succeed(address)

        self.logger.info("Address for trader %s not found locally, doing DHT request", trader_id.as_hex())
        deferred = Deferred()

        def on_peers(peers):
            if peers:
                self.update_ip(trader_id, peers[0].address)
                deferred.callback(peers[0].address)

        def on_dht_error(failure):
            self._logger.warning("Unable to get address for trader %s", trader_id.as_hex())
            deferred.errback(failure)

        if not self.dht:
            return fail(RuntimeError("DHT not available"))

        self.dht.connect_peer(bytes(trader_id)).addCallbacks(on_peers, on_dht_error)

        return deferred

    def enable_matchmaker(self):
        """
        Enable this node to be a matchmaker
        """
        if self.use_database:
            self.order_book = DatabaseOrderBook(self.market_database)
            self.order_book.restore_from_database()
        else:
            self.order_book = OrderBook()

        self.matching_engine = MatchingEngine(TaxiStrategy(self.order_book))
        self.is_matchmaker = True

    def disable_matchmaker(self):
        """
        Disable the matchmaker status of this node
        """
        self.order_book = None
        self.matching_engine = None
        self.is_matchmaker = False

    def create_introduction_request(self, socket_address, extra_bytes=b''):
        extra_payload = InfoPayload(TraderId(self.mid), Timestamp.now(), self.is_matchmaker)
        extra_bytes = self.serializer.pack_multiple(extra_payload.to_pack_list())[0]
        return super(MarketCommunity, self).create_introduction_request(socket_address, extra_bytes)

    def create_introduction_response(self, lan_socket_address, socket_address, identifier,
                                     introduction=None, extra_bytes=b''):
        extra_payload = InfoPayload(TraderId(self.mid), Timestamp.now(), self.is_matchmaker)
        extra_bytes = self.serializer.pack_multiple(extra_payload.to_pack_list())[0]
        return super(MarketCommunity, self).create_introduction_response(lan_socket_address, socket_address,
                                                                         identifier, introduction, extra_bytes)

    def parse_extra_bytes(self, extra_bytes, peer):
        if not extra_bytes:
            return False

        payload = self.serializer.unpack_to_serializables([InfoPayload], extra_bytes)[0]
        self.update_ip(payload.trader_id, peer.address)

        if payload.is_matchmaker:
            self.add_matchmaker(peer)

    def introduction_request_callback(self, peer, dist, payload):
        self.parse_extra_bytes(payload.extra_bytes, peer)

    def introduction_response_callback(self, peer, dist, payload):
        self.parse_extra_bytes(payload.extra_bytes, peer)

    def send_orderbook_sync(self, peer):
        """
        Send an orderbook sync message to a specific peer.
        """
        self.logger.debug("Sending orderbook sync to peer %s", peer)
        bloomfilter = self.get_orders_bloomfilter()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = OrderbookSyncPayload(TraderId(self.mid), Timestamp.now(), bloomfilter).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_BOOK_SYNC, [auth, payload])
        self.endpoint.send(peer.address, packet)

    def get_orders_bloomfilter(self):
        order_ids = [bytes(order_id) for order_id in self.order_book.get_order_ids()]
        orders_bloom_filter = BloomFilter(0.005, max(len(order_ids), 1), prefix=b' ')
        if order_ids:
            orders_bloom_filter.add_keys(order_ids)
        return orders_bloom_filter

    @inlineCallbacks
    def unload(self):
        self.request_cache.clear()

        # Save the ticks to the database
        if self.is_matchmaker:
            if self.use_database:
                self.order_book.save_to_database()
            if self.sync_lc:
                self.sync_lc.stop()
                self.sync_lc = None
            self.order_book.shutdown_task_manager()
        self.market_database.close()
        yield super(MarketCommunity, self).unload()

    def get_ipv8_address(self):
        """
        Returns the address of the IPV8 instance. This method is here to make the experiments on the DAS5 succeed;
        direct messaging is not possible there with a wan address so we are using the local address instead.
        """
        return self.my_estimated_lan if self.use_local_address else self.my_estimated_wan

    def match_order_ids(self, order_ids):
        """
        Attempt to match the ticks with the provided order ids
        :param order_ids: The order ids to match
        """
        for order_id in order_ids:
            if self.order_book.tick_exists(order_id):
                self.match(self.order_book.get_tick(order_id))

    def match(self, tick):
        """
        Try to find a match for a specific tick and send proposed trade messages if there is a match
        :param tick: The tick to find matches for
        """
        if not self.matching_enabled:
            return 0

        order_tick_entry = self.order_book.get_tick(tick.order_id)
        if 1 - tick.traded <= 0:
            self.logger.debug("Tick %s does not have any quantity to match!", tick.order_id)
            return 0

        matched_ticks = self.matching_engine.match(order_tick_entry)
        self.send_match_messages(matched_ticks, tick.order_id)
        return len(matched_ticks)

    def lookup_ip(self, trader_id):
        """
        Lookup the ip for the public key to send a message to a specific node

        :param trader_id: The public key of the node to send to
        :type trader_id: TraderId
        :return: The ip and port tuple: (<ip>, <port>)
        :rtype: tuple
        """
        return self.mid_register.get(trader_id)

    def update_ip(self, trader_id, ip):
        """
        Update the public key to ip mapping

        :param trader_id: The public key of the node
        :param ip: The ip and port of the node
        :type trader_id: TraderId
        :type ip: tuple
        """
        self.logger.debug("Updating ip of trader %s to (%s, %s)", trader_id.as_hex(), ip[0], ip[1])
        self.mid_register[trader_id] = ip

    def on_ask_timeout(self, ask):
        if not ask:
            return

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_UPDATE, None, ask.to_dictionary())

    def on_bid_timeout(self, bid):
        if not bid:
            return

        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_BID_TIMEOUT, NTFY_UPDATE, None, bid.to_dictionary())

    @lazy_wrapper(OrderbookSyncPayload)
    def received_orderbook_sync(self, peer, payload):
        if not self.is_matchmaker:
            return

        ticks = []
        for order_id in self.order_book.get_order_ids():
            if bytes(order_id) not in payload.bloomfilter:
                is_ask = self.order_book.ask_exists(order_id)
                entry = self.order_book.get_ask(order_id) if is_ask else self.order_book.get_bid(order_id)
                ticks.append(entry)

        for entry in random.sample(ticks, min(len(ticks), self.settings.num_order_sync)):
            self.send_order(entry.tick, peer.address)

    def ping_peer(self, peer):
        """
        Ping a specific peer. Return a deferred that fires with a boolean value whether the peer responded within time.
        """
        deferred = Deferred()
        cache = PingRequestCache(self, deferred)
        self.request_cache.add(cache)
        self.send_ping(peer, cache.number)
        return deferred

    def send_ping(self, peer, identifier):
        """
        Send a ping message with an identifier to a specific peer.
        """
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = PingPongPayload(TraderId(self.mid), Timestamp.now(), identifier).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_PING, [auth, payload])
        self.endpoint.send(peer.address, packet)

    @lazy_wrapper(PingPongPayload)
    def received_ping(self, peer, payload):
        self.send_pong(peer, payload.identifier)

    def send_pong(self, peer, identifier):
        """
        Send a pong message with an identifier to a specific peer.
        """
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = PingPongPayload(TraderId(self.mid), Timestamp.now(), identifier).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_PONG, [auth, payload])
        self.endpoint.send(peer.address, packet)

    @lazy_wrapper(PingPongPayload)
    def received_pong(self, _, payload):
        if not self.request_cache.has(u"ping", payload.identifier):
            self.logger.warning("ping cache with id %s not found", payload.identifier)
            return

        cache = self.request_cache.pop(u"ping", payload.identifier)
        reactor.callFromThread(cache.request_deferred.callback, True)

    def broadcast_order(self, order):
        payload_args = order.to_network()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = OrderPayload(*payload_args).to_pack_list()

        send_peers = []
        packet = self._ez_pack(self._prefix, MSG_ORDER, [auth, payload])
        if self.settings.dissemination_policy == DISSEMINATION_POLICY_NEIGHBOURS:
            if self.fixed_broadcast_set:
                send_peers = self.fixed_broadcast_set
            else:
                send_peers = random.sample(self.network.verified_peers,
                                           min(len(self.network.verified_peers), self.settings.fanout))
        elif self.settings.dissemination_policy == DISSEMINATION_POLICY_RANDOM:
            send_peers = random.sample(list(self.matchmakers), min(self.settings.fanout, len(self.matchmakers)))

        order.broadcast_peers = send_peers

        for peer in send_peers:
            self.endpoint.send(peer.address, packet)

    def broadcast_trade_completed(self, trade, trade_id):
        self.logger.debug("Broadcasting trade complete (%s and %s)", trade.order_id, trade.recipient_order_id)

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        global_time = self.claim_global_time()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()
        payload_content = trade.to_network() + (trade_id,)
        payload = CompletedTradePayload(*payload_content).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_COMPLETE_TRADE, [auth, dist, payload])
        send_peers = []

        order = self.order_manager.order_repository.find_by_id(trade.order_id) or self.order_manager.order_repository.find_by_id(trade.recipient_order_id)
        if order.broadcast_peers:
            send_peers = order.broadcast_peers
        elif self.settings.dissemination_policy == DISSEMINATION_POLICY_NEIGHBOURS:
            if self.fixed_broadcast_set:
                send_peers = self.fixed_broadcast_set
            else:
                send_peers = random.sample(self.network.verified_peers,
                                           min(len(self.network.verified_peers), self.settings.fanout))
        elif self.settings.dissemination_policy == DISSEMINATION_POLICY_RANDOM:
            send_peers = random.sample(list(self.matchmakers),
                                       min(self.settings.fanout, len(self.matchmakers)))

        # Also process it locally if you are a matchmaker
        if self.is_matchmaker:
            # Update ticks in order book, release the reserved quantity and find a new match
            quantity = 1
            completed = self.order_book.update_ticks(trade.order_id, trade.recipient_order_id, quantity, trade_id)
            for completed_order_id in completed:
                self.on_order_completed(completed_order_id)
            self.match_order_ids([trade.order_id, trade.recipient_order_id])

        for peer in send_peers:
            self.endpoint.send(peer.address, packet)

    def send_order(self, order, address):
        payload_args = order.to_network()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = OrderPayload(*payload_args).to_pack_list()
        packet = self._ez_pack(self._prefix, MSG_ORDER, [auth, payload])
        self.endpoint.send(address, packet)

    def verify_offer_creation(self, latitude, longitude, timeout):
        """
        Verify whether we are creating a valid order.
        This method raises a RuntimeError if the created order is not valid.
        """
        if timeout < 0:
            raise RuntimeError("The timeout for this order should be positive")

        if timeout > MAX_ORDER_TIMEOUT:
            raise RuntimeError("The timeout for this order should be less than a day")

    def create_ride_offer(self, latitude, longitude, timeout):
        """
        Create a taxi ride offer (sell order)

        :param assets: The assets to exchange
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type assets: AssetPair
        :type timeout: int
        :return: The created order
        :rtype: Order
        """
        self.verify_offer_creation(latitude, longitude, timeout)

        # Create the order
        order = self.order_manager.create_ride_offer(latitude, longitude, Timeout(timeout))
        self.order_manager.order_repository.update(order)

        if self.is_matchmaker:
            tick = Tick.from_order(order)
            self.order_book.insert_ask(tick).addCallback(self.on_ask_timeout)
            self.match(tick)

        # Broadcast the order
        self.broadcast_order(order)

        self.logger.info("Ask created with lat %s long %s", latitude, longitude)
        return order

    def create_ride_request(self, latitude, longitude, timeout):
        """
        Create a taxi ride request (sell order)

        :param assets: The assets to exchange
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type assets: AssetPair
        :type timeout: int
        :return: The created order
        :rtype: Order
        """
        self.verify_offer_creation(latitude, longitude, timeout)

        # Create the order
        order = self.order_manager.create_ride_request(latitude, longitude, Timeout(timeout))
        self.order_manager.order_repository.update(order)

        if self.is_matchmaker:
            tick = Tick.from_order(order)
            self.order_book.insert_bid(tick).addCallback(self.on_bid_timeout)
            self.match(tick)

        # Broadcast the order
        self.broadcast_order(order)

        return order

    def add_matchmaker(self, matchmaker):
        """
        Add a matchmaker to the set of known matchmakers. Also check whether there are pending deferreds.
        """
        if matchmaker.public_key.key_to_bin() == self.my_peer.public_key.key_to_bin():
            return

        self.matchmakers.add(matchmaker)

    def on_tick(self, tick):
        """
        Process an incoming tick.
        :param tick: the received tick to process
        """
        self.logger.debug("%s received from trader %s, lat: %f, long: %f", type(tick),
                          tick.order_id.trader_id.as_hex(), tick.latitude, tick.longitude)

        if self.is_matchmaker:
            insert_method = self.order_book.insert_ask if isinstance(tick, Ask) else self.order_book.insert_bid
            timeout_method = self.on_ask_timeout if isinstance(tick, Ask) else self.on_bid_timeout

            if not self.order_book.tick_exists(tick.order_id) and tick.order_id not in self.cancelled_orders:
                self.logger.info("Inserting tick %s from %s", tick, tick.order_id)
                insert_method(tick).addCallback(timeout_method)

                if self.order_book.tick_exists(tick.order_id):
                    if self.tribler_session:
                        subject = NTFY_MARKET_ON_ASK if isinstance(tick, Ask) else NTFY_MARKET_ON_BID
                        self.tribler_session.notifier.notify(subject, NTFY_UPDATE, None, tick.to_dictionary())

                    # Check for new matches against the orders of this node
                    for order in self.order_manager.order_repository.find_all():
                        order_tick_entry = self.order_book.get_tick(order.order_id)
                        if not order.is_valid() or not order_tick_entry:
                            continue

                        self.match(order_tick_entry.tick)

                    # Only after we have matched our own orders, do the matching with other ticks if necessary
                    self.match(tick)

    def send_match_messages(self, matching_ticks, order_id):
        return [self.send_match_message(tick_entry.tick, order_id) for tick_entry in matching_ticks]

    def send_match_message(self, tick, recipient_order_id):
        """
        Send a match message to a specific node
        :param tick: The matched tick
        :param recipient_order_id: The order id of the recipient, matching the tick
        """
        if self.settings.matchmaker_malicious_rate > 0 and random.random() <= self.settings.matchmaker_malicious_rate:
            return
        
        if (recipient_order_id, tick.order_id) in self.sent_matches:
            return
        self.sent_matches.add((recipient_order_id, tick.order_id))

        payload_tup = tick.to_network()

        # Add recipient order number, matched quantity, trader ID of the matched person, our own trader ID and match ID
        my_id = TraderId(self.mid)
        payload_tup += (recipient_order_id.order_number, tick.order_id.trader_id, my_id)

        def on_peer_address(address):
            if not address:
                return

            self.logger.info("Sending match message with order id %s and tick order id %s to trader %s",
                             str(recipient_order_id), str(tick.order_id), recipient_order_id.trader_id.as_hex())

            auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
            payload = MatchPayload(*payload_tup).to_pack_list()

            packet = self._ez_pack(self._prefix, MSG_MATCH, [auth, payload])
            self.endpoint.send(address, packet)

        def get_address():
            err_handler = lambda _: on_peer_address(None)
            self.get_address_for_trader(recipient_order_id.trader_id).addCallbacks(on_peer_address, err_handler)

        if self.settings.match_send_interval == 0:
            get_address()
        else:
            reactor.callLater(random.uniform(0, self.settings.match_send_interval), get_address)

    def received_cancel_order(self, source_address, data):
        """
        We received an order cancellation from the network.
        :param source_address: The peer we received this payload from.
        :param payload: The CancelOrderPayload we received.
        """
        if self.settings.send_fail_rate > 0 and random.random() <= self.settings.send_fail_rate:
            # Ignore the message
            return

        self.num_received_cancel_orders += 1
        auth, dist, payload = self._ez_unpack_auth(CancelOrderPayload, data)

        order_id = OrderId(payload.trader_id, payload.order_number)
        if self.is_matchmaker and self.order_book.tick_exists(order_id):
            self.order_book.remove_tick(order_id)
            self.cancelled_orders.add(order_id)

    @lazy_wrapper(OrderPayload)
    def received_order(self, peer, payload):
        if self.settings.send_fail_rate > 0 and random.random() <= self.settings.send_fail_rate:
            # Ignore the message
            return

        self.num_received_orders += 1
        tick = Ask.from_network(payload) if payload.is_ask else Bid.from_network(payload)
        self.logger.debug("Received order from %s:%d, order %s", peer.address[0], peer.address[1], peer)
        self.on_tick(tick)

    def received_trade_complete_broadcast(self, source_address, data):
        """
        We received a trade completion from the network.
        :param source_address: The peer we received this payload from.
        :param data: The binary data we received.
        """
        self.num_received_complete_trade += 1
        auth, dist, payload = self._ez_unpack_auth(CompletedTradePayload, data)

        if self.is_matchmaker:
            # Update ticks in order book, release the reserved quantity and find a new match
            quantity = 1
            order_id1 = OrderId(TraderId(payload.trader_id), payload.order_number)
            order_id2 = payload.recipient_order_id
            completed = self.order_book.update_ticks(order_id1, order_id2, quantity, payload.trade_id)
            for completed_order_id in completed:
                self.on_order_completed(completed_order_id)
            self.match_order_ids([order_id1, order_id2])

    @lazy_wrapper(MatchPayload)
    def received_match(self, peer, payload):
        """
        We received a match message from a matchmaker.
        """
        if self.settings.send_fail_rate > 0 and random.random() <= self.settings.send_fail_rate:
            # Ignore the message
            return

        self.num_received_match += 1
        self.logger.info("We received a match message from %s for order %s.%s (matched against %s.%s, lat: %f, long: %f)",
                         payload.matchmaker_trader_id.as_hex(), TraderId(self.mid).as_hex(), payload.recipient_order_number, payload.trader_id.as_hex(), payload.order_number, payload.latitude, payload.longitude)

        # We got a match, check whether we can respond to this match
        self.update_ip(payload.matchmaker_trader_id, peer.address)
        self.add_matchmaker(peer)

        self.process_match_payload(payload)

    def process_match_payload(self, payload):
        """
        Process a match payload.
        """
        order_id = OrderId(TraderId(self.mid), payload.recipient_order_number)
        order = self.order_manager.order_repository.find_by_id(order_id)
        if not order:
            self.logger.warning("Cannot find order %s in order repository!", order_id)
            return

        if order.status != "open":
            # Send a declined match back so the matchmaker removes the order from their book
            decline_reason = DeclineMatchReason.ORDER_COMPLETED if order.status != "open" \
                else DeclineMatchReason.OTHER
            other_order_id = OrderId(payload.match_trader_id, payload.recipient_order_number)
            self.send_decline_match_message(order, other_order_id, payload.matchmaker_trader_id, decline_reason)
            return

        cache = self.request_cache.get(u"match", int(payload.recipient_order_number))
        if not cache:
            cache = MatchCache(self, order)
            self.request_cache.add(cache)

        # Add the match to the cache and process it
        cache.add_match(payload)

    def accept_match_and_propose(self, order, other_order_id):
        """
        Accept an incoming match payload and propose a trade to the counterparty
        """
        propose_quantity = order.available_quantity
        if propose_quantity == 0:
            self.logger.info("No available quantity for order %s - not sending outgoing proposal", order.order_id)

            # Notify the match cache
            cache = self.request_cache.get(u"match", int(order.order_id.order_number))
            if cache:
                cache.received_decline_trade(other_order_id, DeclinedTradeReason.NO_AVAILABLE_QUANTITY)
            return

        propose_trade = Trade.propose(
            TraderId(self.mid),
            order.order_id,
            other_order_id,
            order.latitude,
            order.longitude,
            Timestamp.now()
        )

        def on_peer_address(address):
            if address:
                self.send_proposed_trade(propose_trade, address)
            else:
                order.release_quantity_for_tick(other_order_id, propose_quantity)

                # Notify the match cache
                cache = self.request_cache.get(u"match", int(order.order_id.order_number))
                if cache:
                    cache.received_decline_trade(other_order_id, DeclinedTradeReason.ADDRESS_LOOKUP_FAIL)

        # Reserve the quantity
        order.reserve_quantity_for_tick(other_order_id, propose_quantity)
        self.order_manager.order_repository.update(order)

        # Fetch the address of the target peer (we are not guaranteed to know it at this point since we might have
        # received the order indirectly)
        def get_address():
            err_handler = lambda _: on_peer_address(None)
            self.get_address_for_trader(propose_trade.recipient_order_id.trader_id) \
                .addCallbacks(on_peer_address, err_handler)

        reactor.callFromThread(get_address)

    def send_decline_match_message(self, order, other_order_id, matchmaker_trader_id, decline_reason):
        address = self.lookup_ip(matchmaker_trader_id)

        self.logger.info("Sending decline match message for order %s to trader %s (ip: %s, port: %s)",
                         order.order_id, matchmaker_trader_id.as_hex(), *address)

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = (TraderId(self.mid), Timestamp.now(), order.order_id.order_number, other_order_id, decline_reason)
        payload = DeclineMatchPayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_MATCH_DECLINE, [auth, payload])
        self.endpoint.send(address, packet)

    @lazy_wrapper(DeclineMatchPayload)
    def received_decline_match(self, _, payload):
        self.num_received_match_decline += 1
        order_id = OrderId(payload.trader_id, payload.order_number)
        matched_order_id = payload.other_order_id
        self.logger.info("Received decline-match message for tick %s matched with %s, reason %s", order_id, matched_order_id, payload.decline_reason)

        # It could be that one or both matched tick(s) have already been removed from the order book by a
        # tx_done block. We have to account for that and act accordingly.
        tick_entry = self.order_book.get_tick(order_id)
        matched_tick_entry = self.order_book.get_tick(matched_order_id)

        if tick_entry and matched_tick_entry:
            tick_entry.block_for_matching(matched_tick_entry.order_id)
            matched_tick_entry.block_for_matching(tick_entry.order_id)

        if matched_tick_entry and (payload.decline_reason == DeclineMatchReason.OTHER_ORDER_COMPLETED or payload.decline_reason == DeclineMatchReason.OTHER_ORDER_CANCELLED):
            self.order_book.remove_tick(matched_tick_entry.order_id)
            self.order_book.completed_orders.add(matched_tick_entry.order_id)
            self.on_order_completed(matched_tick_entry.order_id)

        if payload.decline_reason == DeclineMatchReason.ORDER_COMPLETED and tick_entry:
            self.order_book.remove_tick(tick_entry.order_id)
            self.order_book.completed_orders.add(tick_entry.order_id)
            self.on_order_completed(tick_entry.order_id)
        elif payload.decline_reason == DeclineMatchReason.OTHER and tick_entry:
            # Search for a new match
            self.match(tick_entry.tick)

    def cancel_order(self, order_id, broadcast=True):
        order = self.order_manager.order_repository.find_by_id(order_id)
        if order and order.status == "open":
            self.order_manager.cancel_order(order_id)

            if self.is_matchmaker:
                self.order_book.remove_tick(order_id)

            if broadcast:
                auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
                global_time = self.claim_global_time()
                dist = GlobalTimeDistributionPayload(global_time).to_pack_list()
                payload = CancelOrderPayload(order.order_id.trader_id, order.timestamp, order.order_id.order_number).to_pack_list()
                packet = self._ez_pack(self._prefix, MSG_CANCEL_ORDER, [auth, dist, payload])

                send_peers = []
                if order.broadcast_peers:
                    send_peers = order.broadcast_peers
                elif self.settings.dissemination_policy == DISSEMINATION_POLICY_NEIGHBOURS:
                    if self.fixed_broadcast_set:
                        send_peers = self.fixed_broadcast_set
                    else:
                        send_peers = random.sample(self.network.verified_peers,
                                                   min(len(self.network.verified_peers), self.settings.fanout))
                elif self.settings.dissemination_policy == DISSEMINATION_POLICY_RANDOM:
                    send_peers = random.sample(list(self.matchmakers),
                                               min(self.settings.fanout, len(self.matchmakers)))

                for peer in send_peers:
                    self.endpoint.send(peer.address, packet)

    def on_order_completed(self, order_id):
        """
        An order has been completed. Update the match caches accordingly
        """
        for cache in self.get_match_caches():
            cache.remove_order(order_id)

    # Proposed trade
    def send_proposed_trade(self, proposed_trade, address):
        payload = proposed_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, proposed_trade))

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = TradePayload(*payload).to_pack_list()

        self.logger.debug("Sending proposed trade with own order id %s and other order id %s to trader "
                          "%s, lat: %f, long: %f", str(proposed_trade.order_id),
                          str(proposed_trade.recipient_order_id), proposed_trade.recipient_order_id.trader_id.as_hex(),
                          proposed_trade.latitude, proposed_trade.longitude)

        packet = self._ez_pack(self._prefix, MSG_PROPOSED_TRADE, [auth, payload])
        self.endpoint.send(address, packet)

    def check_trade_payload_validity(self, payload):
        if bytes(payload.recipient_order_id.trader_id) != self.mid:
            return False, "this payload is not meant for this node"

        if not self.order_manager.order_repository.find_by_id(payload.recipient_order_id):
            return False, "order does not exist"

        return True, ''

    def get_outstanding_proposals(self, order_id, partner_order_id):
        return [(proposal_id, cache) for proposal_id, cache in self.request_cache._identifiers.items()
                if isinstance(cache, ProposedTradeRequestCache)
                and cache.proposed_trade.order_id == order_id
                and cache.proposed_trade.recipient_order_id == partner_order_id]

    def get_match_caches(self):
        """
        Return all match caches.
        """
        return [cache for cache in self.request_cache._identifiers.values() if isinstance(cache, MatchCache)]

    @lazy_wrapper(TradePayload)
    def received_proposed_trade(self, peer, payload):
        self.num_received_proposed_trade += 1
        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of proposed trade payload failed: %s", validation[1])
            return

        proposed_trade = ProposedTrade.from_network(payload)

        self.logger.debug("Proposed trade received from trader %s for order %s",
                          proposed_trade.trader_id.as_hex(), str(proposed_trade.recipient_order_id))

        # Update the known IP address of the sender of this proposed trade
        self.update_ip(proposed_trade.trader_id, peer.address)

        order = self.order_manager.order_repository.find_by_id(proposed_trade.recipient_order_id)

        # We can have a race condition where an ask/bid is created simultaneously on two different nodes.
        # In this case, both nodes first send a proposed trade and then receive a proposed trade from the other
        # node. To counter this, we have the following check.
        outstanding_proposals = self.get_outstanding_proposals(order.order_id, proposed_trade.order_id)
        if outstanding_proposals:
            # Discard current outstanding proposed trade and continue
            for proposal_id, _ in outstanding_proposals:
                request = self.request_cache.get(u"proposed-trade", int(proposal_id.split(':')[1]))
                if order.is_ask():
                    self.logger.info("Discarding current outstanding proposals for order %s", proposed_trade.order_id)
                    self.request_cache.pop(u"proposed-trade", int(proposal_id.split(':')[1]))
                    request.on_timeout()

        should_decline = True
        decline_reason = 0
        if not order.is_valid:
            decline_reason = DeclinedTradeReason.ORDER_INVALID
        elif order.status == "completed":
            decline_reason = DeclinedTradeReason.ORDER_COMPLETED
        elif order.status == "expired":
            decline_reason = DeclinedTradeReason.ORDER_EXPIRED
        elif order.status == "cancelled":
            decline_reason = DeclinedTradeReason.ORDER_CANCELLED
        elif order.available_quantity == 0:
            decline_reason = DeclinedTradeReason.ORDER_RESERVED
        else:
            should_decline = False

        if should_decline:
            declined_trade = Trade.decline(TraderId(self.mid), Timestamp.now(), proposed_trade, decline_reason)
            self.logger.debug("Declined trade made for order id: %s and id: %s "
                              "(valid? %s, available quantity of order: %s, reserved: %s, traded: %s), reason: %s",
                              str(declined_trade.order_id), str(declined_trade.recipient_order_id),
                              order.is_valid(), order.available_quantity, order.reserved_quantity,
                              order.traded_quantity, decline_reason)
            self.send_decline_trade(declined_trade)
        else:
            if order.available_quantity >= 1:  # Enough quantity left
                order.reserve_quantity_for_tick(proposed_trade.order_id, 1)
                self.order_manager.order_repository.update(order)
                self.start_trade(proposed_trade, order)
            else:  # Not all quantity can be traded
                counter_quantity = order.available_quantity
                order.reserve_quantity_for_tick(proposed_trade.order_id, counter_quantity)
                self.order_manager.order_repository.update(order)

                new_pair = order.assets.proportional_downscale(counter_quantity)

                counter_trade = Trade.counter(TraderId(self.mid), new_pair, Timestamp.now(), proposed_trade)
                self.logger.debug("Counter trade made with asset pair %s for proposed trade", counter_trade.assets)
                self.send_counter_trade(counter_trade)

    def send_decline_trade(self, declined_trade):
        payload = declined_trade.to_network()

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = DeclineTradePayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_DECLINED_TRADE, [auth, payload])
        self.endpoint.send(self.lookup_ip(declined_trade.recipient_order_id.trader_id), packet)

    @lazy_wrapper(DeclineTradePayload)
    def received_decline_trade(self, _, payload):
        self.num_received_declined_trade += 1
        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of decline trade payload failed: %s", validation[1])
            return

        declined_trade = DeclinedTrade.from_network(payload)

        if not self.request_cache.has(u"proposed-trade", declined_trade.proposal_id):
            self.logger.warning("declined trade cache with id %s not found", declined_trade.proposal_id)
            return

        request = self.request_cache.pop(u"proposed-trade", declined_trade.proposal_id)

        order = self.order_manager.order_repository.find_by_id(declined_trade.recipient_order_id)
        order.release_quantity_for_tick(declined_trade.order_id, 1)
        self.order_manager.order_repository.update(order)

        # Just remove the tick with the order id of the other party and try to find a new match
        self.logger.debug("Received decline trade (proposal id: %d, reason: %d)",
                          declined_trade.proposal_id, declined_trade.decline_reason)

        other_order_id = OrderId(payload.trader_id, payload.order_number)

        # Update the cache which will inform the related matchmakers
        cache = self.request_cache.get(u"match", int(order.order_id.order_number))
        if cache:
            cache.received_decline_trade(other_order_id, payload.decline_reason)

        # We want to remove this order from all the other caches too if the order is completed or cancelled
        if payload.decline_reason == DeclinedTradeReason.ORDER_COMPLETED or payload.decline_reason == DeclinedTradeReason.ORDER_CANCELLED:
            for cache in self.get_match_caches():
                cache.remove_order(other_order_id)

    # Counter trade
    def send_counter_trade(self, counter_trade):
        payload = counter_trade.to_network()

        self.request_cache.add(ProposedTradeRequestCache(self, counter_trade))

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        payload = TradePayload(*payload).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_COUNTER_TRADE, [auth, payload])
        self.endpoint.send(self.lookup_ip(counter_trade.recipient_order_id.trader_id), packet)

    @lazy_wrapper(TradePayload)
    def received_counter_trade(self, _, payload):
        self.num_received_counter_trade += 1
        validation = self.check_trade_payload_validity(payload)
        if not validation[0]:
            self.logger.warning("Validation of counter trade payload failed: %s", validation[1])
            return

        counter_trade = CounterTrade.from_network(payload)

        if not self.request_cache.has(u"proposed-trade", counter_trade.proposal_id):
            self.logger.warning("proposed trade cache with id %s not found", counter_trade.proposal_id)
            return

        request = self.request_cache.pop(u"proposed-trade", counter_trade.proposal_id)

        order = self.order_manager.order_repository.find_by_id(counter_trade.recipient_order_id)
        self.logger.info("Received counter trade for order %s (quantity: %d)", order.order_id, counter_trade.assets.first.amount)

        should_decline = True
        decline_reason = 0
        if not order.is_valid:
            decline_reason = DeclinedTradeReason.ORDER_INVALID
        elif not order.has_acceptable_price(counter_trade.assets):
            self.logger.info("Unacceptable price for order %s - %s vs %s", order.order_id,
                             counter_trade.assets, order.assets)
            decline_reason = DeclinedTradeReason.UNACCEPTABLE_PRICE
        else:
            should_decline = False

        if should_decline:
            declined_trade = Trade.decline(TraderId(self.mid), Timestamp.now(), counter_trade, decline_reason)
            self.logger.debug("Declined trade made for order id: %s and id: %s ",
                              str(declined_trade.order_id), str(declined_trade.recipient_order_id))
            self.send_decline_trade(declined_trade)

            # Release the quantity from the tick
            order.release_quantity_for_tick(declined_trade.recipient_order_id, request.proposed_trade.assets.first.amount)
            self.order_manager.order_repository.update(order)
        else:
            order.release_quantity_for_tick(counter_trade.order_id, 1)
            order.reserve_quantity_for_tick(counter_trade.order_id, 1)
            self.order_manager.order_repository.update(order)

            # Trade!
            self.start_trade(counter_trade, order)

    # Trade
    def start_trade(self, proposed_trade, order):
        self.logger.info("Starting trade for orders %s and %s", proposed_trade.order_id, proposed_trade.recipient_order_id)
        self.trading_engine.trade(proposed_trade, (order.latitude, order.longitude),
                                  (proposed_trade.latitude, proposed_trade.longitude))

        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        start_trade = StartTrade.start(TraderId(self.mid), order.latitude, order.longitude, Timestamp.now(), proposed_trade)
        payload = TradePayload(*start_trade.to_network()).to_pack_list()

        packet = self._ez_pack(self._prefix, MSG_START_TRADE, [auth, payload])
        self.endpoint.send(self.lookup_ip(proposed_trade.order_id.trader_id), packet)

    @lazy_wrapper(TradePayload)
    def received_start_trade(self, peer, payload):
        self._logger.info("Received start trade from trader %s" % payload.trader_id.as_hex())
        if not self.request_cache.has(u"proposed-trade", payload.proposal_id):
            self._logger.warning("Do not have propose trade cache for proposal %s!", payload.proposal_id)
            return

        # The recipient_order_id in the start_transaction message is our own order
        order = self.order_manager.order_repository.find_by_id(payload.recipient_order_id)
        if not order:
            self._logger.warning("Recipient order in start trade payload is not ours!")
            return

        self.request_cache.pop(u"proposed-trade", payload.proposal_id)

        self.trading_engine.trade(StartTrade.from_network(payload), (order.latitude, order.longitude), (payload.latitude, payload.longitude))

    def on_trade_completed(self, trade, trade_id):
        """
        A trade has been completed. Broadcast details of the trade around the network.
        """
        order = self.order_manager.order_repository.find_by_id(trade.recipient_order_id)
        order.add_trade(trade.order_id, 1)

        # Update the cache and inform the matchmakers
        cache = self.request_cache.get(u"match", int(order.order_id.order_number))
        if cache:
            cache.did_trade(trade, trade_id)

        # Let the rest of the network know
        self.broadcast_trade_completed(trade, trade_id)

    @lazy_wrapper(CompletedTradePayload)
    def received_matched_tx_complete(self, peer, payload):
        self.num_received_complete_trade += 1
        self.logger.debug("Received transaction-completed message as a matchmaker")
        if not self.is_matchmaker:
            return

        # Update ticks in order book, release the reserved quantity and find a new match
        quantity = 1
        order_id1 = OrderId(TraderId(payload.trader_id), payload.order_number)
        order_id2 = payload.recipient_order_id
        completed = self.order_book.update_ticks(order_id1, order_id2, quantity, payload.trade_id)
        for completed_order_id in completed:
            self.on_order_completed(completed_order_id)


class MarketTestnetCommunity(MarketCommunity):
    """
    This community defines a testnet for the market.
    """
    master_peer = Peer(unhexlify("4c69624e61434c504b3a6cd2860aa07739ea53c02b6d40a6682e38a4610a76aeacc6c479022502231"
                                 "424b88aac37f4ec1274e3f89fa8d324be08c11c10b63c1b8662be7d602ae0a26457"))
    DB_NAME = 'market_testnet'
