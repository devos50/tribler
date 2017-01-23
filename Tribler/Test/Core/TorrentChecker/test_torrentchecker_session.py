import os
import struct
from libtorrent import bencode

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks
from twisted.internet.task import Clock, deferLater
from twisted.python.failure import Failure

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentChecker.session import FakeDHTSession, DHT_TRACKER_MAX_RETRIES, DHT_TRACKER_RECHECK_INTERVAL, \
    UdpTrackerSession, UDPScraper, HttpTrackerSession, create_tracker_session
from Tribler.Test.twisted_thread import deferred
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class ClockedUDPCrawler(UDPScraper):
    _reactor = Clock()


class FakeScraper(object):
    def write_data(self, _):
        pass

    def stop(self):
        pass


class TestTorrentCheckerSession(TriblerCoreTest):

    def setUp(self, annotate=True):
        super(TestTorrentCheckerSession, self).setUp(annotate=annotate)
        self.mock_transport = MockObject()
        self.mock_transport.write = lambda *_: None

    def test_httpsession_scrape_no_body(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._process_scrape_response(None)
        session._infohash_list = []
        self.assertTrue(session.is_failed)

    def test_httpsession_bdecode_fails(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._infohash_list = []
        session._process_scrape_response("test")
        self.assertTrue(session.is_failed)

    @deferred(timeout=5)
    def test_httpsession_on_error(self):
        test_deferred = Deferred()
        session = HttpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.result_deferred = Deferred().addErrback(lambda failure: test_deferred.callback(None))
        session.on_error(Failure(RuntimeError(u"test\xf8\xf9")))
        return test_deferred

    def test_httpsession_code_not_200(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)

        class FakeResponse(object):
            code = 201
            phrase = "unit testing!"

        session.on_response(FakeResponse())
        self.assertTrue(session.is_failed)

    def test_httpsession_failure_reason_in_dict(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        session._infohash_list = []
        session._process_scrape_response(bencode({'failure reason': 'test'}))
        self.assertTrue(session.is_failed)

    @deferred(timeout=5)
    def test_httpsession_unicode_err(self):
        session = HttpTrackerSession("retracker.local", ("retracker.local", 80),
                                     u"/announce?comment=%26%23%3B%28%2C%29%5B%5D%E3%5B%D4%E8%EB%FC%EC%EE%E2", 5)

        test_deferred = Deferred()

        def on_error(failure):
            failure.trap(UnicodeEncodeError)
            self.assertTrue(isinstance(failure.value, UnicodeEncodeError))
            test_deferred.callback(None)

        session.connect_to_tracker().addErrback(on_error)
        return test_deferred

    @deferred(timeout=5)
    def test_httpsession_cancel_operation(self):
        test_deferred = Deferred()
        session = HttpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5)
        session.result_deferred = Deferred(session._on_cancel)
        session.result_deferred.addErrback(lambda _: test_deferred.callback(None))
        session.result_deferred.cancel()
        return test_deferred

    @deferred(timeout=5)
    def test_udpsession_cancel_operation(self):
        session = UdpTrackerSession("127.0.0.1", ("localhost", 8475), "/announce", 5)
        d = Deferred(session._on_cancel)
        d.addErrback(lambda _: None)
        session.result_deferred = d
        return session.cleanup()

    def test_udpsession_udp_tracker_timeout(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = ClockedUDPCrawler(session, "127.0.0.1", 4782, 5)
        # Advance 16 seconds so the timeout triggered
        session.scraper._reactor.advance(session.scraper.timeout + 1)
        self.assertFalse(session.scraper.timeout_call.active(), "timeout was active while should've canceled")

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_udpsession_many_trackers(self):
        trackers = """udp://10.rarbg.com:80
udp://10.rarbg.me:80
udp://107.150.14.110:6969
udp://108.61.189.238:6969
udp://108.61.189.238:80
udp://109.121.134.121:1337
udp://109.201.133.19:2710
udp://11.rarbg.com:6969
udp://11.rarbg.com:80
udp://11.rarbg.me:6969
udp://11.rarbg.me:80
udp://11.rarbg.to:80
udp://12.rarbg.com:6969
udp://12.rarbg.com:80
udp://12.rarbg.me:6969
udp://12.rarbg.me:80
udp://121.14.98.151:9090
udp://128.199.70.66:5944
udp://15.rarbg.com:27015
udp://168.235.67.63:6969
udp://178.33.73.26:2710
udp://179.43.146.110:80
udp://182.176.139.122:6969
udp://184.105.214.73:6969
udp://185.86.149.205:1337
udp://192.121.121.30:6969
udp://192.121.121.30:80
udp://208.67.16.113:8000
udp://208.83.20.164:6969
udp://212.10.37.247:6969
udp://213.163.67.56:1337
udp://31.172.63.226:80
udp://31.172.63.252:80
udp://37.187.96.78:6969
udp://43.tracker.hexagon.cc:2710
udp://50.19.80.43:6969
udp://55.tracker.hexagon.cc:2710
udp://62.138.0.158:1337
udp://62.138.0.158:6969
udp://62.138.0.158:80
udp://62.210.137.203:1337
udp://62.212.85.66:2710
udp://69.tracker.hexagon.cc:2710
udp://74.82.52.209:6969
udp://85.25.208.201:6969
udp://9.rarbg.com:2710
udp://9.rarbg.com:2730
udp://9.rarbg.com:2750
udp://9.rarbg.com:2770
udp://9.rarbg.com:5764663
udp://9.rarbg.me:2710
udp://9.rarbg.me:2720
udp://9.rarbg.me:2730
udp://9.rarbg.me:2740
udp://9.rarbg.me:2750
udp://9.rarbg.me:2770
udp://9.rarbg.me:2790
udp://9.rarbg.me:2800
udp://9.rarbg.to:2710
udp://9.rarbg.to:2720
udp://9.rarbg.to:2730
udp://9.rarbg.to:2770
udp://9.rarbg.to:2780
udp://9.rarbg.to:2790
udp://9.rarbg.to:2800
udp://91.218.230.81:6969
udp://93.190.140.138:1337
udp://94.23.183.33:6969
udp://95.215.44.237:6969
udp://TRACKER.OPENBITTORRENT.COM:80
udp://TRACKER.PUBLICBT.COM:80
udp://a.leopard-raws.org:6969
udp://a.tv.tracker.prq.to:80
udp://a2.tracker.hexagon.cc:2710
udp://anisaishuu.de:2710
udp://armaggedon.tracker.prq.to:80
udp://atrack.pow7.com:80
udp://bigfoot1942.sektori.org:6969
udp://bt.btbbt.com:7272
udp://bt.btwuji.com:7979
udp://bt.careland.com.cn:6969
udp://bt.firebit.co.uk:6969
udp://bt.piratbit.net:80
udp://bt.rghost.net:80
udp://bt.rutor.org:2710
udp://bt.tgbus.com:6969
udp://bt.tgbus.com:8080
udp://bt.xxx-tracker.com:2710
udp://bt1.125a.net:6969
udp://bt1.btally.net:6969
udp://bt1.btally.net:8888
udp://bt2.careland.com.cn:6969
udp://bttrack.9you.com:80
udp://bttracker.crunchbanglinux.org:6969
udp://c6.tracker.hexagon.cc:2710
udp://castradio.net:6969
udp://cd.tracker.hexagon.cc:2710
udp://colombo-bt.org:2710
udp://concen.org:6969
udp://coppersurfer.tk:6969
udp://coppersurfer.tk:80
udp://crazy-torrent.com:80
udp://cstv.tv.tracker.prq.to:80
udp://da.tracker.hexagon.cc:2710
udp://denis.stalker.h3q.com:6969
udp://dioa.co.cc:6969
udp://eddie4.nl:6969
udp://entourage.publichd.org:6969
udp://exodus.desync.com:6969
udp://exodus.desync.com:80
udp://explodie.org:6969
udp://eztv.tracker.prq.to:80
udp://f0.tracker.hexagon.cc:2710
udp://fr33dom.h33t.com:3310
udp://fr33dom.h33t.eu:3310
udp://fr33domtracker.h33t.com:3310
udp://fr33domtracker.h33t.eu:3310
udp://free.btr.kz:8888
udp://genesis.1337x.org:1337
udp://genesis.1337x.org:80
udp://glotorrents.com:6969
udp://glotorrents.pw:6969
udp://hdreactor.org:2710
udp://inferno.demonoid.com:3389
udp://inferno.demonoid.com:3390
udp://inferno.demonoid.com:3391
udp://inferno.demonoid.com:3392
udp://inferno.demonoid.com:3393
udp://inferno.demonoid.com:3394
udp://inferno.demonoid.com:3395
udp://inferno.demonoid.com:3396
udp://inferno.demonoid.com:3397
udp://inferno.demonoid.com:3398
udp://inferno.demonoid.com:3399
udp://inferno.demonoid.com:3400
udp://inferno.demonoid.com:3401
udp://inferno.demonoid.com:3402
udp://inferno.demonoid.com:3403
udp://inferno.demonoid.com:3404
udp://inferno.demonoid.com:3405
udp://inferno.demonoid.com:3406
udp://inferno.demonoid.com:3407
udp://inferno.demonoid.com:3408
udp://inferno.demonoid.com:3409
udp://inferno.demonoid.com:3410
udp://inferno.demonoid.com:3411
udp://inferno.demonoid.com:3412
udp://inferno.demonoid.com:3413
udp://inferno.demonoid.com:3414
udp://inferno.demonoid.com:3415
udp://inferno.demonoid.com:3416
udp://inferno.demonoid.com:3417
udp://inferno.demonoid.com:3418
udp://inferno.demonoid.com:3419
udp://inferno.demonoid.com:80
udp://inferno.demonoid.ooo:3389
udp://inferno.demonoid.ooo:3392
udp://inferno.demonoid.ooo:3393
udp://inferno.demonoid.ph:3389
udp://inferno.demonoid.ph:3390
udp://inferno.demonoid.ph:3392
udp://inferno.demonoid.pw:3393
udp://inferno.demonoid.pw:3395
udp://inferno.subdemon.com:3395
udp://ipv4.tracker.harry.lu:6969
udp://ipv4.tracker.harry.lu:80
udp://ipv6.leechers-paradise.org:6969
udp://ipv6.tracker.harry.lu:80
udp://leechers-paradise.org:6969
udp://leopard.raws.ws:6969
udp://megapeer.org:6969
udp://mgtracker.org:2710
udp://mgtracker.org:6969
udp://mirror.strits.dk:6969
udp://mongo56.org:3939
udp://mongo56.org:4141
udp://mongo56.org:4646
udp://nyaatorrents.info:3277
udp://open.Demonii.com:1337
udp://open.dakutorrents.ch:1337
udp://open.demonii.com.prx.websiteproxy.co.uk:1337
udp://open.demonii.com:1337
udp://open.demonii.com:6969
udp://open.demonii.com:80
udp://open.facedatabg.net:6969
udp://open.nyaatorrents.info:6544
udp://open.stealth.si:80
udp://opentor.org:2710
udp://opentrackr.org:1337
udp://p2pdl.com:2710
udp://p4p.arenabg.ch:1337
udp://p4p.arenabg.com:1337
udp://photodiode.mine.nu:6969
udp://pi1.nl:8234
udp://poloniumsurfer.tk:6969
udp://pornleech.cc:2710
udp://pornleech.com:2710
udp://pornleech.me:2710
udp://pornleech.org:2710
udp://pornleech.ru:2710
udp://pow7.com:80
udp://public.popcorn-tracker.org:6969
udp://pubt.net:2710
udp://rarbg.me:2718
udp://red.tracker.prq.to:80
udp://retracker.hotplug.ru:2710
udp://retracker.telecom.kz:80
udp://rhodiumsurfer.tk:6969
udp://sawtooth.zapto.org:7070
udp://secure.pow7.com:80
udp://shadowshq.eddie4.nl:6969
udp://shadowshq.yi.org:6969
udp://share.dmhy.net:8000
udp://sneakybastard.zapto.org:6969
udp://snowy.arsc.alaska.edu:6969
udp://sub4all.org:2710
udp://sugoi.pomf.se:80
udp://t1.pow7.com:80
udp://t2.popgo.org:7456
udp://t2.pow7.com:80
udp://tbp.tracker.prq.to:80
udp://the.illusionist.tracker.prq.to:80
udp://the.last.samurai.tracker.tracker.prq.to:80
udp://thetracker.org:80
udp://tntvillage.org:2710
udp://torrent.gresille.org:80
udp://torrent.ubuntu.com:6969
udp://torrentbay.to:6969
udp://torrentforce.org:2710
udp://total.recall.tracker.prq.to:80
udp://tpb.tracker.prq.to:80
udp://tpb.tracker.thepiratebay.org:80
udp://track.nkw77.com:80
udp://tracker-ccc.de:6969
udp://tracker.1337x.org:80
udp://tracker.aletorrenty.pl:2710
udp://tracker.anime-miako.to:6969
udp://tracker.archlinux.org:6969
udp://tracker.beeimg.com:6969
udp://tracker.bitcomet.net:8080
udp://tracker.bitreactor.to:2710
udp://tracker.bittor.pw:1337
udp://tracker.bittorrent.am:80
udp://tracker.blackunicorn.xyz:6969
udp://tracker.blazing.de:6969
udp://tracker.blazing.de:80
udp://tracker.bluefrog.pw:2710
udp://tracker.btscene.eu:80
udp://tracker.btzoo.eu:80
udp://tracker.ccc.de:80
udp://tracker.ccc.se:80
udp://tracker.concen.cc:1984
udp://tracker.coppersurfer.tk.prx.websiteproxy.co.uk:6969
udp://tracker.coppersurfer.tk:1337
udp://tracker.coppersurfer.tk:6969
udp://tracker.coppersurfer.tk:80
udp://tracker.csze.com:80
udp://tracker.datorrents.com:6969
udp://tracker.dduniverse.net:6969
udp://tracker.dler.org:6969
udp://tracker.dmhy.org:8000
udp://tracker.eddie4.nl:6969
udp://tracker.edgebooster.com:6969
udp://tracker.ex.ua:80
udp://tracker.feednet.ro:80
udp://tracker.filetracker.pl:8089
udp://tracker.flashtorrents.org:6969
udp://tracker.freerainbowtables.com:7198
udp://tracker.glotorrents.com:6969
udp://tracker.grepler.com:6969
udp://tracker.heytracker.com:6969
udp://tracker.ilibr.org:6969
udp://tracker.ilibr.org:80
udp://tracker.internetwarriors.net:1337
udp://tracker.ipv6tracker.org:80
udp://tracker.irc.su:80
udp://tracker.istole.it.prx2.unblocksit.es:80
udp://tracker.istole.it:6969
udp://tracker.istole.it:80
udp://tracker.jamendo.com:80
udp://tracker.justseed.it:1337
udp://tracker.kali.org:6969
udp://tracker.kicks-ass.net:80
udp://tracker.ktxp.com:6868
udp://tracker.ktxp.com:7070
udp://tracker.kuroy.me:5944
udp://tracker.lamsoft.net:6969
udp://tracker.leechers-paradise.org:6969
udp://tracker.mg64.net:6969
udp://tracker.mytorrenttracker.com:6099
udp://tracker.novalayer.org:6969
udp://tracker.nwps.ws:6969
udp://tracker.openbittorrent.com:6969
udp://tracker.openbittorrent.com:80
udp://tracker.openbittorrent.kg:2710
udp://tracker.opentrackr.org:1337
udp://tracker.pirateparty.gr:6969
udp://tracker.piratepublic.com:1337
udp://tracker.piratkopiera.nu:80
udp://tracker.podtropolis.com:2711
udp://tracker.pomf.se:80
udp://tracker.pony.pp.ua:80
udp://tracker.pornoshara.tv:2711
udp://tracker.pow7.com:80
udp://tracker.prq.to.:80
udp://tracker.prq.to:80
udp://tracker.publicbt.com:6969
udp://tracker.publicbt.com:80
udp://tracker.publichash.org:6969
udp://tracker.publichd.eu:80
udp://tracker.pubt.net:2710
udp://tracker.secureboxes.net:80
udp://tracker.seedceo.com:2710
udp://tracker.seedceo.vn:2710
udp://tracker.sith.su:80
udp://tracker.sktorrent.net:6969
udp://tracker.teentorrent.com:7070
udp://tracker.teentorrent.net:7070
udp://tracker.thehashden.com:80
udp://tracker.thepiratebay.org:80
udp://tracker.thepornvilla.com:6969
udp://tracker.tntvillage.org:2710
udp://tracker.tntvillage.scambioetico.org:2710
udp://tracker.tntvillage.scambioetico.org:6969
udp://tracker.token.ro:6969
udp://tracker.token.ro:80
udp://tracker.tordb.ml:6881
udp://tracker.torrent.eu.org:451
udp://tracker.torrentbay.to:6969
udp://tracker.torrentbox.com:2710
udp://tracker.torrentparty.com:6969
udp://tracker.torrentula.se:6969
udp://tracker.torrrentbox.com:2710
udp://tracker.trackerfix.com:80
udp://tracker.trackerfix.com:82
udp://tracker.trackerfix.com:83
udp://tracker.tricitytorrents.com:2710
udp://tracker.vanitycore.co:6969
udp://tracker.viewcave.com:6969
udp://tracker.xelion.fr:6969
udp://tracker.xpear.de:6969
udp://tracker.yify-torrents.com:6969
udp://tracker.yify-torrents.com:80
udp://tracker.yoshi210.com:6969
udp://tracker.zer0day.to:1337
udp://tracker.zerotracker.com:2710
udp://tracker.zond.org:80
udp://tracker1.wasabii.com.tw:6969
udp://tracker2.indowebster.com:6969
udp://tracker2.istole.it:80
udp://tracker2.pony.pp.ua:80
udp://tracker2.pony.pp.ya:80
udp://tracker2.torrentbox.com:2710
udp://tracker4.piratux.com:6969
udp://trackr.sytes.net:80
udp://trackre.ohys.net:80
udp://trk.obtracker.net:2710
udp://tv.tracker.prq.to:80
udp://twig.gs:6969
udp://vip.tracker.prq.to:80
udp://vip.tracker.thepiratebay.org:80
udp://viv.tracker.prq.to:80
udp://viv.tv.tracker.prq.to:80
udp://vlv.tv.tracker.prq.to:80
udp://vtv.tracker.prq.to:80
udp://vtv.tv.tracker.prq.to:80
udp://wannasub.it:6969
udp://windtalkers.tracker.prq.to:80
udp://www.eddie4.nl:6969
udp://www.elitezones.ro:80
udp://www.h33t.com:3310
udp://www.lamsoft.net:6969
udp://www.mongo56.org:3434
udp://www.mongo56.org:3535
udp://www.warsow.be:6969
udp://xbt.torrents-nn.cn:2710
udp://zephir.monocul.us:6969
udp://zer0day.ch:1337
udp://zer0day.ch:1377
udp://zer0day.to:1337"""
        c = 0
        for tracker in trackers.split('\n'):
            print "Creating session for %s" % tracker
            session = create_tracker_session(tracker, 15)
            session.connect_to_tracker()
            yield deferLater(reactor, 5, lambda: None)
            c += 1

    @deferred(timeout=5)
    def test_udp_scraper_stop_no_connection(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        scraper = UDPScraper(session, "127.0.0.1", 4782, 5)
        # Stop it manually, so the transport becomes inactive
        stop_deferred = scraper.stop()

        return DeferredList([stop_deferred, session.cleanup()])

    @deferred(timeout=5)
    def test_udpsession_udp_tracker_connection_refused(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = UDPScraper(session, "127.0.0.1", 4782, 5)
        session.scraper.connectionRefused()
        self.assertTrue(session.is_failed, "Session did not fail while it should")
        return session.scraper.stop()

    def test_udpsession_handle_response_wrong_len(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.on_ip_address_resolved("127.0.0.1", start_scraper=False)
        self.assertFalse(session.is_failed)
        session.handle_connection_response("too short")
        self.assertTrue(session.is_failed)

    def test_udpsession_handle_connection_wrong_action_transaction(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.on_ip_address_resolved("127.0.0.1", start_scraper=None)
        self.assertFalse(session.is_failed)
        packet = struct.pack("!qq4s", 123, 123, "test")
        session.handle_connection_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_handle_packet(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        session._action = 123
        session._transaction_id = 124
        self.assertFalse(session.is_failed)
        packet = struct.pack("!iiq", 123, 124, 126)
        session.handle_connection_response(packet)
        self.assertFalse(session.is_failed)

    def test_udpsession_handle_wrong_action_transaction(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.on_ip_address_resolved("127.0.0.1", start_scraper=None)
        self.assertFalse(session.is_failed)
        packet = struct.pack("!qq4s", 123, 123, "test")
        session.handle_connection_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_mismatch(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        session._action = 123
        session._transaction_id = 124
        session._infohash_list = [1337]
        self.assertFalse(session.is_failed)
        packet = struct.pack("!ii", 123, 124)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_response_too_short(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!i", 123)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_response_wrong_transaction_id(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!ii", 0, 1337)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    def test_udpsession_response_list_len_mismatch(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.scraper = FakeScraper()
        session.result_deferred = Deferred()

        def on_error(_):
            pass

        session.result_deferred.addErrback(on_error)
        session._action = 123
        session._transaction_id = 123
        self.assertFalse(session.is_failed)
        session._infohash_list = ["test", "test2"]
        packet = struct.pack("!iiiii", 123, 123, 0, 1, 2)
        session.handle_response(packet)
        self.assertTrue(session.is_failed)

    @deferred(timeout=5)
    def test_udpsession_correct_handle(self):
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.on_ip_address_resolved("127.0.0.1", start_scraper=False)
        session.result_deferred = Deferred()
        self.assertFalse(session.is_failed)
        session._infohash_list = ["test"]
        packet = struct.pack("!iiiii", session._action, session._transaction_id, 0, 1, 2)
        session.handle_response(packet)

        return session.result_deferred.addCallback(lambda *_: session.cleanup())

    @deferred(timeout=5)
    def test_udpsession_on_error(self):
        test_deferred = Deferred()
        session = UdpTrackerSession("localhost", ("localhost", 4782), "/announce", 5)
        session.result_deferred = Deferred().addErrback(
            lambda failure: test_deferred.callback(failure.getErrorMessage()))
        session.scraper = FakeScraper()
        session.on_error(Failure(RuntimeError("test")))
        return test_deferred

    @deferred(timeout=5)
    def test_big_correct_run(self):
        session = UdpTrackerSession("localhost", ("192.168.1.1", 1234), "/announce", 1)
        session.on_ip_address_resolved("192.168.1.1", start_scraper=False)
        session.scraper.transport = self.mock_transport
        session.result_deferred = Deferred()
        self.assertFalse(session.is_failed)
        packet = struct.pack("!iiq", session._action, session._transaction_id, 126)
        session.scraper.datagramReceived(packet, (None, None))
        session._infohash_list = ["test"]
        packet = struct.pack("!iiiii", session._action, session._transaction_id, 0, 1, 2)
        session.scraper.datagramReceived(packet, (None, None))
        self.assertTrue(session.is_finished)

        return session.result_deferred

    def test_http_unprocessed_infohashes(self):
        session = HttpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)
        result_deffered = Deferred()
        session.result_deferred = result_deffered
        session._infohash_list.append("test")
        response = bencode(dict())
        session._process_scrape_response(response)
        self.assertTrue(session.is_finished)

    @deferred(timeout=5)
    def test_failed_unicode(self):
        test_deferred = Deferred()

        session = HttpTrackerSession(u"localhost", ("localhost", 8475), "/announce", 5)

        def on_error(failure):
            self.assertEqual(failure.type, ValueError)
            test_deferred.callback(None)

        session.result_deferred = Deferred().addErrback(on_error)
        session._process_scrape_response(bencode({'failure reason': '\xe9'}))

        return test_deferred

    @deferred(timeout=5)
    def test_failed_unicode_udp(self):
        test_deferred = Deferred()

        session = UdpTrackerSession("localhost", ("localhost", 8475), "/announce", 5)

        def on_error(failure):
            self.assertEqual(failure.type, ValueError)
            test_deferred.callback(None)

        session.result_deferred = Deferred().addErrback(on_error)
        session.failed(msg='\xd0')

        return test_deferred


class TestDHTSession(TriblerCoreTest):
    """
    Test the DHT session that we use to fetch the swarm status from the DHT.
    """

    def setUp(self, annotate=True):
        super(TestDHTSession, self).setUp(annotate=annotate)

        config = SessionStartupConfig()
        config.set_state_dir(self.getStateDir())

        self.session = Session(config, ignore_singleton=True)

        self.dht_session = FakeDHTSession(self.session, 'a' * 20, 10)

    @deferred(timeout=10)
    def test_cleanup(self):
        """
        Test the cleanup of a DHT session
        """
        return self.dht_session.cleanup()

    @deferred(timeout=10)
    def test_connect_to_tracker(self):
        """
        Test the metainfo lookup of the DHT session
        """
        def get_metainfo(infohash, callback, **_):
            callback({"seeders": 1, "leechers": 2})

        def verify_metainfo(metainfo):
            self.assertTrue('DHT' in metainfo)
            self.assertEqual(metainfo['DHT'][0]['leechers'], 2)
            self.assertEqual(metainfo['DHT'][0]['seeders'], 1)

        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo
        return self.dht_session.connect_to_tracker().addCallback(verify_metainfo)

    @deferred(timeout=10)
    def test_metainfo_timeout(self):
        """
        Test the metainfo timeout of the DHT session
        """
        test_deferred = Deferred()

        def get_metainfo_timeout(*args, **kwargs):
            timeout_cb = kwargs.get('timeout_callback')
            timeout_cb('a' * 20)

        def on_timeout(failure):
            test_deferred.callback(None)

        self.session.lm.ltmgr = MockObject()
        self.session.lm.ltmgr.get_metainfo = get_metainfo_timeout
        self.dht_session.connect_to_tracker().addErrback(on_timeout)
        return test_deferred

    def test_methods(self):
        """
        Test various methods in the DHT session class
        """
        self.assertTrue(self.dht_session.can_add_request())
        self.dht_session.add_infohash('b' * 20)
        self.assertEqual(self.dht_session.infohash, 'b' * 20)
        self.assertEqual(self.dht_session.max_retries, DHT_TRACKER_MAX_RETRIES)
        self.assertEqual(self.dht_session.retry_interval, DHT_TRACKER_RECHECK_INTERVAL)
        self.assertGreater(self.dht_session.last_contact, 0)
