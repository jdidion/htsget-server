"""
https://github.com/googlegenomics/htsget/blob/master/htsget-server/main.go
https://github.com/muayyad-alsadi/python-PooledProcessMixIn/blob/master/PooledProcessMixIn.py
"""
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Sequence, Tuple, Callable
from urllib.parse import ParseResult, urlparse


ServerAddress = Tuple[str, int]


class HttpError(Exception):
    def __init__(self, status: int, error_type: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status = status
        self.error_type = error_type

    @property
    def message(self):
        msg = ""
        if self.args:
            msg = self.args[0]
        elif hasattr(self, "__cause__") and self.__cause__.args:
            msg = self.__cause__.args[0]
        return msg


class NotFoundHttpError(HttpError):
    def __init__(self, path, *args, **kwargs):
        super().__init__(
            HTTPStatus.NOT_FOUND, "NotFound",
            "The resource requested was not found",
            *args, **kwargs
        )
        self.path = path


class UnknownHttpError(HttpError):
    def __init__(self, *args, **kwargs):
        super().__init__(
            HTTPStatus.INTERNAL_SERVER_ERROR, "UnknownError",
            *args, **kwargs
        )


class RoutingHttpRequestHandler(BaseHTTPRequestHandler):
    """HTTPRequestHandler for an htsget server.
    """
    def do_GET(self):
        try:
            self.check_headers()
            self.route_request()
        except HttpError as err:
            self.handle_error(err)
        except Exception as err:
            try:
                raise UnknownHttpError from err
            except HttpError as err:
                self.handle_error(err)

    def check_headers(self):
        pass

    def route_request(self):
        """Route `self.path` to the correct handler.

        Raises:
            NotFoundError if `self.path` is not a valid path.
        """
        parsed = urlparse(self.path)
        if len(parsed.path) == 0 or not parsed.path.startswith("/"):
            raise NotFoundHttpError(self.path)
        path_parts = parsed.path[1:].split("/")
        route_handler, sub_route = self.server.router.get_route_handler(path_parts)
        route_handler(sub_route, parsed, self)

    def handle_error(self, err: HttpError):
        self.send_error(err.status)


class Router:
    def __init__(self):
        self.routes = {}

    def add_route(
        self, path: Sequence[str],
        handler: Callable[[Sequence[str], ParseResult, BaseHTTPRequestHandler], None]
    ):
        route_dict = self.routes
        for part in path[:-1]:
            if part not in route_dict:
                route_dict[part] = {}
            route_dict = route_dict[part]
        route_dict[path[-1]] = handler

    def get_route_handler(self, path: Sequence[str]):
        route_dict = self.routes
        for i in range(len(path)):
            if path[i] not in route_dict:
                raise NotFoundHttpError(path)
            val = route_dict[path[i]]
            if isinstance(val, dict):
                route_dict = val
            else:
                return val, path[i+1:]
        else:
            raise NotFoundHttpError(path)


class ThreadedHttpServer(HTTPServer):
    """HTTP server that handles each request in a new thread.
    """

    def process_request(self, request, client_address):
        thread = Thread(
            target=self._new_request,
            args=(self.RequestHandlerClass, request, client_address, self)
        )
        thread.start()

    def _new_request(self, handler_class, request, address, server):
        handler_class(request, address, server)
        self.shutdown_request(request)


class RoutingServer(ThreadedHttpServer):
    """ThreadedHTTPServer that serves files according to the htsget protocol.
    """

    def __init__(
        self, server_address: ServerAddress, router: Router,
        request_handler_class=RoutingHttpRequestHandler, **kwargs
    ):
        super().__init__(server_address, request_handler_class, **kwargs)
        self.router = router
