from tornado import gen
from web_consumer import WebConsumer
import json
import logging
import traceback
import os.path

from runtime_config import RuntimeConfig

import ssl
import sys
import uuid

import mongomock
import nest_asyncio
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket

from tornado.options import define, options

nest_asyncio.apply()

tornado.options.define("port", default=8001, help="server port", type=int)
tornado.options.define("host", default="0.0.0.0", help="host address to bind", type=str)
tornado.options.define("env", default="local", help="set runtime setup (env.[runtime].json)", type=str)
tornado.options.define("encrypt", default=False, help="start with built in certificates", type=bool)
tornado.options.define("password", default="", help="certificate key", type=str)

class DefaultHandler(tornado.web.RequestHandler):

    def initialize(self, ctx) -> None:
        self.ctx = ctx

    def get(self):
        self.render("blank.html", messages=0)
    
    def post(self):
        try:
            request = json.loads(self.request.body)
            print(request)
        except Exception as e:
            print("{}".format(e))

        self.write(json.dumps({}))
        self.finish()


class Application(tornado.web.Application):

    def __init__(self, config,):

        handlers = [
                (r"/", DefaultHandler, dict(ctx=self)),
                (r"/api/graphql", DefaultHandler, dict(ctx=self)),
        ]

        settings = dict(
            cookie_secret="312c04aa-2254-400c-82b5-2b7cf2fd794b",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            login_url="/login",
            xsrf_cookies=False,
        )

        self.config = config
        self._registery = []

        self._rpc_proxy = WebConsumer('amqp://{}:{}@{}:{}/'.format(
            config.get("rabbitmq", "user"),
            config.get("rabbitmq", "password"),
            config.get("rabbitmq", "host"),
            config.get("rabbitmq", "port"),
        ),'web-server')

        super().__init__(handlers, **settings)

    def run(self):
        self._rpc_proxy.run()

def main():
    tornado.options.parse_command_line()

    runtime = RuntimeConfig('./env.{}.json'.format(options.env))

    app = Application(runtime)

    if options.encrypt:
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        password = options.password or None
        ssl_ctx.load_cert_chain('./keys/host.cert', './keys/host.key', password)

        server = tornado.httpserver.HTTPServer(app, ssl_options=ssl_ctx)
    else:
        server = tornado.httpserver.HTTPServer(app)

    server = tornado.httpserver.HTTPServer(app)
    server.listen(
        runtime.get('server', 'port', options.port), 
        runtime.get('server', 'host', options.host))

    app.run()

if __name__ == "__main__":
    main()
