import code
import io
import os

import sys
from PyQt5.QtCore import QEvent
from TriblerGUI.single_application import QtSingleApplication

# So it is included inside the frozen environment
from PyQt5.QtTest import QTest


class Stream(object):
    def __init__(self):
        self.stream = io.BytesIO()

    def read(self, *args, **kwargs):
        result = self.stream.read(*args, **kwargs)
        self.stream = io.BytesIO(self.stream.read())

        return result

    def write(self, *args, **kwargs):
        p = self.stream.tell()
        self.stream.seek(0, io.SEEK_END)
        result = self.stream.write(*args, **kwargs)
        self.stream.seek(p)

        return result


class Console(object):
    def __init__(self, locals=None):
        self.console = code.InteractiveConsole(locals=locals)

        self.stdout = Stream()
        self.stderr = Stream()

    def runcode(self, *args, **kwargs):
        stdout = sys.stdout
        sys.stdout = self.stdout

        stderr = sys.stderr
        sys.stderr = self.stderr

        result = None
        try:
            result = self.console.runcode(*args, **kwargs)
        except SyntaxError:
            self.console.showsyntaxerror()
        except:
            self.console.showtraceback()

        sys.stdout = stdout

        sys.stderr = stderr

        return result

    def execute(self, command):
        return self.runcode(code.compile_command(command))


class TriblerApplication(QtSingleApplication):
    """
    This class represents the main Tribler application.
    """
    def __init__(self, app_name, args):
        QtSingleApplication.__init__(self, app_name, args)
        self.messageReceived.connect(self.on_app_message)
        self.shell = None
        self.code_queue = []
        self.code_running = False

    def on_app_message(self, msg):
        if msg.startswith('file') or msg.startswith('magnet') or msg.startswith('code'):
            self.handle_uri(msg)

    def run_code(self, uri):
        # Read the python file and execute its code
        self.code_running = True
        file_path = uri[5:]
        with open(file_path, "r") as code_file:
            code = code_file.read()
            output = self.shell.runcode(code)
            self.code_running = False
            stdout = self.shell.stdout.read()
            stderr = self.shell.stderr.read()

            print "Script %s finished:" % str(file_path)
            print "STDOUT: %s" % stdout

            if ('Traceback' in stderr or 'SyntaxError' in stderr) and not 'SystemExit' in stderr:
                # Error during the script - crash tribler
                raise RuntimeError("Error during remote script execution! %s" % stderr)
            elif self.code_queue:
                uri = self.code_queue.pop(0)
                self.run_code(uri)

    def handle_uri(self, uri):
        if uri.startswith('code'):
            if not self.shell:
                variables = globals().copy()
                variables.update(locals())
                variables['window'] = self.activation_window()
                self.shell = Console(locals=variables)

            # Check if code is running or not
            if not self.code_running:
                self.run_code(uri)
            else:
                # Just add it to the queue
                self.code_queue.append(uri)
        else:
            self.activation_window().pending_uri_requests.append(uri)
            if self.activation_window().tribler_started and not self.activation_window().start_download_dialog_active:
                self.activation_window().process_uri_request()

    def parse_sys_args(self, args):
        for arg in args[1:]:
            if os.path.exists(arg):
                self.handle_uri('file:%s' % arg)
            elif arg.startswith('magnet'):
                self.handle_uri(arg)

    def event(self, event):
        if event.type() == QEvent.FileOpen and event.file().endswith(".torrent"):
            self.handle_uri('file:%s' % event.file())
        return QtSingleApplication.event(self, event)
