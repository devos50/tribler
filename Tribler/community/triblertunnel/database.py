"""
This file contains everything related to persistence for the market community.
"""
from __future__ import absolute_import

from os import path


from Tribler.pyipv8.ipv8.database import Database

DATABASE_DIRECTORY = path.join(u"sqlite")
# Path to the database location + dispersy._workingdirectory
DATABASE_PATH = path.join(DATABASE_DIRECTORY, u"tunnels.db")
# Version to keep track if the db schema needs to be updated.
LATEST_DB_VERSION = 1
# Schema for the Tunnel DB.
schema = u"""
CREATE TABLE IF NOT EXISTS payouts(
 trader_id            TEXT NOT NULL,
 order_number         INTEGER NOT NULL,
 asset1_amount        BIGINT NOT NULL,
 asset1_type          TEXT NOT NULL,
 asset2_amount        BIGINT NOT NULL,
 asset2_type          TEXT NOT NULL,
 traded_quantity      BIGINT NOT NULL,
 timeout              INTEGER NOT NULL,
 order_timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
 completed_timestamp  TIMESTAMP,
 is_ask               INTEGER NOT NULL,
 cancelled            INTEGER NOT NULL,
 verified             INTEGER NOT NULL,

 PRIMARY KEY (trader_id, order_number)
 );

CREATE TABLE IF NOT EXISTS option(key TEXT PRIMARY KEY, value BLOB);
INSERT OR REPLACE INTO option(key, value) VALUES('database_version', '""" + str(LATEST_DB_VERSION) + u"""');
"""


class TunnelsDB(Database):
    """
    Persistence layer for the Tribler Tunnel Community.
    """

    def get_schema(self):
        """
        Return the schema for the database.
        """
        return schema



    def open(self, initial_statements=True, prepare_visioning=True):
        return super(TunnelsDB, self).open(initial_statements, prepare_visioning)

    def get_upgrade_script(self, _):
        return None

    def check_database(self, database_version):
        """
        Ensure the proper schema is used by the database.
        :param database_version: Current version of the database.
        :return:
        """
        return LATEST_DB_VERSION
