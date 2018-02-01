from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.python.threadable import isInIOThread

from Tribler.Core.simpledefs import DLSTATUS_SEEDING
from Tribler.Test.Community.Tunnel.FullSession.test_tunnel_base import TestTunnelBase
from Tribler.Test.twisted_thread import deferred
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTunnelCommunity(TestTunnelBase):
    """
    This class contains full session tests for the tunnel community.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        self.test_deferred = Deferred()
        yield super(TestTunnelCommunity, self).setUp(autoload_discovery=autoload_discovery)

    @deferred(timeout=60)
    @inlineCallbacks
    def test_anon_download(self):
        """
        Testing whether an anonymous download over our tunnels works and the downloader pays the right amount.
        """
        yield self.setup_nodes()

        @blocking_call_on_reactor_thread
        def download_state_callback(ds):
            download = ds.get_download()
            if download.get_progress() == 1.0 and ds.get_status() == DLSTATUS_SEEDING:
                for circuit_id in self.tunnel_communities[-1].circuits.keys():
                    self.tunnel_communities[-1].remove_circuit(circuit_id, 'test_finished', destroy=True)

            if self.tunnel_communities[-1].get_bandwidth_tokens() < 0:
                self.test_deferred.callback(None)

            return 2.0, False

        download = self.start_anon_download()
        download.set_state_callback(download_state_callback)

        yield self.test_deferred

    @deferred(timeout=60)
    @inlineCallbacks
    def test_anon_download_no_exitnodes(self):
        """
        Testing whether an anon download does not make progress without exit nodes
        """
        assert isInIOThread()
        yield self.setup_nodes(num_exitnodes=0)

        def download_state_callback(ds):
            download = ds.get_download()
            if download.get_progress() != 0.0:
                self.test_deferred.errback(
                    RuntimeError("Anonymous download should not make progress without exit nodes"))
                return 0.0, False
            return 2.0, False

        download = self.start_anon_download()
        download.set_state_callback(download_state_callback)

        reactor.callLater(30, self.test_deferred.callback, None)

        yield self.test_deferred

    @deferred(timeout=60)
    @inlineCallbacks
    def test_anon_download_no_relays(self):
        """
        Testing whether an anon download does not make progress without relay nodes
        """
        yield self.setup_nodes(num_relays=0, num_exitnodes=1)

        def download_state_callback(ds):
            download = ds.get_download()
            if download.get_progress() != 0.0:
                self.test_deferred.errback(
                    RuntimeError("Anonymous download should not make progress without relay nodes"))
                return 0.0, False
            return 2.0, False

        download = self.start_anon_download(hops=2)
        download.set_state_callback(download_state_callback)

        reactor.callLater(30, self.test_deferred.callback, None)

        yield self.test_deferred
