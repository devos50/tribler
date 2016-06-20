import sys
from PyQt5.QtCore import QProcess, QProcessEnvironment

from TriblerGUI.event_request_manager import EventRequestManager


class CoreManager(object):

    def __init__(self):
        self.core_process = QProcess()

    def start(self):
        self.core_process.readyReadStandardOutput.connect(self.on_ready_read_stdout)
        self.core_process.readyReadStandardError.connect(self.on_ready_read_stderr)
        self.core_process.start("python scripts/start_core.py -n tribler")

        self.events_manager = EventRequestManager()
        self.events_manager.connect()

    def stop(self):
        self.core_process.terminate()
        self.core_process.waitForFinished()

    def kill(self):
        self.core_process.kill()

    def on_ready_read_stdout(self):
        print "Tribler core: %s" % str(self.core_process.readAllStandardOutput()).rstrip()

    def on_ready_read_stderr(self):
        sys.stderr.write(self.core_process.readAllStandardError())
        sys.stderr.flush()
