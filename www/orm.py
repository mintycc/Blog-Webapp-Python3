# -*- coding: utf-8 -*-

__author__ = 'Minty'

import asyncio, logging, aiomysql

# logging.info() will make no use without this config
logging.basicConfig(level = logging.INFO)

def log(sql, args = ()):
    logging.info('SQL: {}'.format(sql))

async def create_pool(loop, **kw):
    logging.info('create database connection pool ...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host', 'localhost'),
        port = kw.get('port', 3306),
        user = kw['user'],
        password = kw['password'],
        db = kw['db'],
        # charset important, otherwise the information fetched from database will be garbled
        charset = kw.get('charset', 'utf-8'),
        # True means autocommit after database is changed
        autocommit = kw.get('autocommit', True),
        maxsize = kw.get('maxsize', 10),
        minsize = kw.get('minsize', 1),
        loop = loop
    )