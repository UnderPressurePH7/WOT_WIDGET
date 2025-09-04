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
        self.worker_thread = None
        self.sender_thread = None
        
        self.connected = False
        self.stop_event = threading.Event()
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
        
        self.ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        self.worker_thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={'sslopt': {"cert_reqs": ssl.CERT_NONE}}
        )
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def _on_open(self, ws):
        print_debug("[WS] Connection opened")

        
    def _on_message(self, ws, msg):
        if msg.startswith("0"):  
            try:
                data = json.loads(msg[1:])
                self.ping_interval = int(data.get("pingInterval", 25000)) / 1000.0
                self.ping_timeout = int(data.get("pingTimeout", 5000)) / 1000.0
                print_debug("[WS] Handshake ok, sid={}, ping={}s".format(data.get('sid'), self.ping_interval))
                
                ws.send("40")
                print_debug("[WS] Namespace connect sent")

                self.connected = True
                self.stop_event.clear()
                self.sender_thread = threading.Thread(target=self._sender_loop)
                self.sender_thread.daemon = True
                self.sender_thread.start()
            except Exception as e:
                print_error("[WS] Failed to parse handshake: {} ({})".format(msg, e))

        elif msg == "3":  
            return
        
        elif msg.startswith("42"): 
            try:
                arr = json.loads(msg[2:])
                event = arr[0]
                data = arr[1] if len(arr) > 1 else None
                print_debug("[WS] <- event={}, data={}".format(event, data))
            except Exception as e:
                print_error("[WS] Failed to parse event: {} ({})".format(msg, e))

        elif msg.startswith("40"):
            print_debug("[WS] Server confirmed namespace connect")

        else:
            print_debug("[WS] <- raw: {}".format(msg))
    
    def _on_error(self, ws, error):
        print_error("[WS] Connection error: {}".format(error))
        self.connected = False
        self.stop_event.set()

    def _on_close(self, ws, close_status_code, close_msg):
        print_debug("[WS] Connection closed")
        self.connected = False
        self.stop_event.set()

    def _sender_loop(self):
        last_ping = time.time()
        while not self.stop_event.is_set():
            try:
                if time.time() - last_ping > self.ping_interval:
                    self.ws.send("2")
                    last_ping = time.time()

                try:
                    event, data = self.queue.get(timeout=0.1)
                    payload = '42{}'.format(json.dumps([event, data]))
                    if len(payload) > MAX_PAYLOAD_SIZE:
                        print_error("[WS] Payload too big, skipped")
                        continue
                    self.ws.send(payload)
                    print_debug("[WS] -> emit {}".format(event))
                except queue.Empty:
                    continue
            except Exception as e:
                print_error("[WS] Sender loop error: {}".format(e))
                self.disconnect() 
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
        if self.ws:
            self.ws.close()