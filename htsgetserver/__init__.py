from abc import ABCMeta, abstractmethod
from http import HTTPStatus
import json
from threading import Lock
from typing import Sequence
from urllib.parse import ParseResult, parse_qs

from htsgetserver.server import (
    Router,
    RoutingServer,
    RoutingHttpRequestHandler,
    HttpError,
    NotFoundHttpError,
)
from htsgetserver.store import DataStore, DefaultDataStore
from htsgetserver.utils import Runnable, run_interruptible


HTSGET_VERSION = (1, 1, 0)
OK_RESPONSE_CONTENT_TYPE = \
    "application/vnd.ga4gh.htsget.v{'.'.join(HTSGET_VERSION)}+json; charset=utf-8"
ERROR_RESPONSE_CONTENT_TYPE = "application/json"
DEFAULT_BLOCK_SIZE = 2 ** 30  # 1 GB
DEFAULT_PORT = 80


# TODO:
# TLS 1.2
# CORS
# urllib.urlencode data block URLs
# Content-Length header
# chunked transfer encoding


class UnsupportedMediaTypeHttpError(HttpError):
    def __init__(self, media_type):
        super().__init__(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            f"The requested media type is unsupported: {media_type}"
        )


class RouteHandler(metaclass=ABCMeta):
    @abstractmethod
    def __call__(
            self, sub_route: Sequence[str], parsed_url: ParseResult,
            http_request_handler: "HtsgetHttpRequestHandler"
    ):
        pass


class ApiRouteHandler(RouteHandler, metaclass=ABCMeta):
    def __init__(self, data_store: DataStore, block_size: int):
        self.data_store = data_store
        self.block_size = block_size
        self._cache = {}
        self._cache_lock = Lock()

    def __call__(
        self, sub_route: Sequence[str], parsed_url: ParseResult,
        http_request_handler: "HtsgetHttpRequestHandler"
    ):
        if len(sub_route) != 0:
            raise NotFoundHttpError(parsed_url.path)
        query = parse_qs(parsed_url.query, True, True)
        self.handle(sub_route, query, http_request_handler)

    @property
    @abstractmethod
    def default_format(self) -> str:
        pass

    @property
    @abstractmethod
    def index_format(self) -> str:
        pass

    def handle(
        self, record_id: Sequence[str], query: dict,
        http_request_handler: "HtsgetHttpRequestHandler"
    ):
        """Handle a query. By default:

        * Assumes route_id as a relative path to a file in the data store.
        * Uses the format specified in the query to determine the file extension.
        * Attempts to resolve the associated index, and, if it doesn't exist, requests
          that it be built.
        * Generates the ticket response.

        Args:
            record_id: ID of the record for which to generate a ticket.
            query: Dict of query parameters.
            http_request_handler: The HTTPRequestHandler that called this
                ApiRouteHandler.
        """
        data_format = query.get('format', self.default_format)
        data_resource, index_resource = self.data_store.resolve(
            record_id, data_format, self.index_format
        )

        if data_resource in self._cache:
            ticket_str = self._cache[data_resource]
        else:
            if not index_resource.exists:
                self.create_index(data_resource, index_resource)
                self.data_store.add_resource(index_resource)
            ticket_urls = self.create_ticket_urls(
                data_format, query, data_resource, index_resource
            )
            ticket = dict(
                htsget=dict(
                    format=data_format.upper(),
                    urls=ticket_urls
                )
            )
            ticket_str = json.dumps(ticket)
            try:
                self._cache_lock.acquire()
                if data_resource not in self._cache:
                    self._cache[data_resource] = ticket_str
            finally:
                self._cache_lock.release()

        http_request_handler.send_response(HTTPStatus.OK)
        http_request_handler.send_header("Content-Type", OK_RESPONSE_CONTENT_TYPE)
        http_request_handler.end_headers()
        http_request_handler.wfile.write(ticket_str)

    @abstractmethod
    def create_index(self, data_resource, index_resource) -> None:
        pass

    def create_ticket_urls(
        self, data_format, query: dict, data_resource, index_resource
    ) -> Sequence[dict]:
        pass


class ReadsApiRouteHandler(ApiRouteHandler):
    @property
    def default_format(self) -> str:
        return "BAM"

    @property
    def index_format(self) -> str:
        return "BAI"

    def create_index(self, data_resource, index_resource) -> None:
        pass

    def handle(self, record_id, query, http_request_handler):
        pass


class VariantsApiRouteHandler(ApiRouteHandler):
    @property
    def default_format(self) -> str:
        return "VCF"

    @property
    def index_format(self) -> str:
        return "TBI"

    def create_index(self, data_resource, index_resource) -> None:
        pass

    def handle(self, record_id, query, http_request_handler):
        pass


class BlockRouteHandler(RouteHandler):
    def __call__(
        self, sub_route: Sequence[str], parsed_url: ParseResult,
        http_request_handler: "HtsgetHttpRequestHandler"
    ):
        pass


class HtsgetHttpRequestHandler(RoutingHttpRequestHandler):
    def check_headers(self):
        if "Accept" in self.headers:
            accept = self.headers["Accept"]
            if not accept.startswith("application/"):
                raise UnsupportedMediaTypeHttpError(accept)

            accept_app = accept[12:].lower()
            if accept_app == "json":
                pass
            elif (
                accept_app.startswith("vnd.ga4gh.htsget.v") and
                accept_app.endswith("+json")
            ):
                try:
                    version = tuple(int(v) for v in accept[18:-5].split("."))
                except:
                    raise UnsupportedMediaTypeHttpError(accept)

                if (
                    # TODO: support backwards compatibility
                    version < HTSGET_VERSION or
                    # Assume forward compatibility if the major version is the same
                    version[0] > HTSGET_VERSION[0]
                ):
                    raise UnsupportedMediaTypeHttpError(accept)
            else:
                raise UnsupportedMediaTypeHttpError(accept)

    def handle_error(self, err: HttpError):
        self.send_error(err.status)
        self.send_header("Content-type", ERROR_RESPONSE_CONTENT_TYPE)
        self.end_headers()
        error_dict = dict(
            htsget=dict(
                error=err.error_type,
                message=err.message
            )
        )
        self.wfile.write(json.dumps(error_dict))


class HtsgetHttpServer(RoutingServer):
    def __init__(self, **kwargs):
        super().__init__(request_handler_class=HtsgetHttpRequestHandler, **kwargs)


class HtsgetServerRunner(Runnable):
    def __init__(self):
        self.server = None

    def run(self, **kwargs):
        self.server = HtsgetHttpServer(**kwargs)

    def stop(self):
        self.server.server_close()


def create_default_router(data_store, block_size=DEFAULT_BLOCK_SIZE):
    router = Router()
    router.add_route(['reads'], ReadsApiRouteHandler(data_store, block_size))
    router.add_route(['variants'], VariantsApiRouteHandler(data_store, block_size))
    router.add_route(['block'], BlockRouteHandler())
    return router


def run(server_address=('localhost', DEFAULT_PORT), router=None):
    if router is None:
        router = create_default_router(DefaultDataStore())
    run_interruptible(
        HtsgetServerRunner(), server_address=server_address, router=router
    )
