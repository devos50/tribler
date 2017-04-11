import os

import sys

import logging
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred

import Tribler
from Tribler.Test.Community.Multichain.test_multichain_utilities import TestBlock
from Tribler.Test.common import TESTS_DATA_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.market.community import MarketCommunity
from Tribler.community.market.wallet.btc_wallet import BitcoinWallet
from Tribler.community.market.wallet.mc_wallet import MultichainWallet
from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.community.tradechain.community import TradeChainCommunity
from Tribler.dispersy.crypto import ECCrypto
from Tribler.dispersy.discovery.community import BOOTSTRAP_FILE_ENVNAME
from Tribler.dispersy.util import blocking_call_on_reactor_thread


logging.basicConfig(level=logging.DEBUG)


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


class TradeChainCommunityTests(TradeChainCommunity):
    """
    We are using a seperate community so we do not interact with the live market.
    """
    master_key = ""

    def __init__(self, *args, **kwargs):
        super(TradeChainCommunityTests, self).__init__(*args, **kwargs)
        self.expected_sig_response = None

    def wait_for_signature_response(self):
        response_deferred = Deferred()
        self.expected_sig_response = response_deferred
        return response_deferred

    @classmethod
    def get_master_members(cls, dispersy):
        master_key_hex = TradeChainCommunityTests.master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]

    def received_half_block(self, messages):
        super(TradeChainCommunityTests, self).received_half_block(messages)

        self.expected_sig_response.callback(None)
        self.expected_sig_response = None


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
        ec = self.eccrypto.generate_key(u"curve25519")
        TradeChainCommunityTests.master_key = self.eccrypto.key_to_bin(ec.pub()).encode('hex')

        market_member = self.generate_member(self.session)

        self.market_communities = {}
        mc_community = self.load_multichain_community_in_session(self.session)
        market_community = self.load_market_community_in_session(self.session, market_member, mc_community)
        self.load_btc_wallet_in_market(market_community, 0)

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

    def generate_member(self, session):
        dispersy = session.get_dispersy_instance()
        keypair = dispersy.crypto.generate_key(u"curve25519")
        return dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))

    @blocking_call_on_reactor_thread
    def load_market_community_in_session(self, session, market_member, mc_community):
        """
        Load the market community and tradechain community in a given session.
        """
        wallets = {'BTC': BitcoinWallet(os.path.join(session.get_state_dir(), 'wallet')),
                   'MC': MultichainWallet(mc_community)}
        wallets['MC'].check_negative_balance = False

        dispersy = session.get_dispersy_instance()

        # Load TradeChain
        tradechain_kwargs = {'tribler_session': session}
        tradechain_community = dispersy.define_auto_load(TradeChainCommunityTests,
                                                         market_member, load=True, kargs=tradechain_kwargs)[0]

        # Load MarketCommunity
        market_kargs = {'tribler_session': session, 'tradechain_community': tradechain_community, 'wallets': wallets}
        self.market_communities[session] = dispersy.define_auto_load(
            MarketCommunityTests, market_member, kargs=market_kargs, load=True)[0]
        return self.market_communities[session]

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

    def load_btc_wallet_in_market(self, market, index):
        if os.environ.get('SESSION_%d_BTC_WALLET_PATH' % index):
            wallet_path = os.environ.get('SESSION_%d_BTC_WALLET_PATH' % index)
            wallet_dir, wallet_file_name = os.path.split(wallet_path)
            market.wallets['BTC'].wallet_password = os.environ.get('SESSION_%d_BTC_WALLET_PASSWORD' % index)
            market.wallets['BTC'].load_wallet(wallet_dir, wallet_file_name)
        else:
            market.wallets['BTC'].create_wallet()

        def mocked_monitor_transaction(_):
            monitor_deferred = Deferred()
            reactor.callLater(0.5, monitor_deferred.callback, None)
            return monitor_deferred

        if self.should_fake_btc:
            market.wallets['BTC'].get_balance = lambda: {"confirmed": 50, "unconfirmed": 0, "unmatured": 0}
            market.wallets['BTC'].transfer = lambda *_: 'abcd'
            market.wallets['BTC'].monitor_transaction = mocked_monitor_transaction

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

        market_member = self.generate_member(session)
        mc_community = self.load_multichain_community_in_session(session)
        market_community = self.load_market_community_in_session(session, market_member, mc_community)
        self.load_btc_wallet_in_market(market_community, index)
        returnValue(session)
