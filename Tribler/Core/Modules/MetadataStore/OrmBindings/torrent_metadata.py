from __future__ import absolute_import

from datetime import datetime

from pony import orm
from pony.orm import db_session, raw_sql

from Tribler.Core.Modules.MetadataStore.serialization import TorrentMetadataPayload, REGULAR_TORRENT
from Tribler.pyipv8.ipv8.database import database_blob


def define_binding(db):
    class TorrentMetadata(db.ChannelNode):
        _discriminator_ = REGULAR_TORRENT

        # Serializable
        timestamp = orm.Required(int, size=64, default=0)
        infohash = orm.Optional(database_blob, default='\x00' * 20)
        size = orm.Optional(int, size=64, default=0)
        torrent_date = orm.Optional(datetime, default=datetime.utcnow)
        title = orm.Optional(str, default='')
        tags = orm.Optional(str, default='')
        tracker_info = orm.Optional(str, default='')

        # Local
        xxx = orm.Optional(float, default=0)
        health = orm.Optional('TorrentState', reverse='metadata')

        _payload_class = TorrentMetadataPayload

        def __init__(self, *args, **kwargs):
            if "health" not in kwargs and "infohash" in kwargs:
                ts = db.TorrentState.get(infohash=kwargs["infohash"])
                kwargs["health"] = ts or db.TorrentState(infohash=kwargs["infohash"])
            super(TorrentMetadata, self).__init__(*args, **kwargs)

        def get_magnet(self):
            return ("magnet:?xt=urn:btih:%s&dn=%s" %
                    (str(self.infohash).encode('hex'), self.title)) + \
                   ("&tr=%s" % self.tracker_info if self.tracker_info else "")

        @classmethod
        def search_keyword(cls, query, entry_type=None, lim=100):
            # Requires FTS5 table "FtsIndex" to be generated and populated.
            # FTS table is maintained automatically by SQL triggers.
            # BM25 ranking is embedded in FTS5.

            # Sanitize FTS query
            if not query:
                return []
            if query.endswith("*"):
                query = "\"" + query[:-1] + "\"" + "*"
            else:
                query = "\"" + query + "\""

            fts_ids = raw_sql(
                "SELECT rowid FROM FtsIndex WHERE FtsIndex MATCH $query ORDER BY bm25(FtsIndex) LIMIT %d" % lim)
            return cls.select(lambda g: g.rowid in fts_ids)

        @classmethod
        def get_auto_complete_terms(cls, keyword, max_terms, limit=100):
            with db_session:
                result = cls.search_keyword(keyword + "*", lim=limit)[:]
            titles = [g.title.lower() for g in result]

            # Copy-pasted from the old DBHandler (almost) completely
            all_terms = set()
            for line in titles:
                if len(all_terms) >= max_terms:
                    break
                i1 = line.find(keyword)
                i2 = line.find(' ', i1 + len(keyword))
                term = line[i1:i2] if i2 >= 0 else line[i1:]
                if term != keyword:
                    all_terms.add(term)
            return list(all_terms)

    return TorrentMetadata
