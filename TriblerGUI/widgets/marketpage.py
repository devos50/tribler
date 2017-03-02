from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager


class MarketPage(QWidget):
    """
    This page displays the decentralized market in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.statistics = None
        self.request_mgr = None

    def initialize_market_page(self, statistics):
        self.statistics = statistics
        net_score = int(self.statistics["self_total_up_mb"]) - int(self.statistics["self_total_down_mb"])
        self.window().net_score_label.setText("%d" % net_score)
        self.load_wallet_balance()

    def load_wallet_balance(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallet/balance", self.received_wallet_balance)

    def received_wallet_balance(self, balance):
        balance = balance["balance"]
        self.window().btc_amount_label.setText("%s" % balance["confirmed"])
