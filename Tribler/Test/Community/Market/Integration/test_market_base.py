import os

import sys
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred

import Tribler
from Tribler.Test.Community.Multichain.test_multichain_utilities import TestBlock
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.market.community import MarketCommunity
from Tribler.community.multichain.community import MultiChainCommunity
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


class MultiChainCommunityTests(MultiChainCommunity):
    """
    We are using a seperate community so we do not interact with the live market.
    """
    master_key = ""

    @classmethod
    def get_master_members(cls, dispersy):
        master_key_hex = MultiChainCommunityTests.master_key.decode("HEX")
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
        ec = self.eccrypto.generate_key(u"curve25519")
        MultiChainCommunityTests.master_key = self.eccrypto.key_to_bin(ec.pub()).encode('hex')

        self.market_communities = {}
        mc_community = self.load_multichain_community_in_session(self.session)
        self.give_multichain_credits(mc_community, 10)
        self.load_market_community_in_session(self.session)
        self.load_btc_wallet_in_session(self.session, 0)

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
        self.config.set_enable_multichain(False)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_market_community_enabled(False)

    def give_multichain_credits(self, mc_community, amount):
        block = TestBlock()
        block.up = amount
        block.down = 0
        block.total_up_requester = amount
        block.total_down_requester = 0
        block.public_key_requester = mc_community._public_key
        mc_community.persistence.add_block(block)

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

    @blocking_call_on_reactor_thread
    def load_multichain_community_in_session(self, session):
        """
        Load a custom instance of the multichain community in a given session.
        """
        dispersy = session.get_dispersy_instance()
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        multichain_kwargs = {'tribler_session': session}
        return dispersy.define_auto_load(MultiChainCommunityTests, dispersy_member, load=True, kargs=multichain_kwargs)[0]

    def load_btc_wallet_in_session(self, session, index):
        if os.environ.get('SESSION_%d_BTC_WALLET_PATH' % index):
            wallet_path = os.environ.get('SESSION_%d_BTC_WALLET_PATH' % index)
            wallet_dir, wallet_file_name = os.path.split(wallet_path)
            session.lm.btc_wallet.load_wallet(wallet_dir, wallet_file_name)
        else:
            session.lm.btc_wallet.create_wallet(password=session.lm.btc_wallet.get_wallet_password())

        def mocked_monitor_transaction(_):
            monitor_deferred = Deferred()
            reactor.callLater(0.5, monitor_deferred.callback, None)
            return monitor_deferred

        def add_transaction(txid):
            # Make sure we can find the electrum wallet
            sys.path.append(os.path.join(os.path.dirname(os.path.abspath(Tribler.__file__)), '..', 'electrum'))
            import imp
            imp.load_module('electrum', *imp.find_module('lib'))
            from electrum import Transaction

            fake_transaction = Transaction(None)
            fake_transaction._inputs = [{'is_coinbase': False,
                                         'prevout_hash': '3140eb24b43386f35ba69e3875eb6c93130ac66201d01c58f598defc949a5c2a',
                                         'prevout_n': 0}]
            fake_transaction._outputs = [[0, 395599, False]]
            session.lm.btc_wallet.wallet.receive_tx_callback(txid, fake_transaction, 0)

        if self.should_fake_btc:
            session.lm.btc_wallet.get_balance = lambda: {"confirmed": 50, "unconfirmed": 0, "unmatured": 0}
            session.lm.btc_wallet.transfer = lambda *_: 'abcd'
            session.lm.btc_wallet.monitor_transaction = mocked_monitor_transaction

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

        self.load_btc_wallet_in_session(session, index)

        self.load_multichain_community_in_session(session)
        self.load_market_community_in_session(session)
        returnValue(session)
