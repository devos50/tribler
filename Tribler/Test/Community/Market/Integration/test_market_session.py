from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.task import LoopingCall

from Tribler.Core.simpledefs import NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE
from Tribler.Test.Community.Market.Integration.test_market_base import TestMarketBase
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMarketSession(TestMarketBase):
    """
    This class contains some integration tests for the market community.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_e2e_transaction(self):
        """
        test whether a full transaction will be executed between two nodes.
        """
        bid_session = yield self.create_session(1)
        test_deferred = Deferred()

        def on_signature_response(_):
            test_deferred.callback(None)

        ask_community = self.market_communities[self.session]
        bid_community = self.market_communities[bid_session]

        ask_community.add_discovered_candidate(
            Candidate(bid_session.get_dispersy_instance().lan_address, tunnel=False))
        bid_community.add_discovered_candidate(
            Candidate(self.session.get_dispersy_instance().lan_address, tunnel=False))
        yield self.async_sleep(5)  # TODO(Martijn): make this event-based
        bid_community.create_bid(0.0001, 2, 3600)
        yield self.async_sleep(1)
        ask_community.create_ask(0.0001, 2, 3600)

        ask_community.tradechain_community.wait_for_signature_response().addCallback(on_signature_response)
        bid_community.tradechain_community.wait_for_signature_response().addCallback(on_signature_response)

        yield test_deferred

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_orderbook_sync(self):
        """
        Test whether the order book of two nodes are being synchronized
        """
        def check_orderbook_size():
            if len(ask_community.order_book.bids) == 1 and len(bid_community.order_book.asks) == 1:
                check_lc.stop()
                test_deferred.callback(None)

        test_deferred = Deferred()
        bid_session = yield self.create_session(1)
        ask_community = self.market_communities[self.session]
        bid_community = self.market_communities[bid_session]

        ask_community.create_ask(10, 2, 3600)
        bid_community.create_bid(1, 2, 3600)  # Does not match the ask

        ask_community.add_discovered_candidate(
            Candidate(bid_session.get_dispersy_instance().lan_address, tunnel=False))
        check_lc = LoopingCall(check_orderbook_size)
        check_lc.start(0.2)

        yield test_deferred
