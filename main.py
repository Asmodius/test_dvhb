import asyncio
import logging
import json

from tornado.web import RequestHandler, Application, HTTPError
from tornado.platform.asyncio import AsyncIOMainLoop
from aiopg import Pool, DEFAULT_TIMEOUT

from auth import basic_auth


logger = logging.getLogger(__name__)

DSN = "dbname=warrior user=warrior"
PORT = 8888

LOGIN = 'test'
PASSW = 'test'


def check_user(user, pwd):
    return user == LOGIN and pwd == PASSW


def rec4list(*recs):
    return [{'id': i[0], 'path': i[1], 'text': i[2]} for i in recs]


@basic_auth(check_user)
class NodeHandler(RequestHandler):

    async def get(self, _id=None):
        async with self.application.db.acquire() as conn:
            async with conn.cursor() as cur:
                if not _id:
                    await cur.execute("SELECT min(id) FROM node")
                    root = await cur.fetchone()
                    if not root:
                        raise HTTPError(404)
                    _id = root[0]
                await cur.execute("SELECT id, path, text FROM node "
                                  "WHERE id=%s", [_id])
                root = await cur.fetchone()
                if not root:
                    raise HTTPError(404)

                text = self.get_argument('text', '')
                path = '.'.join([root[1], str(_id)])
                if not text:
                    await cur.execute("SELECT id, path, text FROM node "
                                      "WHERE (id = %s OR path LIKE %s)", [_id, path + '%'])
                else:
                    await cur.execute("SELECT id, path, text FROM node "
                                      "WHERE (id = %s OR path LIKE %s) AND "
                                      "text @@ %s", [_id, path + '%', text])
                data = await cur.fetchall()
                self.write(json.dumps(rec4list(*data)))

    async def post(self, _id=None):
        text = self.get_argument('text', '') or \
               self.request.body.decode("utf-8")

        async with self.application.db.acquire() as conn:
            async with conn.cursor() as cur:
                if not _id:
                    await cur.execute("SELECT id FROM node LIMIT 1")
                    root = await cur.fetchone()
                    if root:
                        raise HTTPError(404)
                    path = ''
                else:
                    await cur.execute("SELECT path FROM node "
                                      "WHERE id=%s", [_id])
                    root = await cur.fetchone()
                    if not root:
                        raise HTTPError(404)
                    path = '.'.join([root[0], _id])
                await cur.execute(
                    "INSERT INTO node (path, text) VALUES (%s, %s)",
                    [path, text]
                )

    async def delete(self, _id=None):
        if not _id:
            raise HTTPError(404)

        async with self.application.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT path FROM node WHERE id=%s", [_id])
                root = await cur.fetchone()
                if not root:
                    raise HTTPError(404)
                path = '.'.join([root[0], _id])
                await cur.execute(
                    "DELETE FROM node WHERE id=%s OR path LIKE %s",
                    [_id, path + '%']
                )


class AppServer(Application):

    def __init__(self):
        self.db = Pool(DSN,
                       minsize=1,
                       maxsize=10,
                       loop=None,
                       timeout=DEFAULT_TIMEOUT,
                       enable_json=True,
                       enable_hstore=True,
                       enable_uuid=True,
                       echo=False)

        handlers = [
            (r"/", NodeHandler),
            (r"/(\d*)/?", NodeHandler),
        ]
        settings = {
            # "debug": True,
        }
        Application.__init__(self, handlers, **settings)


if __name__ == '__main__':
    AsyncIOMainLoop().install()
    app = AppServer()
    app.listen(PORT)
    logger.warning('SERVER STARTED: %s' % PORT)
    loop = asyncio.get_event_loop()
    loop.run_forever()
