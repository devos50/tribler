import os
import sys
import logging.config

import signal

from TriblerGUI.utilities import get_base_path
from check_os import check_environment, check_free_space, error_and_exit, setup_gui_logging, \
    should_kill_other_tribler_instances, enable_fault_handler, set_process_priority


# https://github.com/Tribler/tribler/issues/3702
# We need to make sure that anyone running cp65001 can print to the stdout before we print anything.
# Annoyingly cp65001 is not shipped by default, so we add support for it through mapping it to mbcs.
if getattr(sys.stdout, 'encoding', None) == 'cp65001':
    import codecs

    def remapped_mbcs(_):
        mbcs_codec = codecs.lookup('mbcs')
        return codecs.CodecInfo(
            name='cp65001',
            encode=mbcs_codec.encode,
            decode=mbcs_codec.decode,
            incrementalencoder=mbcs_codec.incrementalencoder,
            incrementaldecoder=mbcs_codec.incrementaldecoder,
            streamreader=mbcs_codec.streamreader,
            streamwriter=mbcs_codec.streamwriter,
        )

    codecs.register(remapped_mbcs)


def start_tribler_core(base_path, api_port):
    """
    This method will start a new Tribler session.
    Note that there is no direct communication between the GUI process and the core: all communication is performed
    through the HTTP API.
    """
    from twisted.internet import reactor
    from check_os import setup_core_logging
    setup_core_logging()

    from Tribler.Core.Config.tribler_config import TriblerConfig
    from Tribler.Core.Modules.process_checker import ProcessChecker
    from Tribler.Core.Session import Session

    def on_tribler_shutdown(_):
        reactor.stop()

    def shutdown(session, *_):
        logging.info("Stopping Tribler core")
        session.shutdown().addCallback(on_tribler_shutdown)

    sys.path.insert(0, base_path)

    def start_tribler():
        config = TriblerConfig()

        priority_order = config.get_cpu_priority_order()
        set_process_priority(pid=os.getpid(), priority_order=priority_order)

        config.set_http_api_port(int(api_port))
        config.set_http_api_enabled(True)

        # Check if we are already running a Tribler instance
        process_checker = ProcessChecker(config.get_state_dir())
        if process_checker.already_running:
            return
        else:
            process_checker.create_lock_file()

        session = Session(config)

        signal.signal(signal.SIGTERM, lambda signum, stack: shutdown(session, signum, stack))
        if '--headless' in sys.argv:
            # In headless mode, we directly invoke the shutdown here.
            # If not in headless mode, TriblerWindow handles the SIGINT.
            signal.signal(signal.SIGINT, lambda signum, stack: shutdown(session, signum, stack))

        session.start()

    reactor.callWhenRunning(start_tribler)
    reactor.run()


if __name__ == "__main__":
    if '--headless' in sys.argv:
        start_tribler_core(get_base_path(), 8085)

    # Check whether we need to start the core or the user interface
    elif 'CORE_PROCESS' in os.environ:
        base_path = os.environ['CORE_BASE_PATH']
        api_port = os.environ['CORE_API_PORT']
        start_tribler_core(base_path, api_port)
    else:
        enable_fault_handler()

        # Exit if we cant read/write files, etc.
        check_environment()

        should_kill_other_tribler_instances()

        check_free_space()

        # Set up logging
        setup_gui_logging()

        try:
            from TriblerGUI.tribler_app import TriblerApplication
            from TriblerGUI.tribler_window import TriblerWindow

            app = TriblerApplication("triblerapp", sys.argv)

            if app.is_running():
                for arg in sys.argv[1:]:
                    if os.path.exists(arg) and arg.endswith(".torrent"):
                        app.send_message("file:%s" % arg)
                    elif arg.startswith('magnet'):
                        app.send_message(arg)
                sys.exit(1)

            window = TriblerWindow()
            window.setWindowTitle("Tribler")
            app.set_activation_window(window)
            app.parse_sys_args(sys.argv)
            sys.exit(app.exec_())
        except ImportError as ie:
            logging.exception(ie)
            error_and_exit("Import Error", "Import error: {0}".format(ie))

        except SystemExit as se:
            logging.info("Shutting down Tribler")
            # Flush all the logs to make sure it is written to file before it exits
            for handler in logging.getLogger().handlers:
                handler.flush()
            raise
