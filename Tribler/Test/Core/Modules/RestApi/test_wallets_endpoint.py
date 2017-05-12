import json

from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestWalletsEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    def setUpPreSession(self):
        super(TestWalletsEndpoint, self).setUpPreSession()
        self.config.set_enable_multichain(True)
        self.config.set_dispersy(True)
        self.config.set_tunnel_community_enabled(True)

    @deferred(timeout=20)
    def test_get_wallets(self):
        """
        Testing whether the API returns wallets when we query for them
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('wallets', json_response)
            self.assertGreaterEqual(len(json_response['wallets']), 2)

        self.should_check_equality = False
        return self.do_request('wallets', expected_code=200).addCallback(on_response)

    @deferred(timeout=20)
    def test_create_wallet_exists(self):
        """
        Testing whether creating a wallet that already exists throws an error
        """
        self.should_check_equality = False
        return self.do_request('wallets/DUM1', expected_code=400, request_type='PUT')

    @deferred(timeout=20)
    def test_create_wallet(self):
        """
        Testing whether we can create a wallet
        """
        self.session.lm.market_community.wallets['DUM1'].created = False
        self.should_check_equality = False
        return self.do_request('wallets/DUM1', expected_code=200, request_type='PUT')

    @deferred(timeout=20)
    def test_get_wallet_balance(self):
        """
        Testing whether we can retrieve the balance of a wallet
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('balance', json_response)
            self.assertGreater(json_response['balance']['available'], 0)

        self.should_check_equality = False
        return self.do_request('wallets/DUM1/balance', expected_code=200).addCallback(on_response)

    @deferred(timeout=20)
    def test_get_wallet_transaction(self):
        """
        Testing whether we can receive the transactions of a wallet
        """
        def on_response(response):
            json_response = json.loads(response)
            self.assertIn('transactions', json_response)

        self.should_check_equality = False
        return self.do_request('wallets/DUM1/transactions', expected_code=200).addCallback(on_response)
