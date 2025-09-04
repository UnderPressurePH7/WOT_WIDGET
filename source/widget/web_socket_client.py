# -*- coding: utf-8 -*-
import socket
import ssl
import threading
import time
import base64
import hashlib
import os
import json

from .utils import print_error, print_debug


class WebSocketClient(object):
    def __init__(self, host, port=443, secure=True,
                 api_key=None, secret_key=None, player_id=None,
                 message_callback=None):

        self.host = host
        self.port = int(port)
        self.secure = bool(secure)

        self.api_key = api_key
        self.secret_key = secret_key
        self.player_id = player_id

        self.message_callback = message_callback

        self.sock = None
        self.ssl_sock = None
        self.is_connected = False

        self._recv_thread = None
        self._stop = threading.Event()

        self._ping_interval = 20
        self._last_ping = 0

    def _handshake(self):
        key = base64.b64encode(os.urandom(16))
        path = "/socket.io/?EIO=4&transport=websocket"

        headers = [
            "GET {} HTTP/1.1".format(path),
            "Host: {}".format(self.host),
            "Upgrade: websocket",
            "Connection: Upgrade",
            "Sec-WebSocket-Key: {}".format(key),
            "Sec-WebSocket-Version: 13",
            "\r\n"
        ]
        req = "\r\n".join(headers)
        self.ssl_sock.sendall(req.encode("utf-8"))

        resp = self.ssl_sock.recv(4096)
        if b"101 Switching Protocols" not in resp:
            raise Exception("WebSocket handshake failed: {}".format(resp))

    def connect(self):
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.settimeout(10.0)
        if self.secure:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self.ssl_sock = context.wrap_socket(raw_sock, server_hostname=self.host)
        else:
            self.ssl_sock = raw_sock
        self.ssl_sock.connect((self.host, self.port))

        self._handshake()
        self.is_connected = True
        self._stop.clear()

        self._recv_thread = threading.Thread(target=self._recv_loop)
        self._recv_thread.daemon = True
        self._recv_thread.start()

        self._send_raw("40")


    def _encode_ws_frame(self, data):
        payload = data.encode("utf-8")
        b1 = 0x81

        length = len(payload)
        if length < 126:
            header = bytearray([b1, 0x80 | length])
        elif length <= 0xFFFF:
            header = bytearray([b1, 0x80 | 126]) + bytearray([(length >> 8) & 0xFF, length & 0xFF])
        else:
            header = bytearray([b1, 0x80 | 127]) + bytearray([(length >> (8 * i)) & 0xFF for i in range(7, -1, -1)])

        mask = os.urandom(4)
        header.extend(mask)

        masked_payload = bytearray([payload[i] ^ mask[i % 4] for i in range(length)])
        return header + masked_payload

    def _send_raw(self, data):
        if not self.is_connected:
            return
        try:
            frame = self._encode_ws_frame(data)
            self.ssl_sock.sendall(frame)
        except Exception as e:
            print_error("[WS] send_raw error: {}".format(e))
            self.close()


    def emit(self, event, data=None):
        try:
            arr = [event]
            if data is not None:
                arr.append(data)
            payload = "42" + json.dumps(arr, ensure_ascii=False)
            self._send_raw(payload)
        except Exception as e:
            print_error("[WS] emit error: {}".format(e))

    def _decode_ws_frame(self, data):
        if len(data) < 2:
            return None, data

        b1 = ord(data[0])
        b2 = ord(data[1])
        fin = b1 & 0x80
        opcode = b1 & 0x0F
        masked = b2 & 0x80
        length = b2 & 0x7F

        idx = 2
        if length == 126:
            if len(data) < 4:
                return None, data
            length = (ord(data[2]) << 8) | ord(data[3])
            idx = 4
        elif length == 127:
            if len(data) < 10:
                return None, data
            length = 0
            for i in range(8):
                length = (length << 8) | ord(data[2 + i])
            idx = 10

        if masked:
            mask = map(ord, data[idx:idx + 4])
            idx += 4
        else:
            mask = None

        if len(data) < idx + length:
            return None, data

        payload = data[idx:idx + length]
        rest = data[idx + length:]

        if masked:
            payload = "".join(chr(ord(payload[i]) ^ mask[i % 4]) for i in range(length))

        if opcode == 1: 
            return payload, rest
        else:
            return None, rest

    def _recv_loop(self):
        buf = ""
        try:
            while not self._stop.is_set() and self.is_connected:
                chunk = self.ssl_sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while True:
                    msg, buf = self._decode_ws_frame(buf)
                    if msg is None:
                        break
                    self._handle_message(msg)

        except Exception as e:
            print_error("[WS] recv_loop error: {}".format(e))
        finally:
            self.close()


    def _handle_message(self, msg):
        if msg == "2":
            self._send_raw("3")
            return
        if msg == "3":
            return

        if self.message_callback:
            try:
                self.message_callback(msg)
            except Exception as e:
                print_error("[WS] message_callback error: {}".format(e))


    def close(self):
        self._stop.set()
        if self.is_connected:
            try:
                self.ssl_sock.close()
            except:
                pass
        self.is_connected = False


