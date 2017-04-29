import datetime
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


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
            self.initialized = True

        self.load_orders()

    def load_orders(self):
        self.window().market_orders_list.clear()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/orders", self.on_received_orders)

    def on_received_orders(self, orders):
        for order in orders["orders"]:
            order_time = datetime.datetime.fromtimestamp(int(order["timestamp"])).strftime('%Y-%m-%d %H:%M:%S')

            item = QTreeWidgetItem(self.window().market_orders_list)
            item.setText(0, "%s" % order["order_number"])
            item.setText(1, order_time)
            item.setText(2, "%g %s" % (order["price"], order["price_type"]))
            item.setText(3, "%g %s" % (order["quantity"], order["quantity_type"]))
            item.setText(4, "Sell" if order["is_ask"] else "Buy")
            item.setText(5, "Yes" if order["completed_timestamp"] else "No")
            self.window().market_orders_list.addTopLevelItem(item)
