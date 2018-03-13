# -*- coding: utf-8 -*-

__author__ = 'Minty'

import logging
logging.basicConfig(level = logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static

# jinja2 document: http://jinja.pocoo.org/docs/2.10/
def init_jinja2(app, **kw):
    logging.info('init jinja2 ...')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if not path:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    env = Environment(loader = FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters:
        for name, f in filters.items():
            env.filters[name] = f
    app['__template__'] = env

# new style middleware: https://aiohttp.readthedocs.io/en/stable/web_advanced.html#aiohttp-web-middlewares
# middleware to log
@web.middleware
async def logger_middleware(request, handler):
    logging.info('Request: {} {}'.format(request.method, request.path))
    return await handler(request)

# middleware to produce response in right format
@web.middleware
async def response_middleware(request, handler):
    logging.info('Response handler ...')
    r = await handler(request)
    logging.info('response result = {}'.format(str(r)))
    # StreamResponse is the superclass of all response classes
    if isinstance(r, web.StreamResponse):
        return r
    if isinstance(r, bytes):
        logging.info('*'*10)
        resp = web.Response(body = r)
        resp.content_type = 'application/octet-stream'
        return resp
    if isinstance(r, str):
        if r.startswith('redirect:'):
            return web.HTTPFound(r[9 :])
        resp = web.Response(body = r.encode('utf-8'))
        resp.content_type = 'text/html;charset=utf-8'
        return resp
    if isinstance(r, dict):
        template = r.get('__template__', None)
        if template is None:
            resp = web.Response(
                body = json.dumps(r, ensure_ascii = False, default = lambda obj: obj.__dict__).encode('utf-8'))
            resp.content_type = 'application/json;charset=utf-8'
            return resp
        else:
            # ??
            resp = web.Response(body = request.app['__template__'].get_template(template).render(**r))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
    if isinstance(r, int) and (100 <= r < 600):
        resp = web.Response(status = r)
        return resp
    if isinstance(r, tuple) and len(r) == 2:
        status_code, message = r
        if isinstance(status_code, int) and (100 <= status_code < 600):
            resp = web.Response(status = r, text = str(message))
    resp = web.Response(body = str(r).encode('utf-8'))
    resp.content_type = 'text/plain;charset=utf-8'
    return resp

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 120:
        return u'1 min ago'
    if delta < 3600:
        return u'{} mins ago'.format(delta // 60)
    if delta < 7200:
        return u'1 hr ago'
    if delta < 86400:
        return u'{} hrs ago'.format(delta // 3600)
    if delta < 172800:
        return u'1 day ago'
    if delta < 604800:
        return u'{} days ago'.format(delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'{}/{}/{}'.format(dt.monty, dt.day, dt.year)

async def init(loop):
    app = web.Application(loop = loop, middlewares = [logger_middleware, response_middleware])
    init_jinja2(app, filters = dict(datetime = datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), 'localhost', 9000)
    logging.info('server started at http://127.0.0.1:9000 ...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()