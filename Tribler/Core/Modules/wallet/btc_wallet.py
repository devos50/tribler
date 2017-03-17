import os

import sys

import logging
from time import sleep

import datetime

import Tribler

from Tribler.Core.Modules.wallet.wallet import Wallet, InsufficientFunds

# Make sure we can find the electrum wallet
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(Tribler.__file__)), '..', 'electrum'))

import imp
imp.load_module('electrum', *imp.find_module('lib'))

from electrum import SimpleConfig
from electrum import WalletStorage
from electrum import daemon
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
        self.tribler_session = session
        self.created = False
        self.daemon = None
        self.storage = WalletStorage(config.get_wallet_path())
        self.storage.read(None)

        if os.path.exists(os.path.join(session.get_state_dir(), 'wallet', 'btc_wallet')):
            self.wallet = ElectrumWallet(self.storage)
            self.created = True
            self.start_daemon()

    def start_daemon(self):
        options = {'verbose': False, 'cmd': 'daemon', 'testnet': False, 'oneserver': False, 'segwit': False,
                   'cwd': self.tribler_session.get_state_dir(), 'portable': False, 'password': '',
                   'wallet_path': os.path.join('wallet', 'btc_wallet')}
        config = SimpleConfig(options)
        fd, server = daemon.get_fd_or_server(config)
        self.daemon = daemon.Daemon(config, fd)
        self.daemon.start()

        options = {'password': None, 'subcommand': 'open', 'verbose': False, 'cmd': 'daemon', 'testnet': False,
                   'oneserver': False, 'segwit': False, 'cwd': self.tribler_session.get_state_dir(), 'portable': False,
                   'wallet_path': os.path.join('wallet', 'btc_wallet')}
        config = SimpleConfig(options)

        server = daemon.get_server(config)
        if server is not None:
            # Run the command to open the wallet
            server.daemon(options)

    def get_identifier(self):
        return 'btc'

    def create_wallet(self, password=''):
        """
        Create a new bitcoin wallet.
        """
        seed = Mnemonic('en').make_seed()
        k = keystore.from_seed(seed, '')
        k.update_password(None, password)
        self.storage.put('keystore', k.dump())
        self.storage.put('wallet_type', 'standard')
        self.storage.put('use_encryption', bool(password))
        self.storage.write()

        self.wallet = ElectrumWallet(self.storage)
        self.wallet.synchronize()
        self.wallet.storage.write()
        self.created = True
        self.start_daemon()

        self._logger.info("Bitcoin wallet saved in '%s'" % self.wallet.storage.path)

    def get_balance(self):
        """
        Return the balance of the wallet.
        """
        divider = 100000000
        if self.created:
            confirmed, unconfirmed, unmatured = self.wallet.get_balance()
            return {"confirmed": float(confirmed) / divider,
                    "unconfirmed": float(unconfirmed) / divider,
                    "unmatured": float(unmatured) / divider}
        else:
            return {"confirmed": 0, "unconfirmed": 0, "unmatured": 0}

    def transfer(self, amount, address):
        self._logger.info("Creating Bitcoin payment with amount %f to address %s", amount, address)
        if self.get_balance()['confirmed'] >= amount:
            # TODO(Martijn): actually transfer the BTC...
            pass
        else:
            raise InsufficientFunds()

    def get_address(self):
        if not self.created:
            return None
        return self.wallet.get_receiving_address()

    def get_transactions(self):
        self.wallet.load_transactions()
        out = []
        for item in self.wallet.get_history():
            tx_hash, height, conf, timestamp, value, balance = item
            if timestamp:
                date = datetime.datetime.fromtimestamp(timestamp).isoformat(' ')[:-3]
            else:
                date = "----"
            label = self.wallet.get_label(tx_hash)
            out.append({
                'txid': tx_hash,
                'timestamp': timestamp,
                'date': date,
                'label': label,
                'value': float(value) / 100000000 if value is not None else None,
                'height': height,
                'confirmations': conf
            })
        return out
