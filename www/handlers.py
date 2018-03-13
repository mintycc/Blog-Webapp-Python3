# -*- coding: utf-8 -*-

__author__ = 'Minty'

from coroweb import get, post
from model import User
import asyncio

@get('/')
async def index(request):
    users = await User.findAll()
    return {
        '__template__': 'test.html',
        'users': users
    }