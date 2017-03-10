import time
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.python.threadable import isInIOThread

from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.community.market.community import MarketCommunity
from Tribler.dispersy.tests.debugcommunity.node import DebugNode
from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMarketTrade(TriblerCoreTest, DispersyTestFunc):
    """
    This class contains tests for trading between nodes.
    """

    def async_sleep(self, secs):
        d = Deferred()
        reactor.callLater(secs, d.callback, None)
        return d

    @blocking_call_on_reactor_thread
    def _create_target(self, source, destination):
        target = destination.my_candidate
        return target

    def introduce_node(self, source, destination):
        """
        Introduce node source to node destination
        """
        source.send_identity(destination)
        destination.community.add_discovered_candidate(self._create_target(destination, source))
        destination.community.candidates.values()[0].stumble(time.time())
        destination.community.candidates.values()[0].associate(
            destination._dispersy.get_member(public_key=source.my_pub_member.public_key))

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        yield TriblerCoreTest.setUp(self, annotate=annotate)
        yield DispersyTestFunc.setUp(self)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        DispersyTestFunc.tearDown(self)
        yield TriblerCoreTest.tearDown(self, annotate=annotate)

    def create_nodes(self, *args, **kwargs):
        return super(TestMarketTrade, self).create_nodes(*args, community_class=MarketCommunity,
                                                         memory_database=False, **kwargs)

    def _create_node(self, dispersy, community_class, c_master_member):
        return DebugNode(self, dispersy, community_class, c_master_member, curve=u"curve25519")

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_trade(self):
        """
        Test whether a simple trade between two nodes can be made
        """
        ask_node, bid_node = yield self.create_nodes(2)

        self.introduce_node(ask_node, bid_node)
        self.introduce_node(bid_node, ask_node)

        ask_node.community.create_ask(1, 1, 3600)
        bid_node.community.create_bid(1, 1, 3600)
        ask_node.process_packets()
        bid_node.process_packets()
        yield self.async_sleep(0.5)
        ask_node.process_packets()
        bid_node.process_packets()
        yield self.async_sleep(0.5)
        _, message = bid_node.receive_message(names=[u"start-transaction"]).next()
        self.assertTrue(message)
