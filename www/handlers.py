# -*- coding: utf-8 -*-

__author__ = 'Minty'

from coroweb import get, post
from model import User, Blog, Comment
import asyncio, time

@get('/')
async def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(
            id = '1', 
            name = 'Test Blog', 
            summary = summary, 
            created_at = time.time() - 120
        ),
        Blog(
            id = '2', 
            name = 'Something New', 
            summary = summary, 
            created_at = time.time() - 3600
        ),
        Blog(
            id = '3', 
            name = 'Learn Swift', 
            summary = summary, 
            created_at = time.time() - 7200
        )
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }

@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy = 'created_at desc')
    for u in users:
        u.password = '******'
    return dict(users = users)