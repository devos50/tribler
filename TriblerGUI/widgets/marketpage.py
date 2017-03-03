import hashlib

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.widgets.tickwidgetitem import TickWidgetItem


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

        self.window().core_manager.events_manager.received_market_ask.connect(self.on_ask)
        self.window().core_manager.events_manager.received_market_bid.connect(self.on_bid)

        # Sort asks ascending and bids descending
        self.window().asks_list.sortItems(2, Qt.AscendingOrder)
        self.window().bids_list.sortItems(2, Qt.DescendingOrder)

        self.window().asks_list.itemSelectionChanged.connect(
            lambda: self.on_tick_item_clicked(self.window().asks_list))
        self.window().bids_list.itemSelectionChanged.connect(
            lambda: self.on_tick_item_clicked(self.window().bids_list))

        self.window().tick_detail_container.hide()

        self.load_wallet_balance()

    def load_wallet_balance(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallet/balance", self.on_wallet_balance)

    def on_wallet_balance(self, balance):
        balance = balance["balance"]
        self.window().btc_amount_label.setText("%s" % balance["confirmed"])
        self.load_asks()

    def create_widget_item_from_tick(self, tick_list, tick, is_ask=True):
        tick["type"] = "ask" if is_ask else "bid"
        item = TickWidgetItem(tick_list, tick)
        item.setText(0, hashlib.sha1(tick["trader_id"]).hexdigest()[:10])
        item.setText(1, "%d" % tick["quantity"])
        item.setText(2, tick["price"])
        return item

    def load_asks(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/asks", self.on_received_asks)

    def on_received_asks(self, asks):
        self.window().asks_list.clear()
        for ask in asks["asks"]:
            self.window().asks_list.addTopLevelItem(
                self.create_widget_item_from_tick(self.window().asks_list, ask, is_ask=True))
        self.load_bids()

    def load_bids(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/bids", self.on_received_bids)

    def on_received_bids(self, bids):
        self.window().bids_list.clear()
        for bid in bids["bids"]:
            self.window().bids_list.addTopLevelItem(
                self.create_widget_item_from_tick(self.window().bids_list, bid, is_ask=False))

    def on_ask(self, ask):
        self.window().asks_list.addTopLevelItem(
            self.create_widget_item_from_tick(self.window().asks_list, ask, is_ask=True))

    def on_bid(self, bid):
        self.window().bids_list.addTopLevelItem(
            self.create_widget_item_from_tick(self.window().bids_list, bid, is_ask=False))

    def on_tick_item_clicked(self, tick_list):
        if len(tick_list.selectedItems()) == 0:
            return
        tick = tick_list.selectedItems()[0].tick

        self.window().market_detail_order_id_label.setText(
            hashlib.sha1(tick["trader_id"] + tick["order_id"]).hexdigest())
        self.window().market_detail_trader_id_label.setText(hashlib.sha1(tick["trader_id"]).hexdigest())
        self.window().market_detail_credits_label.setText("%d" % tick["quantity"])
        self.window().market_detail_price_label.setText(tick["price"])
        self.window().market_detail_time_created_label.setText(tick["timestamp"])

        self.window().tick_detail_container.show()
