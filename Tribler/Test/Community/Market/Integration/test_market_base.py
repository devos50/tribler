import os

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred

from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.market.community import MarketCommunity
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.discovery.community import BOOTSTRAP_FILE_ENVNAME
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class MarketCommunityTests(MarketCommunity):
    """
    We are using a seperate community so we do not interact with the live market.
    """
    master_key = ""

    @classmethod
    def get_master_members(cls, dispersy):
        master_key_hex = MarketCommunityTests.master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]


class TestMarketBase(TestAsServer):

    def async_sleep(self, secs):
        d = Deferred()
        reactor.callLater(secs, d.callback, None)
        return d

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        """
        Setup various variables.
        """
        os.environ[BOOTSTRAP_FILE_ENVNAME] = os.path.join(TESTS_DATA_DIR, 'bootstrap_empty.txt')

        yield TestAsServer.setUp(self, autoload_discovery=autoload_discovery)

        self.should_fake_btc = True
        self.sessions = []
        self.eccrypto = ECCrypto()
        ec = self.eccrypto.generate_key(u"curve25519")
        MarketCommunityTests.master_key = self.eccrypto.key_to_bin(ec.pub()).encode('hex')

        self.market_communities = {}
        self.load_market_community_in_session(self.session)
        self.create_btc_wallet_in_session(self.session)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        for session in self.sessions:
            yield session.shutdown()

        yield TestAsServer.tearDown(self)

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_dispersy(True)
        self.config.set_libtorrent(False)
        self.config.set_videoserver_enabled(False)
        self.config.set_enable_multichain(True)
        self.config.set_tunnel_community_enabled(True)
        self.config.set_market_community_enabled(False)

    @blocking_call_on_reactor_thread
    def load_market_community_in_session(self, session):
        """
        Load the market community in a given session.
        """
        dispersy = session.get_dispersy_instance()
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        self.market_communities[session] = dispersy.define_auto_load(
            MarketCommunityTests, dispersy_member, (session,), load=True)[0]

    def create_btc_wallet_in_session(self, session):
        session.lm.btc_wallet.create_wallet()

        if self.should_fake_btc:
            session.lm.btc_wallet.get_balance = lambda: {"confirmed": 50, "unconfirmed": 0, "unmatured": 0}

    @inlineCallbacks
    def create_session(self, index):
        """
        Create a single session and load the tunnel community in the session of that proxy.
        """
        from Tribler.Core.Session import Session

        config = self.config.copy()
        config.set_state_dir(self.getStateDir(index))

        session = Session(config, ignore_singleton=True, autoload_discovery=False)
        yield session.start()
        self.sessions.append(session)

        self.create_btc_wallet_in_session(session)

        self.load_market_community_in_session(session)
        returnValue(session)
