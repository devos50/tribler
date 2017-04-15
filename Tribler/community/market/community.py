import time
from base64 import b64decode

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.simpledefs import NTFY_MARKET_ON_ASK, NTFY_MARKET_ON_BID, NTFY_MARKET_ON_TRANSACTION_COMPLETE, \
    NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID_TIMEOUT
from Tribler.Core.simpledefs import NTFY_UPDATE
from Tribler.community.market.core.payment_id import PaymentId
from Tribler.community.market.core.wallet_address import WalletAddress
from Tribler.community.market.wallet.mc_wallet import MultichainWallet
from Tribler.community.market.wallet.wallet import InsufficientFunds
from Tribler.dispersy.authentication import MemberAuthentication
from Tribler.dispersy.bloomfilter import BloomFilter
from Tribler.dispersy.candidate import Candidate, WalkCandidate
from Tribler.dispersy.community import Community
from Tribler.dispersy.conversion import DefaultConversion
from Tribler.dispersy.destination import CommunityDestination, CandidateDestination
from Tribler.dispersy.distribution import DirectDistribution
from Tribler.dispersy.message import Message, DelayMessageByProof
from Tribler.dispersy.requestcache import IntroductionRequestCache
from Tribler.dispersy.resolution import PublicResolution
from conversion import MarketConversion
from core.matching_engine import MatchingEngine, PriceTimeStrategy
from core.message import TraderId
from core.message_repository import MemoryMessageRepository
from core.order import TickWasNotReserved
from core.order_manager import OrderManager
from core.order_repository import MemoryOrderRepository
from core.orderbook import OrderBook
from core.payment import Payment
from core.price import Price
from core.quantity import Quantity
from core.tick import Ask, Bid, Tick
from core.timeout import Timeout
from core.timestamp import Timestamp
from core.trade import Trade, ProposedTrade, AcceptedTrade, DeclinedTrade, CounterTrade
from core.transaction import StartTransaction, TransactionId, Transaction
from core.transaction_manager import TransactionManager
from core.transaction_repository import MemoryTransactionRepository
from payload import OfferPayload, TradePayload, AcceptedTradePayload, DeclinedTradePayload, StartTransactionPayload, \
    TransactionPayload, WalletInfoPayload, MarketIntroPayload, \
    OfferSyncPayload, PaymentPayload
from ttl import Ttl


