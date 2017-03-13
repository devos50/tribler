import os

import sys

import logging

import Tribler

from Tribler.Core.Modules.wallet.wallet import Wallet

# Make sure we can find the electrum wallet
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(Tribler.__file__)), '..', 'electrum'))

import imp
imp.load_module('electrum', *imp.find_module('lib'))

from electrum import SimpleConfig
from electrum import WalletStorage
from electrum.mnemonic import Mnemonic
from electrum import keystore
from electrum import Wallet as ElectrumWallet


class BitcoinWallet(Wallet):
    """
    This class is responsible for handling your wallet of bitcoins.
    """

    def __init__(self, session):
        super(BitcoinWallet, self).__init__()

        config = SimpleConfig(options={'cwd': session.get_state_dir(),
                                       'wallet_path': os.path.join('wallet', 'btc_wallet')})
        self._logger = logging.getLogger(self.__class__.__name__)
        self.storage = WalletStorage(config.get_wallet_path())
        self.storage.read(None)

        if not os.path.exists(os.path.join(session.get_state_dir(), 'wallet', 'btc_wallet')):
            self.wallet = self.create_wallet()
        else:
            self.wallet = ElectrumWallet(self.storage)

    def get_identifier(self):
        return 'btc'

    def create_wallet(self):
        """
        Create a new bitcoin wallet.
        """
        seed = Mnemonic('en').make_seed()
        k = keystore.from_seed(seed, '')
        self.storage.put('keystore', k.dump())
        self.storage.put('wallet_type', 'standard')
        self.storage.put('use_encryption', False)
        self.storage.write()

        wallet = ElectrumWallet(self.storage)
        wallet.synchronize()
        wallet.storage.write()

        self._logger.info("Bitcoin wallet saved in '%s'" % wallet.storage.path)
        return wallet

    def get_balance(self):
        """
        Return the balance of the wallet.
        """
        confirmed, unconfirmed, unmatured = self.wallet.get_balance()
        return {"confirmed": confirmed, "unconfirmed": unconfirmed, "unmatured": unmatured}
