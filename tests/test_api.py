import json

import psycopg2
from tornado.platform.asyncio import AsyncIOMainLoop
from tornado.testing import AsyncHTTPTestCase

from main import AppServer, LOGIN, PASSW, DSN


class APITestCase(AsyncHTTPTestCase):
    def __init__(self, *args, **kwargs):
        super(APITestCase, self).__init__(*args, **kwargs)
        self.db = psycopg2.connect(DSN)

    def get_app(self):
        return AppServer()

    def get_new_ioloop(self):
        return AsyncIOMainLoop()

    def setUp(self):
        super(APITestCase, self).setUp()
        curr = self.db.cursor()
        curr.execute("DELETE FROM node")
        curr.execute("ALTER SEQUENCE node_id_seq RESTART WITH 1")
        self.db.commit()

    def _select(self):
        curr = self.db.cursor()
        curr.execute("SELECT id, path, text FROM node")
        return curr.fetchall()

    def _insert(self):
        curr = self.db.cursor()
        curr.execute("INSERT INTO node (path, text) VALUES ('', 'T1 foo')")
        curr.execute("INSERT INTO node (path, text) VALUES ('.1', 'T2 bar')")
        curr.execute("INSERT INTO node (path, text) VALUES ('.1', 'T3 baz')")
        curr.execute("INSERT INTO node (path, text) VALUES ('.1.2', 'T4 foo')")
        self.db.commit()

    def _fetch(self, url, method, data=None):
        response = self.fetch(url,
                              method=method,
                              auth_username=LOGIN,
                              auth_password=PASSW,
                              body=data
                              )
        data = response.body
        try:
            if data is not None:
                data = json.loads(response.body.decode("utf-8"))
        except json.decoder.JSONDecodeError:
            data = None
        return response.code, data

    def test_get_root(self):
        code, data = self._fetch('/', 'GET')
        self.assertEqual(code, 404)
        self.assertIsNone(data)

        self._insert()
        code, data = self._fetch('/', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'text': 'T1 foo', 'path': '', 'id': 1},
                                    {'text': 'T2 bar', 'path': '.1', 'id': 2},
                                    {'text': 'T3 baz', 'path': '.1', 'id': 3},
                                    {'text': 'T4 foo', 'path': '.1.2', 'id': 4}])

    def test_get_sub_tree(self):
        self._insert()

        code, data = self._fetch('/1', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'text': 'T1 foo', 'id': 1, 'path': ''},
                                    {'text': 'T2 bar', 'id': 2, 'path': '.1'},
                                    {'text': 'T3 baz', 'id': 3, 'path': '.1'},
                                    {'text': 'T4 foo', 'id': 4, 'path': '.1.2'}])

        code, data = self._fetch('/2', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'path': '.1', 'text': 'T2 bar', 'id': 2},
                                    {'path': '.1.2', 'text': 'T4 foo', 'id': 4}])

        code, data = self._fetch('/3', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'id': 3, 'path': '.1', 'text': 'T3 baz'}])

        code, data = self._fetch('/4', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'id': 4, 'text': 'T4 foo', 'path': '.1.2'}])

        code, data = self._fetch('/5', 'GET')
        self.assertEqual(code, 404)
        self.assertIsNone(data)

    def test_get_find(self):
        self._insert()

        code, data = self._fetch('/?text=foo', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'text': 'T1 foo', 'path': '', 'id': 1},
                                    {'text': 'T4 foo', 'path': '.1.2', 'id': 4}])

        code, data = self._fetch('/1?text=foo', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'id': 1, 'text': 'T1 foo', 'path': ''},
                                    {'id': 4, 'text': 'T4 foo', 'path': '.1.2'}])

        code, data = self._fetch('/2?text=foo', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'path': '.1.2', 'text': 'T4 foo', 'id': 4}])

        code, data = self._fetch('/3?text=foo', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [])

        code, data = self._fetch('/4?text=foo', 'GET')
        self.assertEqual(code, 200)
        self.assertListEqual(data, [{'text': 'T4 foo', 'path': '.1.2', 'id': 4}])

        code, data = self._fetch('/5?text=foo', 'GET')
        self.assertEqual(code, 404)
        self.assertIsNone(data)

    def test_post(self):
        code, _ = self._fetch('/1', 'POST', 'text1')
        self.assertEqual(code, 404)
        data = self._select()
        self.assertListEqual(data, [])

        code, _ = self._fetch('/', 'POST', 'text1')
        self.assertEqual(code, 200)
        data = self._select()
        self.assertListEqual(data, [(1, '', 'text1')])

        code, _ = self._fetch('/', 'POST', 'text')
        self.assertEqual(code, 404)

        code, _ = self._fetch('/1', 'POST', 'text2')
        self.assertEqual(code, 200)
        data = self._select()
        self.assertListEqual(data, [(1, '', 'text1'), (2, '.1', 'text2')])

        code, _ = self._fetch('/1', 'POST', 'text3')
        self.assertEqual(code, 200)
        data = self._select()
        self.assertListEqual(data, [(1, '', 'text1'), (2, '.1', 'text2'), (3, '.1', 'text3')])

        code, _ = self._fetch('/2', 'POST', 'text4')
        self.assertEqual(code, 200)
        data = self._select()
        self.assertListEqual(data, [(1, '', 'text1'),
                                    (2, '.1', 'text2'),
                                    (3, '.1', 'text3'),
                                    (4, '.1.2', 'text4')])

    def test_get_delete(self):
        self._insert()

        code, _ = self._fetch('/', 'DELETE')
        self.assertEqual(code, 404)
        data = self._select()
        self.assertListEqual(data, [(1, '', 'T1 foo'),
                                    (2, '.1', 'T2 bar'),
                                    (3, '.1', 'T3 baz'),
                                    (4, '.1.2', 'T4 foo')])

        code, _ = self._fetch('/2', 'DELETE')
        self.assertEqual(code, 200)
        data = self._select()
        self.assertListEqual(data, [(1, '', 'T1 foo'),
                                    (3, '.1', 'T3 baz')])

        code, _ = self._fetch('/1', 'DELETE')
        self.assertEqual(code, 200)
        data = self._select()
        self.assertListEqual(data, [])
