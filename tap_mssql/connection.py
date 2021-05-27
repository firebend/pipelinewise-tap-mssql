#!/usr/bin/env python3

import os

import backoff

import pyodbc
import pymssql

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

import singer
import ssl

from urllib.parse import quote_plus

LOGGER = singer.get_logger()


@backoff.on_exception(backoff.expo, pymssql.Error, max_tries=5, factor=2)
def connect_with_backoff(connection):
    warnings = []
    with connection.cursor() as cur:
        if warnings:
            LOGGER.info(
                (
                    "Encountered non-fatal errors when configuring session that could "
                    "impact performance:"
                )
            )
        for w in warnings:
            LOGGER.warning(w)

    return connection

def get_azure_sql_engine(config) -> Engine:
    """The All-Purpose SQL connection object for the Azure Data Warehouse."""

    # conn_values = {
    #     "prefix": "mssql+pyodbc://",
    #     "username": quote_plus(os.getenv("AZUREDB_USERNAME")) or config["user"],
    #     "password": quote_plus(os.getenv("AZUREDB_PASSWORD")) or config["password"],
    #     "port": os.getenv("AZUREDB_PORT") or config.get("port", "1433"),
    #     "host": os.getenv("AZUREDB_HOST") or config["host"],
    #     "driver": "ODBC+Driver+17+for+SQL+Server",
    #     "database": os.getenv("AZUREDB_NAME") or config["database"],
    # }
    conn_values = {
        "prefix": "mssql+pyodbc://",
        "username": quote_plus(os.getenv("AZUREDB_USERNAME")),
        "password": quote_plus(os.getenv("AZUREDB_PASSWORD")),
        "port": os.getenv("AZUREDB_PORT"),
        "host": os.getenv("AZUREDB_HOST"),
        "driver": "ODBC+Driver+17+for+SQL+Server",
        "database": os.getenv("AZUREDB_NAME"),
    }

    conn_values["authentication"] = "SqlPassword"
    raw_conn_string = "{prefix}{username}:{password}@{host}:\
{port}/{database}?driver={driver}&Authentication={authentication}&\
autocommit=True&IntegratedSecurity=False"

    engine = create_engine(raw_conn_string.format(**conn_values))
    return engine


class MSSQLConnection(pymssql.Connection):
    def __init__(self, config):
        args = {
            "user": config["user"],
            "password": config["password"],
            "server": config["host"],
            "database": config["database"],
            "charset": "utf8",
            "port": config.get("port", "1433"),
        }
        conn = pymssql._mssql.connect(**args)
        super().__init__(conn, False, True)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        del exc_info
        self.close()


def make_connection_wrapper(config):
    class ConnectionWrapper(MSSQLConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(config)

            connect_with_backoff(self)

    return ConnectionWrapper
