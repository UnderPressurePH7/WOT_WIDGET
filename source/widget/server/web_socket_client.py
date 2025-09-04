# -*- coding: utf-8 -*-
import socket
import ssl
import threading
import time
import base64
import hashlib
import os
import json

try:
    unicode
except NameError:
    unicode = str

from ..utils import print_error, print_debug


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
        self.connection_lock = threading.Lock()

        self._recv_thread = None
        self._stop = threading.Event()

        self._ping_interval = 20
        self._last_ping = 0

    def _handshake(self):
        key = base64.b64encode(os.urandom(16))
        if isinstance(key, bytes):
            key = key.decode('ascii')
        
        params = []
        if self.api_key:
            params.append("key={}".format(self.api_key))
        if self.secret_key:
            params.append("secretKey={}".format(self.secret_key))
        if self.player_id:
            params.append("playerId={}".format(self.player_id))
        
        query_string = "&".join(params)
        path = "/socket.io/?EIO=4&transport=websocket"
        if query_string:
            path += "&{}".format(query_string)

        headers = [
            "GET {} HTTP/1.1".format(path),
            "Host: {}".format(self.host),
            "Upgrade: websocket", 
            "Connection: Upgrade",
            "Sec-WebSocket-Key: {}".format(key),
            "Sec-WebSocket-Version: 13",
            "",
            ""
        ]
        req = "\r\n".join(headers)
        
        try:
            if isinstance(req, unicode):
                req = req.encode("utf-8")
            self.ssl_sock.sendall(req)
            print_debug("[WS] Handshake request sent with auth params")
            
            response_data = ""
            while "\r\n\r\n" not in response_data:
                chunk = self.ssl_sock.recv(1024)
                if not chunk:
                    raise Exception("Connection closed during handshake")
                if isinstance(chunk, bytes):
                    chunk = chunk.decode("utf-8", errors='ignore')
                response_data += chunk
            
            print_debug("[WS] Handshake response received")
            
            if "101 Switching Protocols" not in response_data:
                raise Exception("WebSocket handshake failed")
                
            print_debug("[WS] Handshake successful")
            
        except Exception as e:
            print_error("[WS] Handshake error: {}".format(e))
            raise

    def connect(self):
        with self.connection_lock:
            if self.is_connected:
                print_debug("[WS] Already connected")
                return
                
            try:
                print_debug("[WS] Attempting to connect to {}:{}".format(self.host, self.port))
                
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_sock.settimeout(30.0)
                
                print_debug("[WS] Connecting raw socket...")
                raw_sock.connect((self.host, self.port))
                print_debug("[WS] Raw socket connected")
                
                if self.secure:
                    print_debug("[WS] Wrapping with SSL...")
                    try:
                        self.ssl_sock = ssl.wrap_socket(
                            raw_sock,
                            ssl_version=ssl.PROTOCOL_SSLv23,
                            cert_reqs=ssl.CERT_NONE
                        )
                        print_debug("[WS] SSL wrap successful")
                    except Exception as ssl_error:
                        print_error("[WS] SSL wrap failed: {}".format(ssl_error))
                        try:
                            raw_sock.close()
                        except:
                            pass
                        raise ssl_error
                else:
                    self.ssl_sock = raw_sock
                
                print_debug("[WS] Starting handshake...")
                self._handshake()
                
                self.is_connected = True
                self._stop.clear()

                self._recv_thread = threading.Thread(target=self._recv_loop)
                self._recv_thread.daemon = True
                self._recv_thread.start()

                time.sleep(0.2)
                self._send_raw("40")
                print_debug("[WS] Connection established successfully")
                
            except Exception as e:
                print_error("[WS] Connection failed: {}".format(e))
                self._cleanup_connection()
                raise

    def _cleanup_connection(self):
        self.is_connected = False
        if self.ssl_sock:
            try:
                self.ssl_sock.close()
            except:
                pass
            self.ssl_sock = None

    def _encode_ws_frame(self, data):
        if isinstance(data, unicode):
            payload = data.encode("utf-8")
        else:
            payload = str(data)
            
        b1 = 0x81
        payload_len = len(payload)
        
        if payload_len < 126:
            header = chr(b1) + chr(0x80 | payload_len)
        elif payload_len <= 0xFFFF:
            header = chr(b1) + chr(0x80 | 126) + chr((payload_len >> 8) & 0xFF) + chr(payload_len & 0xFF)
        else:
            header = chr(b1) + chr(0x80 | 127)
            for i in range(7, -1, -1):
                header += chr((payload_len >> (8 * i)) & 0xFF)

        mask = os.urandom(4)
        header += mask

        masked_payload = ""
        for i in range(len(payload)):
            if isinstance(payload, str):
                byte_val = ord(payload[i])
            else:
                byte_val = payload[i]
            masked_byte = byte_val ^ ord(mask[i % 4])
            masked_payload += chr(masked_byte)

        return header + masked_payload

    def _send_raw(self, data):
        if not self.is_connected or not self.ssl_sock:
            print_debug("[WS] Cannot send - not connected")
            return False
            
        try:
            frame = self._encode_ws_frame(data)
            if isinstance(frame, unicode):
                frame = frame.encode('latin1')
            self.ssl_sock.sendall(frame)
            print_debug("[WS] Sent: {}".format(data[:50]))
            return True
        except Exception as e:
            print_error("[WS] send_raw error: {}".format(e))
            self.close()
            return False

    def emit(self, event, data=None):
        try:
            arr = [event]
            if data is not None:
                arr.append(data)
            payload = "42" + json.dumps(arr, ensure_ascii=False)
            return self._send_raw(payload)
        except Exception as e:
            print_error("[WS] emit error: {}".format(e))
            return False

    def _decode_ws_frame(self, data):
        if len(data) < 2:
            return None, data

        try:
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
                if len(data) < idx + 4:
                    return None, data
                mask = [ord(data[idx + i]) for i in range(4)]
                idx += 4
            else:
                mask = None

            if len(data) < idx + length:
                return None, data

            payload_bytes = data[idx:idx + length]
            rest = data[idx + length:]

            if masked and mask:
                payload = ""
                for i in range(length):
                    byte_val = ord(payload_bytes[i])
                    payload += chr(byte_val ^ mask[i % 4])
            else:
                payload = payload_bytes

            if opcode == 1:
                return payload, rest
            elif opcode == 8:
                print_debug("[WS] Received close frame")
                self.close()
                return None, rest
            else:
                return None, rest
                
        except Exception as e:
            print_error("[WS] Frame decode error: {}".format(e))
            return None, data

    def _recv_loop(self):
        buf = ""
        print_debug("[WS] Receive loop started")
        
        try:
            while not self._stop.is_set() and self.is_connected:
                try:
                    chunk = self.ssl_sock.recv(4096)
                    if not chunk:
                        print_debug("[WS] Connection closed by server")
                        break
                    
                    if isinstance(chunk, bytes):
                        chunk = chunk.decode('latin1', errors='ignore')
                    
                    buf += chunk
                    
                    while True:
                        msg, buf = self._decode_ws_frame(buf)
                        if msg is None:
                            break
                        self._handle_message(msg)

                except socket.timeout:
                    continue
                except Exception as e:
                    print_error("[WS] Recv error: {}".format(e))
                    break
                    
        except Exception as e:
            print_error("[WS] recv_loop critical error: {}".format(e))
        finally:
            print_debug("[WS] Receive loop ended")
            self._cleanup_connection()

    def _handle_message(self, msg):
        try:
            if msg == "2":
                self._send_raw("3")
                return
            if msg == "3":
                return

            if self.message_callback:
                self.message_callback(msg)
                
        except Exception as e:
            print_error("[WS] message_callback error: {}".format(e))

    def close(self):
        print_debug("[WS] Closing connection...")
        self._stop.set()
        
        with self.connection_lock:
            if self.is_connected:
                self.is_connected = False
                try:
                    if self.ssl_sock:
                        self.ssl_sock.close()
                except:
                    pass
                self.ssl_sock = None
            
        print_debug("[WS] Connection closed")