import os
import sys
import unittest
from bisect import bisect
from random import choice, random, randint

import logging
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from Tribler.Core.Utilities.network_utils import get_random_port
from TriblerGUI.defs import PAGE_DOWNLOADS
from TriblerGUI.tribler_request_manager import TriblerRequestManager

rand_port = get_random_port()


from TriblerGUI.tribler_window import TriblerWindow

app = QApplication(sys.argv)
window = TriblerWindow()
QTest.qWaitForWindowExposed(window)

sys.excepthook = sys.__excepthook__


class TimeoutException(Exception):
    pass


search_keywords = ['search', 'vodo', 'eztv', 'big buck bunny', 'windows', 'debian', 'linux', '2012', 'pioneer',
                   'tribler', 'test', 'free music', 'free video', '2016', 'whatsapp', 'ebooks', 'race', 'funny']
torrent_limit = 20  # How many concurrent torrents we can download


class AbstractTriblerGUITest(unittest.TestCase):
    """
    This class contains various utility methods that are used during the GUI test.
    """

    def get_attr_recursive(self, attr_name):
        parts = attr_name.split(".")
        cur_attr = window
        for part in parts:
            cur_attr = getattr(cur_attr, part)
        return cur_attr

    def wait_for_variable(self, var, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if self.get_attr_recursive(var) is not None:
                return

        raise TimeoutException("Variable %s within 10 seconds" % var)

    def wait_for_signal(self, signal, timeout=10, no_args=False):
        self.signal_received = False

        def on_signal(_):
            self.signal_received = True

        if no_args:
            signal.connect(lambda: on_signal(None))
        else:
            signal.connect(on_signal)

        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if self.signal_received:
                return

        raise TimeoutException("Signal %s not raised within 10 seconds" % signal)

    def weighted_choice(self, choices):
        values, weights = zip(*choices)
        total = 0
        cum_weights = []
        for w in weights:
            total += w
            cum_weights.append(total)
        x = random() * total
        i = bisect(cum_weights, x)
        return values[i]

    def get_rand_bool(self):
        return randint(0, 1) == 0


class TriblerGUIApplicationTest(AbstractTriblerGUITest):

    def setUp(self):
        self.signal_received = None
        self.torrents = []
        self._logger = logging.getLogger(self.__class__.__name__)

        TriblerRequestManager.show_error = lambda *_: None  # Don't show an error during requests

        cur_dir = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
        with open(os.path.join(cur_dir, 'data', 'torrent_links.txt'), 'r') as torrents_file:
            lines = torrents_file.readlines()

        for torrent in lines:
            self.torrents.append(torrent.replace('\n', ''))

        if not window.tribler_started:
            self.wait_for_signal(window.core_manager.events_manager.tribler_started, no_args=True)

    def perform_random_action(self):
        """
        This method performs a random action in Tribler. There are various actions possible that can occur with
        different probabilities.
        """
        probs = [('random_page', 50), ('remote_search', 25), ('start_download', 20), ('stop_download', 5)]
        #probs = [('random_page', 100), ('remote_search', 0), ('start_download', 0), ('stop_download', 0)]
        action = self.weighted_choice(probs)
        self._logger.info("Performing action: %s", action)
        if action == 'random_page':
            self.move_to_page()
        elif action == 'remote_search':
            self.perform_remote_search()
        elif action == 'start_download':
            self.start_download()
        elif action == 'stop_download':
            self.stop_download()

    def move_to_page(self):
        # For now, we just move to a random page
        page_buttons = window.menu_buttons + [window.trust_button, window.settings_button]
        selected_button = choice(page_buttons)
        #selected_button = window.left_menu_button_discovered
        QTest.mouseClick(selected_button, Qt.LeftButton)

        QTest.qWait(1000)
        if selected_button == window.settings_button:
            # Jump to a random tab
            setting_buttons = [window.settings_general_button, window.settings_connection_button,
                               window.settings_bandwidth_button, window.settings_seeding_button,
                               window.settings_anonymity_button]
            random_settings_button = choice(setting_buttons)
            QTest.mouseClick(random_settings_button, Qt.LeftButton)
        elif selected_button == window.left_menu_button_discovered:
            # Click on a random channel and go back
            rand_ind = min(5, randint(0, window.discovered_channels_list.count() - 1))
            item = window.discovered_channels_list.item(rand_ind)
            item_widget = window.discovered_channels_list.itemWidget(item)
            QTest.mouseClick(item_widget, Qt.LeftButton)
            QTest.qWait(2000)
            QTest.mouseClick(window.channel_back_button, Qt.LeftButton)
        elif selected_button == window.left_menu_button_downloads:
            # Click a random download or move between tabs
            click_download = self.get_rand_bool()
            if click_download:
                if len(window.downloads_page.downloads['downloads']) == 0:
                    return

                rand_ind = randint(0, len(window.downloads_page.download_widgets.keys()) - 1)
                QTest.mouseClick(window.downloads_list.topLevelItem(rand_ind).progress_slider, Qt.LeftButton)
                window.download_details_widget.setCurrentIndex(randint(0, 3))
            else:
                download_tabs = [window.downloads_all_button, window.downloads_downloading_button,
                                 window.downloads_completed_button, window.downloads_active_button,
                                 window.downloads_inactive_button]
                rand_button = choice(download_tabs)
                QTest.mouseClick(rand_button, Qt.LeftButton)
                QTest.qWait(2000)
                QTest.mouseClick(window.downloads_all_button, Qt.LeftButton)

    def perform_remote_search(self):
        search_query = choice(search_keywords)
        window.top_search_bar.setText('')
        QTest.mouseClick(window.top_search_bar, Qt.LeftButton)
        QTest.keyClicks(window.top_search_bar, search_query, delay=400)
        QTest.keyClick(window.top_search_bar, Qt.Key_Enter)

    def start_download(self):
        if len(window.downloads_page.downloads['downloads']) == torrent_limit:
            return

        rand_download = choice(self.torrents)
        window.on_add_torrent_from_url()
        QTest.qWait(1000)
        window.dialog.dialog_widget.dialog_input.setText(rand_download)
        QTest.qWait(1000)
        QTest.mouseClick(window.dialog.buttons[0], Qt.LeftButton)
        QTest.qWait(1000)

        # Decide whether we want anonymity or not
        anon_enabled = self.get_rand_bool()
        if anon_enabled:
            if not window.dialog.dialog_widget.anon_download_checkbox.isChecked():
                QTest.mouseClick(window.dialog.dialog_widget.anon_download_checkbox, Qt.LeftButton)
        else:
            if window.dialog.dialog_widget.anon_download_checkbox.isChecked():
                QTest.mouseClick(window.dialog.dialog_widget.anon_download_checkbox, Qt.LeftButton)

            anon_seeding = self.get_rand_bool()
            if anon_seeding:
                if not window.dialog.dialog_widget.safe_seed_checkbox.isChecked():
                    QTest.mouseClick(window.dialog.dialog_widget.safe_seed_checkbox, Qt.LeftButton)
            else:
                if window.dialog.dialog_widget.safe_seed_checkbox.isChecked():
                    QTest.mouseClick(window.dialog.dialog_widget.safe_seed_checkbox, Qt.LeftButton)

        QTest.qWait(10000)
        QTest.mouseClick(window.dialog.dialog_widget.download_button, Qt.LeftButton)

        QTest.qWait(2000)
        if window.dialog:  # Download already exists
            QTest.mouseClick(window.dialog.buttons[0], Qt.LeftButton)

    def stop_download(self):
        if len(window.downloads_page.downloads['downloads']) == 0:
            return

        QTest.mouseClick(window.left_menu_button_downloads, Qt.LeftButton)
        QTest.qWait(1000)

        rand_ind = randint(0, len(window.downloads_page.download_widgets.keys()) - 1)
        QTest.mouseClick(window.downloads_list.topLevelItem(rand_ind).progress_slider, Qt.LeftButton)
        QTest.mouseClick(window.remove_download_button, Qt.LeftButton)
        QTest.mouseClick(window.downloads_page.dialog.buttons[1], Qt.LeftButton)

    def test_tribler(self):
        QTest.qWait(2000)
        while True:
            self.perform_random_action()
            QTest.qWait(10000)
