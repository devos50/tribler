import os

import sys

import logging

import datetime
from threading import Thread

import keyring
from twisted.internet import reactor
from twisted.internet.defer import Deferred

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

        self.wallet_dir = os.path.join(session.get_state_dir(), 'wallet')
        self.wallet_file = 'btc_wallet'
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tribler_session = session
        self.min_confirmations = 0
        self.created = False
        self.daemon = None
        keychain_pw = self.get_wallet_password()
        self.wallet_password = keychain_pw if len(keychain_pw) > 0 else None
        self.monitored_transactions = {}
        self.storage = None
        self.wallet = None
        self.load_wallet(self.wallet_dir, self.wallet_file)

    def load_wallet(self, wallet_dir, wallet_file):
        self.wallet_dir = wallet_dir
        self.wallet_file = wallet_file

        config = SimpleConfig(options={'cwd': self.wallet_dir, 'wallet_path': self.wallet_file})
        self.storage = WalletStorage(config.get_wallet_path())
        self.storage.read(self.wallet_password)

        if os.path.exists(config.get_wallet_path()):
            self.wallet = ElectrumWallet(self.storage)
            self.created = True
            self.start_daemon()
            self.open_wallet()

    def get_wallet_password(self):
        return keyring.get_password('tribler', 'btc_wallet_password')

    def set_wallet_password(self, password):
        keyring.set_password('tribler', 'btc_wallet_password', password)

    def start_daemon(self):
        options = {'verbose': False, 'cmd': 'daemon', 'testnet': False, 'oneserver': False, 'segwit': False,
                   'cwd': self.tribler_session.get_state_dir(), 'portable': False, 'password': '',
                   'wallet_path': os.path.join('wallet', 'btc_wallet')}
        config = SimpleConfig(options)
        fd, server = daemon.get_fd_or_server(config)

        if not fd:
            return

        self.daemon = daemon.Daemon(config, fd)
        self.daemon.start()

    def open_wallet(self):
        options = {'password': self.wallet_password, 'subcommand': 'open', 'verbose': False,
                   'cmd': 'daemon', 'testnet': False, 'oneserver': False, 'segwit': False,
                   'cwd': self.wallet_dir, 'portable': False, 'wallet_path': self.wallet_file}
        config = SimpleConfig(options)

        server = daemon.get_server(config)
        if server is not None:
            # Run the command to open the wallet
            server.daemon(options)

        self.wallet.receive_tx_callback = self.on_received_tx

    def on_received_tx(self, tx_hash, tx, tx_height):
        self.wallet.add_transaction(tx_hash, tx)
        self.wallet.add_unverified_tx(tx_hash, tx_height)

        if tx_hash in self.monitored_transactions:
            self.monitored_transactions[tx_hash].callback(None)
            del self.monitored_transactions[tx_hash]

    def get_identifier(self):
        return 'btc'

    def create_wallet(self, password=''):
        """
        Create a new bitcoin wallet.
        """
        self._logger.info("Creating wallet in %s", self.tribler_session.get_state_dir())

        def run_on_thread(callable):
            # We are running code that writes to the wallet on a separate thread.
            # This is done because ethereum does not allow writing to a wallet from a daemon thread.
            wallet_thread = Thread(target=lambda: callable(), name="ethereum-create-wallet")
            wallet_thread.setDaemon(False)
            wallet_thread.start()
            wallet_thread.join()

        seed = Mnemonic('en').make_seed()
        k = keystore.from_seed(seed, '')
        k.update_password(None, password)
        self.storage.put('keystore', k.dump())
        self.storage.put('wallet_type', 'standard')
        self.storage.set_password(password, bool(password))
        run_on_thread(self.storage.write)

        self.wallet = ElectrumWallet(self.storage)
        self.wallet.synchronize()
        run_on_thread(self.wallet.storage.write)
        self.created = True

        self.set_wallet_password(password)
        self.wallet_password = password

        self.start_daemon()
        self.open_wallet()

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
            return "abcd"
        else:
            raise InsufficientFunds()

    def monitor_transaction(self, txid):
        """
        Monitor a given transaction ID. Returns a Deferred that fires when the transaction is present.
        """
        monitor_deferred = Deferred()
        self.monitored_transactions[txid] = monitor_deferred
        return monitor_deferred

    def get_address(self):
        if not self.created:
            return None
        return self.wallet.get_receiving_address()

    def get_transactions(self):
        # TODO(Martijn): We should probably reload the storage/wallet...
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
