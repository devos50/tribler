from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path
from TriblerGUI.widgets.TransactionWidgetItem import TransactionWidgetItem


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
            self.window().core_manager.events_manager.market_payment_received.connect(self.on_payment_received)
            self.window().core_manager.events_manager.market_payment_sent.connect(self.on_payment_sent)

            self.window().transactions_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.initialized = True

        self.load_transactions()

    def load_transactions(self):
        self.window().market_transactions_list.clear()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/transactions", self.on_received_transactions)

    def on_payment_received(self, payment):
        print "received"
        print payment

    def on_payment_sent(self, payment):
        print "sent"
        print payment

    def on_received_transactions(self, transactions):
        for transaction in transactions["transactions"]:
            item = TransactionWidgetItem(self.window().market_transactions_list, transaction)
            item.update_item()
            self.window().market_transactions_list.addTopLevelItem(item)
