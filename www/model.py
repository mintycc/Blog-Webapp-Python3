# -*- coding: utf-8 -*-

__author__ = 'Minty'

import time, uuid, asyncio

import orm

from orm import Model, StringField, BooleanField, FloatField, TextField

def next_id():
    return '{:0^15}{}000'.format(
        int(time.time() * 1000),
        uuid.uuid4().hex
    )

class User(Model):
    __table__ = 'users'

    id = StringField(primary_key = True, default = next_id, ddl = 'varchar(50)')
    email = StringField(ddl = 'varchar(50)')
    password = StringField(ddl = 'varchar(50)')
    admin = BooleanField()
    name = StringField(ddl = 'varchar(50)')
    image = StringField(ddl = 'varchar(500)')
    created_at = FloatField(default = time.time)

class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key = True, default = next_id, ddl = 'varchar(50)')
    user_id = StringField(ddl = 'varchar(50)')
    user_name = StringField(ddl = 'varchar(50)')
    user_image = StringField(ddl = 'varchar(500)')
    name = StringField(ddl = 'varchar(50)')
    summary = StringField(ddl = 'varchar(200)')
    content = TextField()
    created_at = FloatField(default = time.time)

class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key = True, default = next_id, ddl = 'varchar(50)')
    blog_id = StringField(ddl = 'varchar(50)')
    user_id = StringField(ddl = 'varchar(50)')
    user_name = StringField(ddl = 'varchar(50)')
    user_image = StringField(ddl = 'varchar(500)')
    content = TextField()
    created_at = FloatField(default = time.time)

if __name__ == '__main__':

    async def test(loop, **kw):
        await orm.create_pool(
            loop = loop,
            user = 'root',
            password = 'password',
            db = 'awesome'
        )
        '''
        user = User(
            name = kw.get('name'),
            email = kw.get('email'),
            password = kw.get('password'),
            image = kw.get('image')
        )
        '''
        user = User(
            name = 'Reepom',
            email = 'reepom@gmail.com',
            password = 'password',
            image = 'pic3.jpg'
        )
        await user.save()
        await orm.destroy_pool()
    
    data = dict(
        name='minty', 
        email='destroy@test.com', 
        password='password', 
        image='about:blank'
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop, **data))
    loop.close()