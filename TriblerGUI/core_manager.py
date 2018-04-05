import subprocess

import sys
from twisted.internet.error import ReactorAlreadyInstalledError

# We always use a selectreactor
try:
    from twisted.internet import selectreactor
    selectreactor.install()
except ReactorAlreadyInstalledError:
    pass

import os
from PyQt5.QtCore import QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication

from TriblerGUI.event_request_manager import EventRequestManager
from TriblerGUI.tribler_request_manager import TriblerRequestManager, QueuePriorityEnum
from TriblerGUI.utilities import get_base_path, is_frozen

START_FAKE_API = False


class CoreManager(QObject):
    """
    The CoreManager is responsible for managing the Tribler core (starting/stopping). When we are running the GUI tests,
    a fake API will be started.
    """
    tribler_stopped = pyqtSignal()
    core_state_update = pyqtSignal(str)

    def __init__(self, api_port):
        QObject.__init__(self, None)

        self.base_path = get_base_path()
        if not is_frozen():
            self.base_path = os.path.join(get_base_path(), "..")

        self.request_mgr = None
        self.core_process = None
        self.api_port = api_port
        self.events_manager = EventRequestManager(self.api_port)

        self.shutting_down = False
        self.recorded_stderr = ""
        self.use_existing_core = True

        self.stop_timer = QTimer()
        self.stop_timer.timeout.connect(self.check_stopped)

        self.check_state_timer = QTimer()

    def check_stopped(self):
        if self.core_process.poll():
            self.stop_timer.stop()
            self.on_finished()

    def start(self):
        """
        First test whether we already have a Tribler process listening on port 8085. If so, use that one and don't
        start a new, fresh session.
        """
        def on_request_error(_):
            self.use_existing_core = False
            self.start_tribler_core()

        self.events_manager.connect(reschedule_on_err=False)
        self.events_manager.reply.error.connect(on_request_error)

    def start_tribler_core(self):
        if not START_FAKE_API:
            custom_env = os.environ.copy()
            custom_env["CORE_PROCESS"] = "1"
            custom_env["CORE_BASE_PATH"] = self.base_path
            custom_env["CORE_API_PORT"] = "%s" % self.api_port
            self.core_process = subprocess.Popen([sys.executable] + sys.argv, env=custom_env)

        self.check_core_ready()

    def check_core_ready(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("state", self.on_received_state, capture_errors=False,
                                         priority=QueuePriorityEnum.CRITICAL)

    def on_received_state(self, state):
        if not state or state['state'] not in ['STARTED', 'EXCEPTION']:
            self.check_state_timer = QTimer()
            self.check_state_timer.setSingleShot(True)
            self.check_state_timer.timeout.connect(self.check_core_ready)
            self.check_state_timer.start(50)
            return

        self.core_state_update.emit(state['readable_state'])

        if state['state'] == 'STARTED':
            self.events_manager.connect(reschedule_on_err=False)
        elif state['state'] == 'EXCEPTION':
            raise RuntimeError(state['last_exception'])

    def stop(self, stop_app_on_shutdown=True):
        if self.core_process:
            self.events_manager.shutting_down = True
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("shutdown", lambda _: None, method="PUT",
                                             priority=QueuePriorityEnum.CRITICAL)

            if stop_app_on_shutdown:
                self.stop_timer.start(100)

    def throw_core_exception(self):
        raise RuntimeError(self.recorded_stderr)

    def on_finished(self):
        self.tribler_stopped.emit()
        if self.shutting_down:
            QApplication.quit()
