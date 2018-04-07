# -*- coding: utf-8 -*-

__author__ = 'Minty'

from coroweb import get, post
from model import User, Blog, Comment, next_id
from apis import APIError, APIPermissionError, APIValueError, APIResourceNotFoundError
from aiohttp import web

from config import configs
import asyncio, time, re, hashlib, json, logging

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

# re.compile() compile a regular expression pattern into a regular expression object, which doesn't need compile anymore before match() etc.
_RE_EMAIL = re.compile(r'^[\w\.\-\_]+\@[\w\-\_]+(\.[\w\-\_]+){1,4}$')
_RE_SHA1  = re.compile(r'^[0-9a-f]{40}$')

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError

def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '{}-{}-{}-{}'.format(user.id, user.password, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        logging.info('enter cookie2user successfully')
        logging.info(cookie_str)
        L = cookie_str.split('-')
        if len(L) != 3:
            logging.info('wrong cookie format')
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            logging.info('cookie expires')
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '{}-{}-{}-{}'.format(uid, user.password, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.password = '******'
        logging.info('finish cookie2user successfully')
        return user
    except Exception as e:
        logging.exception(e)
        return None

async def text2html(text):
    lines = map(lambda s: '<p>{}</p>'.format(s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')),
        filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

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
        'blogs': blogs,
        '__user__': request.__user__
    }

@get('/register')
async def register():
    return {
        '__template__': 'register.html'
    }

@get('/signin')
async def signin():
    return {
        '__template__': 'signin.html'
    }

@get('/signout')
async def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/blog/{id}')
async def get_blog(id):
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = text2html(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }

@get('/manage/blogs/create')
async def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }

@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy = 'created_at desc')
    for u in users:
        u.password = '******'
    return dict(users = users)

@post('/api/users')
async def api_register_user(*, email, name, password):
    # string.strip() delete the prefix or suffix blanks
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not password or not _RE_SHA1.match(password):
        raise APIValueError('password')
    users = await User.findAll('email=?', [email])
    if len(users) > 0 :
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_password = '{}:{}'.format(uid, password)
    user = User(
        id = uid,
        name = name.strip(),
        email = email,
        password = hashlib.sha1(sha1_password.encode('utf-8')).hexdigest(),
        image = 'http://www.gravatar.com/avatar/{}?d=mm&s=120'.format(hashlib.md5(email.encode('utf-8')).hexdigest())
    )
    await user.save()
    r = web.Response()
    r.set_cookie(
        COOKIE_NAME,
        user2cookie(user, 86400),
        max_age = 86400,
        httponly = True
    )
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii = False).encode('utf-8')
    return r

@post('/api/authenticate')
async def authenticate(*, email, password):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not password:
        raise APIValueError('password', 'Invalid password.')
    users = await User.findAll('email=?', email)
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # verify password
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(password.encode('utf-8'))
    if sha1.hexdigest() != user.password:
        raise APIValueError('password', 'Wrong password.')
    # create response
    logging.info("****** signin successfully ******")
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog

@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)    
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(
        user_id = request.__user__.id,
        user_name = request.__user__.name,
        user_image = request.__user__.image,
        name = name.strip(),
        summary = summary.strip(),
        content = content.strip()
    )
    await blog.save()
    return blog