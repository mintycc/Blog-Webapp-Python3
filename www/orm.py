# -*- coding: utf-8 -*-

__author__ = 'Minty'

import asyncio, logging, aiomysql

# logging.info() will make no use without this config
logging.basicConfig(level = logging.INFO)

def log(sql, args = ()):
    logging.info('SQL: {}'.format(sql))

async def create_pool(loop, **kw):
    logging.info('  create database connection pool ...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host', 'localhost'),
        port = kw.get('port', 3306),
        user = kw['user'],
        password = kw['password'],
        db = kw['db'],
        # charset important, otherwise the information fetched from database will be garbled
        charset = kw.get('charset', 'utf8'),
        # True means autocommit after database is changed
        autocommit = kw.get('autocommit', True),
        maxsize = kw.get('maxsize', 10),
        minsize = kw.get('minsize', 1),
        loop = loop
    )

async def destroy_pool():
    logging.info('  close database connection pool ...')
    global __pool
    if __pool is not None:
        __pool.close()
        await __pool.wait_closed()

async def select(sql, args, size = None):
    log(sql, args)
    global __pool
    # equals await type(__pool.acquire).__aenter
    # connect database
    async with __pool.acquire() as conn:
        #Obtain cursor. DictCursor: a cursor which returns results as a dictionary. 
        async with conn.cursor(aiomysql.DictCursor) as cur:
            #execute(query, args=None): sql statement and tuple or list of arguments for sql query
            await cur.execute(sql.replace('?', '%s'), args or ())
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
            logging.info('rows returned: {}'.format(len(rs)))
            logging.info(rs)
            return rs

#includes all INSERT, UPDATE and DELETE
async def execute(sql, args, autocommit = True):
    log(sql, args)
    async with __pool.acquire() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args or ())
                # rowcount: Returns the number of rows that has been produced of affected.
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return affected

# create a string filled with placeholders
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)

# base class to save column type and name
class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<{}, {}: {}>'.format(self.__class__.__name__, self.column_type, self.name)
    
# belows are several specific column types
class StringField(Field):

    def __init__(self, name = None, primary_key = False, default = None, ddl = 'varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):

    def __init__(self, name = None, default = False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):

    def __init__(self, name = None, primary_key = False, default = 0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):

    def __init__(self, name = None, primary_key = False, default = 0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):

    def __init__(self, name = None, default = None):
        super().__init__(name, 'text', False, default)

class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name
        logging.info('  found model: {} (table: {})'.format(name, tableName))
        mappings = dict() # column type
        fields = [] # column name
        primarykey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: {} ==> {}'.format(k, v))
                mappings[k] = v
                if v.primary_key:
                    if primarykey:
                        raise Exception('Duplicate primary key for field: {}'.format(v))
                    primarykey = k
                else:
                    fields.append(k)
        if not primarykey:
            raise Exception('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`{}`'.format(f), fields))
        attrs['__mappings__'] = mappings
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primarykey
        attrs['__fields__'] = fields
        # four different operations. `` to avoid keyword conflicts
        attrs['__select__'] = 'select `{}`, {} from `{}`'.format(primarykey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `{}` ({}, `{}`) values ({})'.format(tableName, ', '.join(escaped_fields), primarykey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `{}` set {} where `{}`=?'.format(tableName, ', '.join(map(lambda f:'`{}`=?'.format(mappings.get(f).name or f), fields)), primarykey)
        attrs['__delete__'] = 'delete from `{}` where `{}`=?'.format(tableName, primarykey)
        return type.__new__(cls, name, bases, attrs)

class Model(dict, metaclass = ModelMetaclass):

    def __init__(self, **kw):
        # super(type, self) by default
        super().__init__(**kw)
    
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError('"Model" object has no attribute "{}"'.format(key))

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for {}: {}'.format(key, str(value)))
                setattr(self, key, value)
        return value

    # make one method the class method
    @classmethod
    async def findAll(cls, where = None, args = None, **kw):
        ' find objects by where clause.'
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('orderBy')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        # may be problem
        if limit:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: {}'.format(str(limit)))
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where = None, args = None):
        ' find number by select and where. '
        sql = ['select {} _num_ from `{}`'.format(selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        ' find object by primary key. '
        rs = await select('{} where `{}`=?'.format(cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        # ** is a shortcut that allows you to pass multiple arguments to a function directly using either a list/tuple or a dictionary. 
        return cls(**rs[0])

    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to insert record: affected rows: {}'.format(rows))

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: {}'.format(rows))

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.info('failed to remove by primary key: affected rows: {}'.format(rows))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_pool(
        host = '127.0.0.1',
        port = 3306,
        user = 'root',
        password = 'password',
        db = 'test',
        loop = loop
    ))
    rs = loop.run_until_complete(select('select * from student', None))
    #rs = loop.run_until_complete(execute('update student set age=19 where name=?', 'minty'))
    print('heh:{}'.format(rs))