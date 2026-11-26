"""SQL Server backend that reports an unavailable site database as ``OperationalError``.

When the instance is reachable but the site database is offline or restoring, or the login is refused,
ODBC answers the connect with SQLSTATE 28000 (SQL Server error 4060/18456). pyodbc raises that as
``InterfaceError``, which Django does not treat as a ``DatabaseError``, so every ``except DatabaseError``
site guard let it escape as HTTP 500 instead of listing the site in ``missing_sites``. Converting it at the
one place a connection is opened lets those guards work unchanged. Query-time errors are not touched.
"""

from mssql.base import DatabaseWrapper as MssqlDatabaseWrapper

# ODBC connection-failure states: login failed / cannot open database, cannot connect, connection failed, timeout.
UNAVAILABLE_STATES = frozenset({"28000", "08001", "08004", "08S01", "HYT00", "HYT01"})


class DatabaseWrapper(MssqlDatabaseWrapper):
    def get_new_connection(self, conn_params):
        try:
            return super().get_new_connection(conn_params)
        except self.Database.InterfaceError as exc:
            state = str(exc.args[0]) if exc.args else ""
            if state in UNAVAILABLE_STATES:
                raise self.Database.OperationalError(*exc.args) from exc
            raise
