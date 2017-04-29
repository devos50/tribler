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
            self.window().core_manager.events_manager.market_payment_received.connect(self.on_payment)
            self.window().core_manager.events_manager.market_payment_sent.connect(self.on_payment)

            self.window().transactions_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.initialized = True

        self.load_transactions()

    def load_transactions(self):
        self.window().market_transactions_list.clear()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/transactions", self.on_received_transactions)

    def get_widget_with_transaction(self, trader_id, transaction_number):
        for i in range(self.window().market_transactions_list.topLevelItemCount()):
            item = self.window().market_transactions_list.topLevelItem(i)
            if item.transaction["trader_id"] == trader_id and item.transaction["transaction_number"] == transaction_number:
                return item

    def on_payment(self, payment):
        item = self.get_widget_with_transaction(payment["trader_id"], payment["transaction_number"])
        if item:
            item.transaction["current_payment"] += 1
            item.update_item()

    def on_received_transactions(self, transactions):
        for transaction in transactions["transactions"]:
            item = TransactionWidgetItem(self.window().market_transactions_list, transaction)
            item.update_item()
            self.window().market_transactions_list.addTopLevelItem(item)
