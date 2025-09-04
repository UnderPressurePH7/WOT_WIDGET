# -*- coding: utf-8 -*-
import websocket
import threading
import json
import time
import ssl
import Queue as queue 
from .utils import print_error, print_debug

MAX_PAYLOAD_SIZE = 2 * 1024 * 1024


class WebSocketClient(object):  
    def __init__(self, host, port=443, secure=True, api_key=None, secret_key=None, player_id=None):
        self.host = host
        self.port = port
        self.secure = secure
        self.api_key = api_key
        self.secret_key = secret_key
        self.player_id = player_id

        self.ws = None
        self.connected = False
        self.stop_event = threading.Event()
        self.sender_thread = None
        self.recv_thread = None
        self.queue = queue.Queue(maxsize=100)

        self.ping_interval = 25
        self.ping_timeout = 5

    def _build_url(self):
        scheme = "wss" if self.secure else "ws"
        query = "EIO=4&transport=websocket"
        if self.secret_key:
            query += "&secretKey={}".format(self.secret_key)
        elif self.api_key:
            query += "&key={}".format(self.api_key)
        if self.player_id:
            query += "&playerId={}".format(self.player_id)
        return "{}://{}:{}/socket.io/?{}".format(scheme, self.host, self.port, query)

    def connect(self):
        url = self._build_url()
        print_debug("[WS] Connecting to {}".format(url))
        self.ws = websocket.WebSocket()
        try:
            self.ws.connect(url, sslopt={"cert_reqs": ssl.CERT_NONE})
            self.connected = True
            print_debug("[WS] TCP connection established")

            open_packet = self.ws.recv()
            if open_packet.startswith("0"):
                data = json.loads(open_packet[1:])
                self.ping_interval = int(data.get("pingInterval", 25000)) / 1000.0
                self.ping_timeout = int(data.get("pingTimeout", 5000)) / 1000.0
                print_debug("[WS] Handshake ok, sid={}, ping={}s".format(data.get('sid'), self.ping_interval))

            self.ws.send("40")
            print_debug("[WS] Namespace connected")

            self.stop_event.clear()
            
            self.sender_thread = threading.Thread(target=self._sender_loop)
            self.sender_thread.daemon = True  
            
            self.recv_thread = threading.Thread(target=self._recv_loop)
            self.recv_thread.daemon = True
            
            self.sender_thread.start()
            self.recv_thread.start()

        except Exception as e:
            print_error("[WS] Connection error: {}".format(e))
            self.connected = False
            self.ws = None

    def _sender_loop(self):
        last_ping = time.time()
        while not self.stop_event.is_set():
            try:
                # ping
                if time.time() - last_ping > self.ping_interval:
                    self.ws.send("2")  # ping
                    last_ping = time.time()

                # send queued messages
                try:
                    event, data = self.queue.get(timeout=0.1)
                    payload = '42{}'.format(json.dumps([event, data]))
                    # У Python 2 str - це вже байти, encode не потрібен
                    if len(payload) > MAX_PAYLOAD_SIZE:
                        print_error("[WS] Payload too big, skipped")
                        continue
                    self.ws.send(payload)
                    print_debug("[WS] -> emit {}".format(event))
                except queue.Empty:
                    continue
            except Exception as e:
                print_error("[WS] Sender loop error: {}".format(e))
                self.connected = False
                break

    def _recv_loop(self):
        while not self.stop_event.is_set() and self.connected:
            try:
                msg = self.ws.recv()
                if msg == "3":
                    # pong
                    continue
                elif msg.startswith("42"):
                    try:
                        arr = json.loads(msg[2:])
                        event = arr[0]
                        data = arr[1] if len(arr) > 1 else None
                        print_debug("[WS] <- event={}, data={}".format(event, data))
                    except Exception as e:
                        print_error("[WS] Failed to parse 42 message: {} ({})".format(msg, e))
                elif msg.startswith("0"):
                    print_debug("[WS] server handshake: {}".format(msg))
                elif msg.startswith("40"):
                    print_debug("[WS] server confirmed namespace connect")
                elif msg.startswith("41"):
                    print_debug("[WS] server disconnected namespace")
                else:
                    print_debug("[WS] <- raw: {}".format(msg))
            except Exception as e:
                print_error("[WS] Receiver loop error: {}".format(e))
                self.connected = False
                break

    def emit(self, event, data):
        if not self.connected:
            print_error("[WS] Not connected, cannot emit")
            return
        try:
            self.queue.put((event, data), timeout=0.1)
        except queue.Full:
            print_error("[WS] Local send queue full, dropping")

    def disconnect(self):
        print_debug("[WS] Disconnecting...")
        self.stop_event.set()
        try:
            if self.ws:
                self.ws.send("41")
                self.ws.close()
        except Exception:
            pass
        self.connected = False