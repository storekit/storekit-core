import json
import logging
import uuid
import pika

from pika.adapters.tornado_connection import TornadoConnection
from tornado import gen
from tornado.concurrent import Future

LOG_FORMAT = ('%(asctime)s  %(name)s  %(levelname)s: %(message)s')
LOGGER= logging.getLogger(__name__)


class WebConsumer(object):


    def __init__(self, amqp_url, name):

        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self._url = amqp_url
        self._event_exchange = "{}_events".format(name)
        self._rpc_exchange = "{}_rpc".format(name)
        self._dl_exchange = "{}_dl".format(name)
        self._dl_queue = "{}_dead_letters".format(name)
        self._name = name
        self._jobs = {}

    def connect(self):

        return TornadoConnection(
            pika.URLParameters(self._url),
            self.on_connection_open,
        )

    def close_connection(self):

        self._connection.close()

    def add_on_connection_close_callback(self):

        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reason):

        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            self._connection.ioloop.call_later(5, self.reconnect)

    def on_connection_open(self, unused_connection):

        self.add_on_connection_close_callback()
        self.open_channel()

    def reconnect(self):

        if not self._closing:

            # Create a new connection
            self._connection = self.connect()

    def add_on_channel_close_callback(self):

        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reason):

        self._connection.close()

    def on_channel_open(self, channel):

        logging.info('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange()

    def setup_exchange(self):

        self._channel.exchange_declare(
            exchange=self._event_exchange,
            exchange_type='topic',
            durable=True)

        self._channel.exchange_declare(
            exchange=self._rpc_exchange,
            callback=self.on_rpc_exchange_declareok,
            exchange_type='direct',
            durable=True)

        self._channel.exchange_declare(
            exchange=self._dl_exchange,
            exchange_type='fanout',
            durable=True)

        self._channel.queue_declare(queue=self._dl_queue)
        self._channel.queue_bind(self._dl_queue, self._dl_exchange)


    def on_rpc_exchange_declareok(self, unused_frame):
        self.setup_queue(self._name)

    def setup_queue(self, queue_name):

        self.result = self._channel.queue_declare(
            queue="{}-requests".format(queue_name),
            callback=self.on_queue_declareok,
            durable=True
        )

        self.result = self._channel.queue_declare(
            queue="{}-response".format(queue_name),
            durable=True
        )


    def on_queue_declareok(self, method_frame):
        self._channel.queue_bind(
            queue="{}-requests".format(self._name),
            exchange=self._rpc_exchange,
            routing_key=self._name,
            callback=self.on_bindok,
        )

    def add_on_cancel_callback(self):

        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):

        if self._channel:
            self._channel.close()

    def acknowledge_message(self, delivery_tag):

        self._channel.basic_ack(delivery_tag)

    def on_message(self, unused_channel, basic_deliver, properties, body):

        if properties.correlation_id in self._jobs:
            pending = self._jobs.pop(properties.correlation_id)
            pending.set_result(json.loads(body))

        self.acknowledge_message(basic_deliver.delivery_tag)

    
    @gen.coroutine
    def send_message(self, message):

        pending = Future()
        message_id = uuid.uuid4().hex

        props = {
            'message_type': 'request',
        }


        basic = pika.BasicProperties(
            content_type="application/json",
            correlation_id=message_id,
            headers=props
        )

        self._jobs[message_id] = pending

        self._channel.basic_publish(
            exchange='web_rpc',
            routing_key=message['service'], body=json.dumps(message['args']),
            properties=basic,
            mandatory=True
        )

        resp = yield pending

        logging.info("type: {}".format(type(resp)))

        raise gen.Return(resp)

    def on_cancelok(self, unused_frame):

        self.close_channel()

    def stop_consuming(self):

        if self._channel:
            self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def start_consuming(self):

        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(
            on_message_callback=self.on_message,
            queue='{}-requests'.format(self._name),
            auto_ack=False
        )

    def on_bindok(self, unused_frame):

        self.start_consuming()

    def close_channel(self):

        self._channel.close()

    def open_channel(self):

        self._connection.channel(on_open_callback=self.on_channel_open)

    def run(self):

        self._connection = self.connect()
        self._connection.ioloop.start()

    def stop(self):

        self._closing = True
        self.stop_consuming()
        self._connection.ioloop.start()
        logging.info('Stopped')

