from twisted.internet.defer import inlineCallbacks, Deferred

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

        def on_end_transaction(*_):
            if not on_end_transaction.called:
                test_deferred.callback(None)
                on_end_transaction.called = True

        on_end_transaction.called = False
        self.session.notifier.add_observer(on_end_transaction, NTFY_MARKET_ON_TRANSACTION_COMPLETE, [NTFY_UPDATE])
        bid_session.notifier.add_observer(on_end_transaction, NTFY_MARKET_ON_TRANSACTION_COMPLETE, [NTFY_UPDATE])

        ask_community = self.market_communities[self.session]
        bid_community = self.market_communities[bid_session]
        ask_community.add_discovered_candidate(
            Candidate(bid_session.get_dispersy_instance().lan_address, tunnel=False))
        bid_community.add_discovered_candidate(
            Candidate(self.session.get_dispersy_instance().lan_address, tunnel=False))
        yield self.async_sleep(5)
        bid_community.create_bid(1, 2, 3600)
        yield self.async_sleep(1)
        ask_community.create_ask(1, 2, 3600)
        yield test_deferred

        self.assertEqual(self.session.lm.wallets['mc'].get_balance()['net'], 8)
