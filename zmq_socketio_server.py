#!/usr/bin/env python
""" ZeroMQ to Socket.IO Bridge """
# based on https://github.com/abourget/gevent-socketio/blob/master/examples/live_cpu_graph/live_cpu_graph/serve.py

from gevent import monkey
monkey.patch_all()
import gevent

from gevent_zeromq import zmq

from socketio import socketio_manage
from socketio.server import SocketIOServer
from socketio.namespace import BaseNamespace
from socketio.mixins import BroadcastMixin

from urlparse import parse_qs

import zmq_cmd

WEB_ROOT = "webroot/"

# Map Socket.IO 'service' query parameter to ZeroMQ socket address:
# TODO: Make this configurable...
SERVICE_MAP = {
    'test1' : 'tcp://127.0.0.1:1234'
}

class ZMQSubNamespace(BaseNamespace, BroadcastMixin):
    def send_output(self, msg):
        self.emit("output", {"data": msg})

    def recv_connect(self):
        qs = parse_qs(self.environ['QUERY_STRING'])
        service = qs.get('service',[None,])[0]

        zmq_addr = SERVICE_MAP.get(service, None)
        if not zmq_addr:
            self.send_output("Error: Unknown service '%s'\n" % (service,));
            return

        self.send_output("Connected to %s\n" % zmq_addr)

        def send_zmq_subscriber_output():
            ctx = zmq.Context()
            sock = ctx.socket(zmq.SUB)
            sock.setsockopt(zmq.SUBSCRIBE, zmq_cmd.OUTPUT_TOPIC)
            sock.connect(zmq_addr)
            done = False
            while not done:
                data = sock.recv()
                topic, message = data.split(" ", 1)
                if topic == zmq_cmd.OUTPUT_TOPIC:
                    if message == '':
                        self.send_output(">>> end of output <<<\n\n")
                    else:
                        self.send_output(message.replace("\r",""))   
                
        self.spawn(send_zmq_subscriber_output)

class WebApp(object):
    def __init__(self):
        self.buffer = []

    def __call__(self, environ, start_response):
        path = environ['PATH_INFO'].strip('/') or 'index.html'
        if path.find('../') != -1:
            return not_found(start_response)

        if path.startswith('static/') or path == 'index.html':
            print "reading: %s" % (WEB_ROOT + path)
            try:
                data = open(WEB_ROOT + path).read()
            except Exception:
                return not_found(start_response)

            if path.endswith(".js"):
                content_type = "text/javascript"
            elif path.endswith(".css"):
                content_type = "text/css"
            elif path.endswith(".swf"):
                content_type = "application/x-shockwave-flash"
            else:
                content_type = "text/html"

            start_response('200 OK', [('Content-Type', content_type)])
            return [data]

        if path.startswith("socket.io"):
            socketio_manage(environ, {'/zmq': ZMQSubNamespace})
        else:
            return not_found(start_response)


def not_found(start_response):
    start_response('404 Not Found', [])
    return ['<h1>Not Found</h1>']

if __name__ == '__main__':
    print 'Listening on port http://0.0.0.0:8080 and on port 10843 (flash policy server)'
    SocketIOServer(('0.0.0.0', 8080), WebApp(),
        resource="socket.io", policy_server=True,
        policy_listener=('0.0.0.0', 10843)).serve_forever()

