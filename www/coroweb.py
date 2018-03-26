# -*- coding: utf-8 -*-

__author__ = 'Minty'

import asyncio, functools, inspect, logging, os
from aiohttp import web
from urllib import parse
from apis import APIError

logging.basicConfig(level = logging.INFO)

# decorator for view functions, store URL information in these functions
def Handler_decorator(path, *, method):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__route__ = path
        wrapper.__method__ = method
        return wrapper
    return decorator
    
# create GET and POST method by partial functions
# the final object is to map normal function into view function
get = functools.partial(Handler_decorator, method = 'GET')
post = functools.partial(Handler_decorator, method = 'POST')

'''
link: http://docs.python.org/3/library/inspect.html#inspect.Parameter

Use 'inspect' to parse the parameters of view functions:

POSITIONAL_ONLY	        Value must be supplied as a positional argument.
POSITIONAL_OR_KEYWORD   Value may be supplied as either a keyword or positional argument.
VAR_POSITIONAL	        A tuple of positional arguments that aren’t bound to any other parameter. 
KEYWORD_ONLY	        Value must be supplied as a keyword argument. 
VAR_KEYWORD	            A dict of keyword arguments that aren’t bound to any other parameter. 
'''

# get parameters must be supplied as a keyword and without default value
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

# get parameters must be supplied as a keyword
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

# check if parameters must be supplied as a keyword exist
def has_named_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

# check if a dict of keyword arguments exist
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

# check if parameter 'request' exist and appears at last
def has_request_arg(fn):
    params = inspect.signature(fn).parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (
            param.kind != inspect.Parameter.VAR_KEYWORD and 
            param.kind != inspect.Parameter.KEYWORD_ONLY and 
            param.kind != inspect.Parameter.VAR_POSITIONAL
            ):
            raise ValueError('request parameter must be the last parameter in function: {}'.format(fn.__name__))
    return found

# RequestHandler analyze the parameters of view function, abstract them from web.Request, call view function, then process the result into web.Response
class RequestHandler(object):

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._required_kw_args = get_required_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._has_request_arg = has_request_arg(fn)
        self._has_named_kw_arg = has_named_kw_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)

    async def __call__(self, request):
        kw = None
        if self._has_named_kw_arg or self._has_var_kw_arg:

            if request.method == 'POST':
                # return error 400 if content_type doesn't exist
                if request.content_type == None:
                    return web.HTTPBadRequest(text = 'Missing Content_Type.')
                ct = request.content_type.lower()
                # json format
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text = 'JSON body must be object.')
                    kw = params
                # form format
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(text = 'Unsupported Content_Type: {}'.format(request.content_type))

            elif request.method == 'GET':
                # the query part in url request after ?
                qs = request.query_string()
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]

        if kw is None:
            kw = dict(**request.match_info)
        else:
            if self._has_named_kw_arg and (not self._has_var_kw_arg):
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warn('Duplicate arg name in named arg and kw args: {}'.format(k))
                kw[k] = v

        if self._has_request_arg:
            kw['request'] = request

        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest(text = 'Missing argument: {}'.format(name))
        
        logging.info('call with args: {}'.format(str(kw)))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error = e.error, data = e.data, message = e.message)

# register an view function:
# 1. check if it has path and method
# 2. transfer it into coroutine if it is not one
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if method is None or path is None:
        raise ValueError('@get or @post not defined in {}'.format(fn.__name__))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route {} {} => {}({})'.format(method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))

# register many view functions in one module
def add_routes(app, module_name):
    n = module_name.rfind('.')
    
    if n == -1:
        # __import__ the function version of import
        mod = __import__(module_name, globals(), locals(), [], 0)
    else:
        name = module_name[(n + 1) :]
        mod = getattr(__import__(module_name[: n], globals(), locals(), [name], 0), name)

    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)    
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)

# add static files like image, css or js files
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static {} => {}'.format('/static/', path))