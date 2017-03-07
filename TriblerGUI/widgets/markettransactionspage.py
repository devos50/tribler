import hashlib

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class MarketTransactionsPage(QWidget):
    """
    This page displays the past transactions on the decentralized market in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.request_mgr = None
        self.initialized = False

    def initialize_transactions_page(self):
        if not self.initialized:
            self.window().transactions_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.initialized = True

        self.load_transactions()

    def load_transactions(self):
        self.window().market_transactions_list.clear()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/transactions", self.on_received_transactions)

    def on_received_transactions(self, transactions):
        for transaction in transactions["transactions"]:
            item = QTreeWidgetItem(self.window().market_transactions_list)
            item.setText(0, transaction["timestamp"])
            item.setText(1, transaction["trader_id"])
            item.setText(2, transaction["price"])
            item.setText(3, "%d" % transaction["quantity"])
            item.setText(4, "%s" % ("yes" if transaction["payment_complete"] else "no"))
            self.window().market_transactions_list.addTopLevelItem(item)
