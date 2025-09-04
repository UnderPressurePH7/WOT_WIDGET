import BigWorld
from .server_connect import ServerClient

__all__ = [
    'g_serverClient',
    'ServerClient'
]

g_serverClient = ServerClient()