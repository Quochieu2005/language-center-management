"""A site database that refuses the connection is a ``DatabaseError`` so site guards report it as missing."""

from unittest.mock import patch

import pyodbc
from django.db.utils import DatabaseError, InterfaceError, OperationalError
from django.test import SimpleTestCase
from mssql.base import DatabaseWrapper as MssqlDatabaseWrapper

from core.sites.mssql_backend.base import DatabaseWrapper

SETTINGS = {
    "NAME": "x", "HOST": "h", "PORT": "1", "USER": "", "PASSWORD": "", "OPTIONS": {}, "TIME_ZONE": None,
    "CONN_MAX_AGE": 0, "AUTOCOMMIT": True, "CONN_HEALTH_CHECKS": False, "ATOMIC_REQUESTS": False, "TEST": {},
}


def failing(state):
    return patch.object(MssqlDatabaseWrapper, "get_new_connection",
                        side_effect=pyodbc.InterfaceError(state, f"[{state}] Login failed"))


class ConnectFailureTests(SimpleTestCase):
    def wrapper(self):
        return DatabaseWrapper(dict(SETTINGS), "site_test")

    def test_login_failure_on_an_offline_database_becomes_an_operational_error(self):
        with failing("28000"), self.assertRaises(pyodbc.OperationalError):
            self.wrapper().get_new_connection({})

    def test_django_sees_a_database_error_not_an_interface_error(self):
        wrapper = self.wrapper()
        with failing("28000"), patch.object(DatabaseWrapper, "get_connection_params", return_value={}):
            with self.assertRaises(DatabaseError) as caught:
                wrapper.ensure_connection()
        self.assertIsInstance(caught.exception, OperationalError)
        self.assertNotIsInstance(caught.exception, InterfaceError)

    def test_other_interface_errors_are_left_alone(self):
        with failing("IM002"), self.assertRaises(pyodbc.InterfaceError):
            self.wrapper().get_new_connection({})
