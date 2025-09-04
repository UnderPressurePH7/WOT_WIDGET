# -*- coding: utf-8 -*-
import socket
import ssl
import threading
import time
import json
import base64
import os
import errno
import select
import Queue as queue
from .utils import print_error, print_debug

class WebSocketClient(object):

    def __init__(self, host, port=443, secure=True, api_key=None, secret_key=None, player_id=None, message_callback=None):
        self.host = host
        self.port = port
        self.secure = secure
        self.api_key = api_key
        self.secret_key = secret_key
        self.player_id = player_id
        self.message_callback = message_callback
        
        self.sock = None
        self.is_connected = False
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.sender_thread = None
        
        self.send_queue = queue.Queue(maxsize=100)
        self.ping_interval = 20.0

    def _build_url_parts(self):
        path = "/socket.io/?EIO=4&transport=websocket"
        if self.secret_key:
            path += "&secretKey=" + self.secret_key
        elif self.api_key:
            path += "&key=" + self.api_key
        if self.player_id:
            path += "&playerId=" + self.player_id
        return path

    def connect(self):
        try:
            addr_info = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)[0]
            sock = socket.socket(addr_info[0], addr_info[1], addr_info[2])
            
            if self.secure:
                self.sock = ssl.wrap_socket(sock, do_handshake_on_connect=False)
            else:
                self.sock = sock

            self.sock.setblocking(False)

            try:
                self.sock.connect(addr_info[4])
            except socket.error as e:
                if e.errno != errno.EINPROGRESS and e.errno != errno.EWOULDBLOCK:
                    raise

            self.stop_event.clear()
            self.worker_thread = threading.Thread(target=self._worker_loop)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            
        except Exception as e:
            print_error("[WS] Connection failed during setup: {}".format(e))
            self.close()

    def _perform_connect_and_handshake(self, timeout=10.0):
        deadline = time.time() + timeout
        
        # 1. Wait for TCP connection to be established
        _, write_socks, err_socks = select.select([], [self.sock], [self.sock], timeout)
        if not write_socks:
            raise socket.error("TCP Connection timeout")
        err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err != 0:
            raise socket.error("TCP Connection failed with error {}".format(err))

        # 2. Perform SSL Handshake if secure
        if self.secure:
            while time.time() < deadline:
                try:
                    self.sock.do_handshake()
                    break
                except ssl.SSLError as e:
                    if e.errno == ssl.SSL_ERROR_WANT_READ:
                        select.select([self.sock], [], [], deadline - time.time())
                    elif e.errno == ssl.SSL_ERROR_WANT_WRITE:
                        select.select([], [self.sock], [], deadline - time.time())
                    else:
                        raise
                except socket.error:
                    raise
            else:
                raise ssl.SSLError("SSL Handshake Timeout")

        # 3. Perform WebSocket Handshake
        key = base64.b64encode(os.urandom(16))
        path = self._build_url_parts()
        request = (
            "GET {path} HTTP/1.1\r\n"
            "Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(path=path, host=self.host, port=self.port, key=key)
        
        self.sock.send(request.encode('utf-8'))
        
        response = ""
        while time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
                if not chunk: break
                response += chunk.decode('utf-8')
                if "\r\n\r\n" in response:
                    break
            except socket.error as e:
                if e.errno != errno.EWOULDBLOCK: raise
                time.sleep(0.1)
        
        if "101 Switching Protocols" not in response:
            raise IOError("WebSocket Handshake failed: " + response.split('\r\n')[0])

    def _worker_loop(self):
        try:
            self._perform_connect_and_handshake()
        except Exception as e:
            print_error("[WS] Handshake/Connect process failed: {}".format(e))
            self.close()
            return
        
        if not self.sender_thread or not self.sender_thread.is_alive():
            self.sender_thread = threading.Thread(target=self._sender_loop)
            self.sender_thread.daemon = True
            self.sender_thread.start()
            
        buffer = bytearray()
        while not self.stop_event.is_set():
            try:
                r, _, _ = select.select([self.sock], [], [], 0.1)
                if not r:
                    continue
                
                chunk = self.sock.recv(8192)
                if not chunk:
                    break
                buffer.extend(chunk)
                
                while len(buffer) > 2:
                    opcode = buffer[0] & 0x0F
                    payload_len = buffer[1] & 0x7F
                    offset = 2
                    if payload_len == 126:
                        if len(buffer) < 4: break
                        payload_len = (buffer[2] << 8) | buffer[3]
                        offset = 4
                    elif payload_len == 127:
                        if len(buffer) < 10: break
                        payload_len = 0
                        for i in range(8):
                            payload_len = (payload_len << 8) | buffer[2 + i]
                        offset = 10
                    
                    if len(buffer) < offset + payload_len: break
                    payload = buffer[offset:offset + payload_len]
                    buffer = buffer[offset + payload_len:]
                    self._handle_frame(opcode, payload)
            except Exception:
                break
        self.close()

    def _handle_frame(self, opcode, payload):
        if opcode == 0x1: # TEXT
            msg = payload.decode('utf-8')
            if msg.startswith('0'):
                data = json.loads(msg[1:])
                self.ping_interval = float(data.get('pingInterval', 25000)) / 1000.0
                self.is_connected = True
                self.emit_raw('40')
            elif self.message_callback:
                self.message_callback(msg)
        elif opcode == 0x8: # CLOSE
            self.is_connected = False
        elif opcode == 0x9: # PING
            self._send_frame(0xA, payload)

    def _sender_loop(self):
        last_ping = time.time()
        while not self.stop_event.is_set():
            try:
                if self.is_connected:
                    if time.time() - last_ping > self.ping_interval:
                        self.emit_raw('2')
                        last_ping = time.time()
                try:
                    payload = self.send_queue.get(timeout=0.1)
                    if self.is_connected:
                        self._send_frame(0x1, payload)
                except queue.Empty:
                    continue
            except Exception:
                break
        self.close()

    def _send_frame(self, opcode, payload):
        if not self.sock: return
        header = bytearray()
        header.append(0x80 | opcode)
        
        if isinstance(payload, unicode):
            payload = payload.encode('utf-8')

        length = len(payload)
        mask = bytearray(os.urandom(4))
        
        if length <= 125:
            header.append(length | 0x80)
        elif length <= 65535:
            header.append(126 | 0x80)
            header.append((length >> 8) & 0xFF)
            header.append(length & 0xFF)
        else:
            header.append(127 | 0x80)
            for i in range(8):
                header.append((length >> (56 - i * 8)) & 0xFF)
        
        masked_payload = bytearray(payload)
        for i in range(len(masked_payload)):
            masked_payload[i] ^= mask[i % 4]
        
        self.sock.sendall(header + mask + masked_payload)

    def emit(self, event, data):
        try:
            payload = '42' + json.dumps([event, data])
            self.send_queue.put(payload, timeout=0.1)
        except queue.Full:
            print_error("[WS] Send queue is full")

    def emit_raw(self, payload):
        try:
            self.send_queue.put(payload, timeout=0.1)
        except queue.Full:
            print_error("[WS] Send queue is full")

    def close(self):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        self.is_connected = False
        
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            finally:
                self.sock = None