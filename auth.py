import base64


def basic_auth(auth_func=lambda *args, **kwargs: True):
    def basic_auth_decorator(handler_cls):
        def wrap_execute(handler_exec):
            def require_basic_auth(handler, kwargs):
                def create_auth_header():
                    handler.set_status(401)
                    handler.set_header('WWW-Authenticate',
                                       'Basic realm=Restricted')
                    handler._transforms = []
                    handler.finish()

                _header = handler.request.headers.get('Authorization')
                if _header is None or not _header.startswith('Basic '):
                    create_auth_header()
                else:
                    user, pwd = base64.b64decode(_header[6:])\
                        .decode("utf-8").split(':', 2)
                    if not auth_func(user, pwd):
                        create_auth_header()

            def _execute(self, transforms, *args, **kwargs):
                require_basic_auth(self, kwargs)
                return handler_exec(self, transforms, *args, **kwargs)

            return _execute

        handler_cls._execute = wrap_execute(handler_cls._execute)
        return handler_cls
    return basic_auth_decorator
