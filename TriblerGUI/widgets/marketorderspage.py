import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path
from TriblerGUI.widgets.orderwidgetitem import OrderWidgetItem


class MarketOrdersPage(QWidget):
    """
    This page displays orders in the decentralized market in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.request_mgr = None
        self.initialized = False

    def initialize_orders_page(self):
        if not self.initialized:
            self.window().orders_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.window().market_orders_list.sortItems(0, Qt.AscendingOrder)
            self.initialized = True

        self.load_orders()

    def load_orders(self):
        self.window().market_orders_list.clear()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/orders", self.on_received_orders)

    def on_received_orders(self, orders):
        for order in orders["orders"]:
            item = OrderWidgetItem(self.window().market_orders_list, order)
            self.window().market_orders_list.addTopLevelItem(item)