class MarketCommunity(Community):
    """Community for selling and buying multichain credits"""

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Tue Mar 22 23:29:40 2016
        # curve: NID_sect571r1
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b8104002703819200040159af0c0925034bba3b4ea26661828e09247236059c773
        # dac29ac9fb84d50fa6bd8acc035127a6f5c11873915f9b9a460e116ecccccfc5db1b5d8ba86bd701886ea45d8dbbb634906989395d36
        # 6888d008f4119ad0e7f45b9dab7fb3d78a0065c5f7a866b78cb8e59b9a7d048cc0d650c5a86bdfdabb434396d23945d1239f88de4935
        # 467424c7cc02b6579e45f63ee
        # pub-sha1 dda25d128ebabe6b588384d05b8ff46153f98c78
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQBWa8MCSUDS7o7TqJmYYKOCSRyNgWc
        # dz2sKayfuE1Q+mvYrMA1EnpvXBGHORX5uaRg4RbszMz8XbG12LqGvXAYhupF2Nu7
        # Y0kGmJOV02aIjQCPQRmtDn9Fudq3+z14oAZcX3qGa3jLjlm5p9BIzA1lDFqGvf2r
        # tDQ5bSOUXRI5+I3kk1RnQkx8wCtleeRfY+4=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b8104002703819200040159af0c0925034bba3b4ea26661828e09247236059" \
                     "c773dac29ac9fb84d50fa6bd8acc035127a6f5c11873915f9b9a460e116ecccccfc5db1b5d8ba86bd701886ea45d8db" \
                     "bb634906989395d366888d008f4119ad0e7f45b9dab7fb3d78a0065c5f7a866b78cb8e59b9a7d048cc0d650c5a86bdf" \
                     "dabb434396d23945d1239f88de4935467424c7cc02b6579e45f63ee".decode("HEX")
        master = dispersy.get_member(public_key=master_key)
        return [master]

    def initialize(self, tribler_session=None, tradechain_community=None, wallets={}):
        super(MarketCommunity, self).initialize()

        self.mid = self.my_member.mid.encode('hex')
        self.mid_register = {}  # TODO: fix memory leak
        self.relayed_asks = []
        self.relayed_bids = []

        order_repository = MemoryOrderRepository(self.mid)
        message_repository = MemoryMessageRepository(self.mid)
        self.order_manager = OrderManager(order_repository)
        self.order_book = OrderBook(message_repository)
        self.matching_engine = MatchingEngine(PriceTimeStrategy(self.order_book))
        self.tribler_session = tribler_session
        self.tradechain_community = tradechain_community
        self.wallets = wallets

        transaction_repository = MemoryTransactionRepository(self.mid)
        self.transaction_manager = TransactionManager(transaction_repository)

        self.history = {}  # List for received messages TODO: fix memory leak
        self.use_local_address = False

        self._logger.info("Market community initialized with mid %s" % self.mid)

    def initiate_meta_messages(self):
        return super(MarketCommunity, self).initiate_meta_messages() + [
            Message(self, u"ask",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    OfferPayload(),
                    self.check_message,
                    self.on_ask),
            Message(self, u"bid",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    OfferPayload(),
                    self.check_message,
                    self.on_bid),
            Message(self, u"offer-sync",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    OfferSyncPayload(),
                    self.check_message,
                    self.on_offer_sync),
            Message(self, u"proposed-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TradePayload(),
                    self.check_message,
                    self.on_proposed_trade),
            Message(self, u"accepted-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CommunityDestination(node_count=10),
                    AcceptedTradePayload(),
                    self.check_message,
                    self.on_accepted_trade),
            Message(self, u"declined-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    DeclinedTradePayload(),
                    self.check_message,
                    self.on_declined_trade),
            Message(self, u"counter-trade",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TradePayload(),
                    self.check_message,
                    self.on_counter_trade),
            Message(self, u"start-transaction",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    StartTransactionPayload(),
                    self.check_message,
                    self.on_start_transaction),
            Message(self, u"wallet-info",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    WalletInfoPayload(),
                    self.check_message,
                    self.on_wallet_info),
            Message(self, u"payment",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    PaymentPayload(),
                    self.check_message,
                    self.on_payment_message),
            Message(self, u"end-transaction",
                    MemberAuthentication(),
                    PublicResolution(),
                    DirectDistribution(),
                    CandidateDestination(),
                    TransactionPayload(),
                    self.check_message,
                    self.on_end_transaction)
        ]

    def _initialize_meta_messages(self):
        super(MarketCommunity, self)._initialize_meta_messages()

        ori = self._meta_messages[u"dispersy-introduction-request"]
        new = Message(self, ori.name, ori.authentication, ori.resolution,
                      ori.distribution, ori.destination, MarketIntroPayload(), ori.check_callback, ori.handle_callback)
        self._meta_messages[u"dispersy-introduction-request"] = new

    def initiate_conversions(self):
        return [DefaultConversion(self), MarketConversion(self)]

    def create_introduction_request(self, destination, allow_sync):
        assert isinstance(destination, WalkCandidate), [type(destination), destination]

        order_ids = map(str, self.order_book.get_order_ids())
        if len(order_ids) == 0:
            orders_bloom_filter = None
        else:
            orders_bloom_filter = BloomFilter(0.005, len(order_ids), prefix=' ')
            orders_bloom_filter.add_keys(order_ids)

        cache = self._request_cache.add(IntroductionRequestCache(self, destination))
        payload = (destination.sock_addr, self._dispersy._lan_address, self._dispersy._wan_address, True,
                   self._dispersy._connection_type, None, cache.number, orders_bloom_filter)

        destination.walk(time.time())
        self.add_candidate(destination)

        meta_request = self.get_meta_message(u"dispersy-introduction-request")
        request = meta_request.impl(authentication=(self.my_member,),
                                    distribution=(self.global_time,),
                                    destination=(destination,),
                                    payload=payload)

        self._logger.debug(u"%s %s sending introduction request to %s", self.cid.encode("HEX"), type(self), destination)

        self._dispersy._forward([request])
        return request

    def on_introduction_request(self, messages):
        super(MarketCommunity, self).on_introduction_request(messages)

        for message in messages:
            orders_bloom_filter = message.payload.orders_bloom_filter
            for order_id in self.order_book.get_order_ids():
                if not orders_bloom_filter or str(order_id) not in orders_bloom_filter:
                    is_ask = self.order_book.ask_exists(order_id)
                    entry = self.order_book.get_ask(order_id) if is_ask else self.order_book.get_bid(order_id)
                    self.send_offer_sync(message.candidate, entry.tick)

    def on_introduction_response(self, messages):
        super(MarketCommunity, self).on_introduction_response(messages)

    def check_message(self, messages):
        for message in messages:
            allowed, _ = self._timeline.check(message)
            if allowed:
                self._logger.debug("Allowing message %s" % message)
                yield message
            else:
                self._logger.debug("Delaying message %s" % message)
                yield DelayMessageByProof(message)

    @inlineCallbacks
    def unload_community(self):
        self.order_book.cancel_all_pending_tasks()
        yield super(MarketCommunity, self).unload_community()

    def get_dispersy_address(self):
        """
        Returns the address of the Dispersy instance. This method is here to make the experiments on the DAS5 succeed;
        direct messaging is not possible there with a wan address so we are using the local address instead.
        """
        return self.dispersy.lan_address if self.use_local_address else self.dispersy.wan_address

    def get_wallet_address(self, wallet_id):
        """
        Returns the address of the wallet with a specific identifier. Raises a ValueError if that wallet is not
        available.
        """
        if wallet_id not in self.wallets or not self.wallets[wallet_id].created:
            raise ValueError("Wallet %s not available" % wallet_id)

        return self.wallets[wallet_id].get_address()

    def get_order_addresses(self, order):
        """
        Return a tuple of incoming and outgoing payment address of an order.
        """
        if order.is_ask():
            return WalletAddress(self.wallets[order.price.wallet_id].get_address()),\
                   WalletAddress(self.wallets[order.total_quantity.wallet_id].get_address())
        else:
            return WalletAddress(self.wallets[order.total_quantity.wallet_id].get_address()), \
                   WalletAddress(self.wallets[order.price.wallet_id].get_address())

    def check_history(self, message):
        """
        Check if the message is already in the history, meaning it has already been received before

        :param message: The message to check for
        :return: True if the message is new to this node, False otherwise
        :rtype: bool
        """
        if message.message_id in self.history:
            return False
        else:
            self.history[message.message_id] = True
            return True

    def lookup_ip(self, trader_id):
        """
        Lookup the ip for the public key to send a message to a specific node

        :param trader_id: The public key of the node to send to
        :type trader_id: TraderId
        :return: The ip and port tuple: (<ip>, <port>)
        :rtype: tuple
        """
        assert isinstance(trader_id, TraderId), type(trader_id)
        return self.mid_register.get(trader_id)

    def update_ip(self, trader_id, ip):
        """
        Update the public key to ip mapping

        :param trader_id: The public key of the node
        :param ip: The ip and port of the node
        :type trader_id: TraderId
        :type ip: tuple
        """
        assert isinstance(trader_id, TraderId), type(trader_id)
        assert isinstance(ip, tuple), type(ip)
        assert isinstance(ip[0], str)
        assert isinstance(ip[1], int)

        self._logger.debug("Updating ip of trader %s to (%s, %s)", trader_id, ip[0], ip[1])
        self.mid_register[trader_id] = ip

    def on_ask_timeout(self, ask):
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_UPDATE, None, ask)

    def on_bid_timeout(self, bid):
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_BID_TIMEOUT, NTFY_UPDATE, None, bid)

    # Ask
    def create_ask(self, price, price_wallet_id, quantity, quantity_wallet_id, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order in btc
        :param price_wallet_id: The type of the price (i.e. eur, btc)
        :param quantity: The quantity of the order
        :param price_wallet_id: The type of the price (i.e. eur, btc)
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type price_wallet_id: str
        :type quantity: float
        :type quantity_wallet_id: str
        :type timeout: float
        :return: The created order
        :rtype: Order
        """
        if price_wallet_id == quantity_wallet_id:
            raise RuntimeError("You cannot trade between the same wallet")

        # TODO(Martijn): balance check?
        if price_wallet_id not in self.wallets or not self.wallets[price_wallet_id].created:
            raise RuntimeError("Please create a %s wallet first" % price_wallet_id)

        if quantity_wallet_id not in self.wallets or not self.wallets[quantity_wallet_id].created:
            raise RuntimeError("Please create a %s wallet first" % quantity_wallet_id)

        # Convert values to value objects
        price = Price(price, price_wallet_id)
        quantity = Quantity(quantity, quantity_wallet_id)
        timeout = Timeout(timeout)

        # Create the order
        order = self.order_manager.create_ask_order(price, quantity, timeout)

        # Search for matches
        proposed_trades = self.matching_engine.match_order(order)
        self.send_proposed_trade_messages(proposed_trades)

        # Create the tick
        tick = Tick.from_order(order, self.order_book.message_repository.next_identity())
        assert isinstance(tick, Ask), type(tick)
        self.order_book.insert_ask(tick).addCallback(self.on_ask_timeout)
        self.send_ask_messages([tick])

        self._logger.debug("Ask created with price %s and quantity %s" % (price, quantity))

        return order

    def send_ask(self, ask):
        """
        Send an ask message

        :param ask: The message to send
        :type ask: Ask
        """
        assert isinstance(ask, Ask), type(ask)

        self._logger.debug("Ask send with id: %s for order with id: %s", str(ask.message_id), str(ask.order_id))

        payload = ask.to_network()

        # Add ttl and the local wan address
        payload += (Ttl.default(),) + self.get_dispersy_address()

        meta = self.get_meta_message(u"ask")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_ask_messages(self, messages):
        for message in messages:
            self.send_ask(message)

    def on_ask(self, messages):
        for message in messages:
            ask = Ask.from_network(message.payload)

            self._logger.debug("Ask received from trader %s (price: %s, quantity: %s)", str(ask.order_id.trader_id),
                               ask.price, ask.quantity)

            # Update the pubkey register with the current address
            self.update_ip(ask.message_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            if not str(ask.order_id) in self.relayed_asks and not self.order_book.tick_exists(ask.order_id):
                self.relayed_asks.append(str(ask.order_id))
                self.order_book.insert_ask(ask).addCallback(self.on_ask_timeout)

                if self.tribler_session:
                    self.tribler_session.notifier.notify(NTFY_MARKET_ON_ASK, NTFY_UPDATE, None, ask)

                # Check for new matches against the orders of this node
                for order in self.order_manager.order_repository.find_all():
                    if (not order.is_ask()) and order.is_valid():
                        proposed_trades = self.matching_engine.match_order(order)
                        self.send_proposed_trade_messages(proposed_trades)

                # Check if message needs to be send on
                ttl = message.payload.ttl

                ttl.make_hop()  # Complete the hop from the previous node

                if ttl.is_alive():  # The ttl is still alive and can be forwarded
                    self.dispersy.store_update_forward([message], True, True, True)

    # Bid
    def create_bid(self, price, price_wallet_id, quantity, quantity_wallet_id, timeout):
        """
        Create an ask order (sell order)

        :param price: The price for the order in btc
        :param price_wallet_id: The type of the price (i.e. eur, btc)
        :param quantity: The quantity of the order
        :param price_wallet_id: The type of the price (i.e. eur, btc)
        :param timeout: The timeout of the order, when does the order need to be timed out
        :type price: float
        :type price_wallet_id: str
        :type quantity: float
        :type quantity_wallet_id: str
        :type timeout: float
        :return: The created order
        :rtype: Order
        """
        if price_wallet_id == quantity_wallet_id:
            raise RuntimeError("You cannot trade between the same wallet")

        # TODO(Martijn): balance check?
        if price_wallet_id not in self.wallets or not self.wallets[price_wallet_id].created:
            raise RuntimeError("Please create a %s wallet first" % price_wallet_id)

        if quantity_wallet_id not in self.wallets or not self.wallets[quantity_wallet_id].created:
            raise RuntimeError("Please create a %s wallet first" % quantity_wallet_id)

        # Convert values to value objects
        price = Price(price, price_wallet_id)
        quantity = Quantity(quantity, quantity_wallet_id)
        timeout = Timeout(timeout)

        # Create the order
        order = self.order_manager.create_bid_order(price, quantity, timeout)

        # Search for matches
        proposed_trades = self.matching_engine.match_order(order)
        self.send_proposed_trade_messages(proposed_trades)

        # Create the tick
        tick = Tick.from_order(order, self.order_book.message_repository.next_identity())
        assert isinstance(tick, Bid), type(tick)
        self.order_book.insert_bid(tick).addCallback(self.on_bid_timeout)
        self.send_bid_messages([tick])

        self._logger.debug("Bid created with price %s and quantity %s" % (price, quantity))

        return order

    def send_bid(self, bid):
        """
        Send a bid message

        :param bid: The message to send
        :type bid: Bid
        """
        assert isinstance(bid, Bid), type(bid)

        self._logger.debug("Bid send with id: %s for order with id: %s", str(bid.message_id), str(bid.order_id))

        payload = bid.to_network()

        # Add ttl and the local wan address
        payload += (Ttl.default(),) + self.get_dispersy_address()

        meta = self.get_meta_message(u"bid")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, True, True)

    def send_bid_messages(self, messages):
        for message in messages:
            self.send_bid(message)

    def on_bid(self, messages):
        for message in messages:
            bid = Bid.from_network(message.payload)

            self._logger.debug("Bid received from trader %s (price: %s, quantity: %s)", str(bid.order_id.trader_id),
                               bid.price, bid.quantity)

            # Update the pubkey register with the current address
            self.update_ip(bid.message_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            if not str(bid.order_id) in self.relayed_bids and not self.order_book.tick_exists(bid.order_id):
                self.relayed_bids.append(str(bid.order_id))
                self.order_book.insert_bid(bid).addCallback(self.on_bid_timeout)

                if self.tribler_session:
                    self.tribler_session.notifier.notify(NTFY_MARKET_ON_BID, NTFY_UPDATE, None, bid)

                # Check if message needs to be send on
                ttl = message.payload.ttl

                ttl.make_hop()  # Complete the hop from the previous node

                if ttl.is_alive():  # The ttl is still alive and can be forwarded
                    self.dispersy.store_update_forward([message], True, True, True)

    def send_offer_sync(self, target_candidate, tick):
        """
        Send an offer sync message

        :param target_candidate: The candidate to send this message to
        :type: target_candidate: WalkCandidate
        :param bid: The message to send
        :type bid: Bid
        """
        assert isinstance(target_candidate, WalkCandidate), type(target_candidate)
        assert isinstance(tick, Tick), type(tick)

        self._logger.debug("Offer sync send with id: %s for order with id: %s",
                           str(tick.message_id), str(tick.order_id))

        payload = tick.to_network()

        # Add ttl and the trader wan address
        trader_ip = self.lookup_ip(tick.order_id.trader_id)
        payload += (Ttl(1),) + trader_ip + (isinstance(tick, Ask),)

        meta = self.get_meta_message(u"offer-sync")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(target_candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_offer_sync(self, messages):
        for message in messages:
            if message.payload.is_ask:
                tick = Ask.from_network(message.payload)
                insert_method = self.order_book.insert_ask
                timeout_method = self.on_ask_timeout
            else:
                tick = Bid.from_network(message.payload)
                insert_method = self.order_book.insert_bid
                timeout_method = self.on_bid_timeout

            self.update_ip(tick.message_id.trader_id, (message.payload.address.ip, message.payload.address.port))

            if not self.order_book.tick_exists(tick.order_id):
                insert_method(tick).addCallback(timeout_method)

                if self.tribler_session:
                    self.tribler_session.notifier.notify(NTFY_MARKET_ON_BID, NTFY_UPDATE, None, tick)

    # Proposed trade
    def send_proposed_trade(self, proposed_trade):
        assert isinstance(proposed_trade, ProposedTrade), type(proposed_trade)
        destination, payload = proposed_trade.to_network()

        # Add the local address to the payload
        payload += self.get_dispersy_address()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        self._logger.debug("Sending proposed trade with own order id %s and other order id %s to trader %s (ip: %s, port: %s)",
                           str(proposed_trade.order_id), str(proposed_trade.recipient_order_id), destination, *self.lookup_ip(destination))

        meta = self.get_meta_message(u"proposed-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def send_proposed_trade_messages(self, messages):
        for message in messages:
            self.send_proposed_trade(message)

    def on_proposed_trade(self, messages):
        for message in messages:
            proposed_trade = ProposedTrade.from_network(message.payload)

            self._logger.debug("Proposed trade received with id: %s", str(proposed_trade.message_id))

            # Update the known IP address of the sender of this proposed trade
            self.update_ip(proposed_trade.message_id.trader_id,
                           (message.payload.address.ip, message.payload.address.port))

            if str(proposed_trade.recipient_order_id.trader_id) == str(self.mid):  # The message is for this node
                order = self.order_manager.order_repository.find_by_id(proposed_trade.recipient_order_id)

                if order and order.is_valid() and order.available_quantity > Quantity(0, order.available_quantity.wallet_id):  # Order is valid
                    self._logger.debug("Proposed trade received with id: %s for order with id: %s",
                                       str(proposed_trade.message_id), str(order.order_id))

                    if order.available_quantity >= proposed_trade.quantity:  # Enough quantity left
                        self.accept_trade(order, proposed_trade)
                    else:  # Not enough quantity for trade
                        counter_trade = Trade.counter(self.order_book.message_repository.next_identity(),
                                                      order.available_quantity, Timestamp.now(), proposed_trade)
                        order.reserve_quantity_for_tick(proposed_trade.order_id, order.available_quantity)
                        self._logger.debug("Counter trade made with id: %s for proposed trade with id: %s",
                                           str(counter_trade.message_id), str(proposed_trade.message_id))
                        self.send_counter_trade(counter_trade)
                else:  # Order invalid send cancel
                    declined_trade = Trade.decline(self.order_book.message_repository.next_identity(), Timestamp.now(),
                                                   proposed_trade)
                    self._logger.debug("Declined trade made with id: %s for proposed trade with id: %s "
                                       "(valid? %s, available quantity of order: %s, reserved: %s, traded: %s)",
                                       str(declined_trade.message_id), str(proposed_trade.message_id),
                                       order.is_valid(), order.available_quantity, order.reserved_quantity,
                                       order.traded_quantity)
                    self.send_declined_trade(declined_trade)
            else:
                self._logger.warning("Received proposed trade message that was not for this node "
                                     "(my id: %s, message recipient id: %s", str(self.mid),
                                     str(proposed_trade.recipient_order_id.trader_id))

    # Accepted trade
    def send_accepted_trade(self, accepted_trade):
        assert isinstance(accepted_trade, AcceptedTrade), type(accepted_trade)
        destination, payload = accepted_trade.to_network()

        # Add ttl
        payload += (Ttl.default(),) + self.get_dispersy_address()

        meta = self.get_meta_message(u"accepted-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_accepted_trade(self, messages):
        for message in messages:
            accepted_trade = AcceptedTrade.from_network(message.payload)

            if self.check_history(accepted_trade):  # The message is new to this node
                self.order_book.trade_tick(accepted_trade.order_id, accepted_trade.recipient_order_id,
                                           accepted_trade.quantity)

                ttl = message.payload.ttl  # Check if message needs to be send on
                ttl.make_hop()  # Complete the hop from the previous node
                if ttl.is_alive():  # The ttl is still alive and can be forwarded
                    self.dispersy.store_update_forward([message], True, True, True)

    # Declined trade
    def send_declined_trade(self, declined_trade):
        assert isinstance(declined_trade, DeclinedTrade), type(declined_trade)
        destination, payload = declined_trade.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        meta = self.get_meta_message(u"declined-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def send_declined_trade_messages(self, messages):
        for message in messages:
            self.send_declined_trade(message)

    def on_declined_trade(self, messages):
        for message in messages:
            declined_trade = DeclinedTrade.from_network(message.payload)

            if str(declined_trade.recipient_order_id.trader_id) == str(self.mid):  # The message is for this node
                order = self.order_manager.order_repository.find_by_id(declined_trade.recipient_order_id)

                if order:
                    try:
                        order.release_quantity_for_tick(declined_trade.order_id)
                    except TickWasNotReserved:  # Nothing left to do
                        pass

                # Just remove the tick with the order id of the other party and try to find a new match
                self._logger.debug("Received declined trade, trying to find a new match for this order")
                self.order_book.remove_tick(declined_trade.order_id)
                proposed_trades = self.matching_engine.match_order(order)
                self.send_proposed_trade_messages(proposed_trades)

    # Counter trade
    def send_counter_trade(self, counter_trade):
        assert isinstance(counter_trade, CounterTrade), type(counter_trade)
        destination, payload = counter_trade.to_network()

        # Add the local address to the payload
        payload += self.get_dispersy_address()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(destination), False)

        meta = self.get_meta_message(u"counter-trade")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def send_counter_trade_messages(self, messages):
        for message in messages:
            self.send_counter_trade(message)

    def on_counter_trade(self, messages):
        for message in messages:
            counter_trade = CounterTrade.from_network(message.payload)

            if str(counter_trade.recipient_order_id.trader_id) == str(self.mid):  # The message is for this node
                order = self.order_manager.order_repository.find_by_id(counter_trade.recipient_order_id)

                if order:
                    try:  # Accept trade
                        order.release_quantity_for_tick(counter_trade.order_id)
                        self.accept_trade(order, counter_trade)
                    except TickWasNotReserved:  # Send cancel
                        declined_trade = Trade.decline(self.order_book.message_repository.next_identity(),
                                                       Timestamp.now(), counter_trade)
                        self._logger.debug("Declined trade made with id: %s for counter trade with id: %s",
                                           str(declined_trade.message_id), str(counter_trade.message_id))
                        self.send_declined_trade(declined_trade)

    def accept_trade(self, order, proposed_trade):
        accepted_trade = Trade.accept(self.order_book.message_repository.next_identity(), Timestamp.now(),
                                      proposed_trade)

        self._logger.debug("Accepted trade made with id: %s for proposed/counter trade with id: %s (quantity: %s)",
                           str(accepted_trade.message_id), str(proposed_trade.message_id), accepted_trade.quantity)

        self.check_history(accepted_trade)  # Set the message received as true

        self.order_book.insert_trade(accepted_trade)
        order.add_trade(accepted_trade.recipient_order_id, accepted_trade.quantity)
        self.order_book.trade_tick(accepted_trade.order_id, accepted_trade.recipient_order_id, accepted_trade.quantity)

        self.send_accepted_trade(accepted_trade)
        self.start_transaction(accepted_trade)

    # Transactions
    def start_transaction(self, accepted_trade):
        order = self.order_manager.order_repository.find_by_id(accepted_trade.order_id)

        if order:
            transaction = self.transaction_manager.create_from_accepted_trade(accepted_trade)

            start_transaction = StartTransaction(self.order_book.message_repository.next_identity(),
                                                 transaction.transaction_id, order.order_id,
                                                 accepted_trade.recipient_order_id, accepted_trade.price,
                                                 accepted_trade.quantity, Timestamp.now())
            self.send_start_transaction(transaction, start_transaction)

    # Start transaction
    def send_start_transaction(self, transaction, start_transaction):
        assert isinstance(start_transaction, StartTransaction), type(start_transaction)
        payload = start_transaction.to_network()

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)

        meta = self.get_meta_message(u"start-transaction")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_start_transaction(self, messages):
        for message in messages:
            start_transaction = StartTransaction.from_network(message.payload)

            # The receipient_order_id in the start_transaction message is our own order
            order = self.order_manager.order_repository.find_by_id(start_transaction.recipient_order_id)

            if order:
                transaction = self.transaction_manager.create_from_start_transaction(start_transaction, order)

                try:
                    order.add_trade(start_transaction.order_id, start_transaction.quantity)
                except TickWasNotReserved:  # Something went wrong
                    pass

                incoming_address, outgoing_address = self.get_order_addresses(order)
                self.send_wallet_info(transaction, incoming_address, outgoing_address)

    def send_wallet_info(self, transaction, incoming_address, outgoing_address):
        assert isinstance(transaction, Transaction), type(transaction)

        # Update the transaction with the address information
        transaction.incoming_address = incoming_address
        transaction.outgoing_address = outgoing_address

        # Lookup the remote address of the peer with the pubkey
        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)

        self._logger.debug("Sending wallet info to trader %s (incoming address: %s, outgoing address: %s",
                           transaction.partner_trader_id, incoming_address, outgoing_address)

        message_id = self.order_book.message_repository.next_identity()

        meta = self.get_meta_message(u"wallet-info")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(
                message_id.trader_id,
                message_id.message_number,
                transaction.transaction_id.trader_id,
                transaction.transaction_id.transaction_number,
                incoming_address,
                outgoing_address,
                Timestamp.now(),
            )
        )

        self.dispersy.store_update_forward([message], True, False, True)
        transaction.sent_wallet_info = True

    def on_wallet_info(self, messages):
        for message in messages:
            transaction = self.transaction_manager.find_by_id(
                TransactionId(message.payload.transaction_trader_id, message.payload.transaction_number))
            transaction.received_wallet_info = True

            transaction.partner_outgoing_address = message.payload.outgoing_address
            transaction.partner_incoming_address = message.payload.incoming_address

            if not transaction.sent_wallet_info:
                order = self.order_manager.order_repository.find_by_id(transaction.order_id)
                incoming_address, outgoing_address = self.get_order_addresses(order)
                self.send_wallet_info(transaction, incoming_address, outgoing_address)
            else:

                self.send_payment(transaction)

    def send_payment(self, transaction):
        transfer_quantity, transfer_price = transaction.next_payment()
        order = self.order_manager.order_repository.find_by_id(transaction.order_id)

        if order.is_ask():
            wallet_id = transaction.total_quantity.wallet_id
            transfer_amount = float(transfer_quantity)
        else:
            wallet_id = transaction.price.wallet_id
            transfer_amount = float(transfer_price)

        wallet = self.wallets[wallet_id]
        if not wallet or not wallet.created:
            raise RuntimeError("No %s wallet present" % wallet_id)

        payment_tup = (transfer_quantity, transfer_price)
        # TODO this should be refactored to the MultichainWallet
        if isinstance(wallet, MultichainWallet):
            candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)
            member = self.dispersy.get_member(public_key=b64decode(str(transaction.partner_incoming_address)))
            candidate.associate(member)
            transfer_deferred = wallet.transfer(float(transfer_amount), candidate)
        else:
            transfer_deferred = wallet.transfer(float(transfer_amount))

        # TODO add errback for insufficient funds
        transfer_deferred.addCallback(lambda txid: self.send_payment_message(PaymentId(txid), transaction, payment_tup))

    def send_payment_message(self, payment_id, transaction, payment):
        message_id = self.order_book.message_repository.next_identity()
        payment_message = self.transaction_manager.create_payment_message(message_id, payment_id, transaction, payment)
        payload = payment_message.to_network()

        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)
        meta = self.get_meta_message(u"payment")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=payload
        )

        self.dispersy.store_update_forward([message], True, False, True)

    def on_payment_message(self, messages):
        for message in messages:
            payment_message = Payment.from_network(message.payload)
            transaction = self.transaction_manager.find_by_id(payment_message.transaction_id)
            order = self.order_manager.order_repository.find_by_id(transaction.order_id)

            if order.is_ask():
                wallet_id = payment_message.transferee_price.wallet_id
                monitor_amount = float(payment_message.transferee_price)
            else:
                wallet_id = payment_message.transferee_quantity.wallet_id
                monitor_amount = float(payment_message.transferee_quantity)

            wallet = self.wallets[wallet_id]
            transaction_deferred = wallet.monitor_transaction(payment_message.payment_id)
            transaction_deferred.addCallback(lambda _: self.received_payment(payment_message, transaction))

    def received_payment(self, payment, transaction):
        transaction.add_payment(payment)
        self.transaction_manager.transaction_repository.update(transaction)

        if not transaction.is_payment_complete():
            self.send_payment(transaction)
        else:
            self.send_end_transaction(transaction)

    # End transaction
    def send_end_transaction(self, transaction):
        # Lookup the remote address of the peer with the pubkey
        self._logger.debug("Sending end transaction (quantity: %s)", transaction.total_quantity)
        candidate = Candidate(self.lookup_ip(transaction.partner_trader_id), False)

        message_id = self.order_book.message_repository.next_identity()

        meta = self.get_meta_message(u"end-transaction")
        message = meta.impl(
            authentication=(self.my_member,),
            distribution=(self.claim_global_time(),),
            destination=(candidate,),
            payload=(
                message_id.trader_id,
                message_id.message_number,
                transaction.transaction_id.trader_id,
                transaction.transaction_id.transaction_number,
                Timestamp.now(),
            )
        )

        self.dispersy.store_update_forward([message], True, False, True)
        self.notify_transaction_complete(transaction)

        def send_tradechain_request(_):
            # TODO add a check that this transaction really happened
            quantity = transaction.total_quantity
            price = transaction.price
            self.tradechain_community.sign_block(candidate, price.int_wallet_id, float(price),
                                                 quantity.int_wallet_id, float(quantity))

        if self.tradechain_community:
            member = self.dispersy.get_member(mid=str(transaction.partner_trader_id).decode('hex'))
            candidate.associate(member)
            self.tradechain_community.add_discovered_candidate(candidate)
            new_candidate = self.tradechain_community.get_candidate(candidate.sock_addr)

            self.tradechain_community.create_introduction_request(new_candidate, False)
            self.tradechain_community.wait_for_intro_of_candidate(new_candidate).addCallback(send_tradechain_request)

    def on_end_transaction(self, messages):
        for message in messages:
            self._logger.debug("Finishing transaction %s", message.payload.transaction_number)
            transaction_id = TransactionId(message.payload.transaction_trader_id, message.payload.transaction_number)
            self.notify_transaction_complete(self.transaction_manager.find_by_id(transaction_id))

    def notify_transaction_complete(self, transaction):
        if self.tribler_session:
            self.tribler_session.notifier.notify(NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE, None, transaction)
