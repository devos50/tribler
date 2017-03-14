from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import PAGE_WALLET_NONE, PAGE_WALLET_BTC, PAGE_WALLET_MC
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class MarketWalletsPage(QWidget):
    """
    This page displays information about wallets.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.request_mgr = None
        self.initialized = False

    def initialize_wallets_page(self):
        if not self.initialized:
            self.window().wallets_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.window().wallets_stacked_widget.setCurrentIndex(PAGE_WALLET_NONE)
            self.window().wallet_btc_overview_button.clicked.connect(self.on_btc_wallet_clicked)
            self.window().wallet_mc_overview_button.clicked.connect(self.on_mc_wallet_clicked)
            self.initialized = True

    def on_btc_wallet_clicked(self):
        self.window().wallets_stacked_widget.setCurrentIndex(PAGE_WALLET_BTC)
        self.load_btc_wallet_balance()

    def on_mc_wallet_clicked(self):
        self.window().wallets_stacked_widget.setCurrentIndex(PAGE_WALLET_MC)
        self.load_mc_wallet_balance()

    def load_btc_wallet_balance(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets/btc/balance", self.on_btc_wallet_balance)

    def on_btc_wallet_balance(self, balance):
        self.window().btc_wallet_confirmed_label.setText("%s" % balance["balance"]["confirmed"])
        self.window().btc_wallet_unconfirmed_label.setText("%s" % balance["balance"]["unconfirmed"])
        self.window().btc_wallet_unmatured_label.setText("%s" % balance["balance"]["unmatured"])

    def load_mc_wallet_balance(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets/mc/balance", self.on_mc_wallet_balance)

    def on_mc_wallet_balance(self, balance):
        self.window().mc_wallet_given_label.setText("%s" % balance["balance"]["total_up"])
        self.window().mc_wallet_taken_label.setText("%s" % balance["balance"]["total_down"])
        self.window().mc_wallet_balance_label.setText("%s" % balance["balance"]["net"])
