"""
This twistd plugin enables to start Tribler headless using the twistd command.
"""
import os
import signal

from Tribler.Core.Config.tribler_config import TriblerConfig
from twisted.application.service import MultiService, IServiceMaker
from twisted.conch import manhole_tap
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg
from zope.interface import implements

from Tribler.Core.Session import Session

# Register yappi profiler
from Tribler.dispersy.utils import twistd_yappi


class Options(usage.Options):
    optParameters = [
        ["manhole", "m", 0, "Enable manhole telnet service listening at the specified port", int],
        ["statedir", "s", None, "Use an alternate statedir", str],
        ["restapi", "p", 8085, "Use an alternate port for the REST API", int],
        ["ipv8", "d", -1, "Use an alternate port for IPv8", int],
    ]


class MarketServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "market"
    description = "Run a liteweight Tribler with the Market community"
    options = Options

    def __init__(self):
        self.session = None
        self._stopping = False
        self.market_community = None

    def shutdown_process(self, shutdown_message, code=1):
        msg(shutdown_message)
        reactor.addSystemEventTrigger('after', 'shutdown', os._exit, code)
        reactor.stop()

    def start_tribler(self, options):
        """
        Main method to startup Tribler.
        """
        def on_tribler_shutdown(_):
            msg("Tribler shut down")
            reactor.stop()

        def signal_handler(sig, _):
            msg("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                self.session.shutdown().addCallback(on_tribler_shutdown)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        config = TriblerConfig()
        config.set_torrent_checking_enabled(False)
        config.set_megacache_enabled(True)
        config.set_dispersy_enabled(False)
        config.set_mainline_dht_enabled(True)
        config.set_torrent_collecting_enabled(False)
        config.set_libtorrent_enabled(False)
        config.set_http_api_enabled(True)
        config.set_video_server_enabled(False)
        config.set_torrent_search_enabled(False)
        config.set_channel_search_enabled(False)

        msg("Starting Tribler")

        if options["statedir"]:
            config.set_state_dir(options["statedir"])

        if options["restapi"] > 0:
            config.set_http_api_enabled(True)
            config.set_http_api_port(options["restapi"])

        if options["ipv8"] != -1 and options["ipv8"] > 0:
            config.set_dispersy_port(options["ipv8"])

        self.session = Session(config)
        self.session.start().addErrback(lambda failure: self.shutdown_process(failure.getErrorMessage()))
        msg("Tribler started")

    def makeService(self, options):
        """
        Construct a Tribler service.
        """
        tribler_service = MultiService()
        tribler_service.setName("Market")

        manhole_namespace = {}
        if options["manhole"] > 0:
            port = options["manhole"]
            manhole = manhole_tap.makeService({
                'namespace': manhole_namespace,
                'telnetPort': 'tcp:%d:interface=127.0.0.1' % port,
                'sshPort': None,
                'passwd': os.path.join(os.path.dirname(__file__), 'passwd'),
            })
            tribler_service.addService(manhole)

        reactor.callWhenRunning(self.start_tribler, options)

        return tribler_service

service_maker = MarketServiceMaker()
