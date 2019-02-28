
import functools
import logging
import threading

from flask import request, session
from flask_socketio import Namespace, disconnect, emit

from assemblyline.common import forge
from assemblyline.remote.datatypes.hash import Hash

classification = forge.get_classification()
config = forge.get_config()
datastore = forge.get_datastore()

KV_SESSION = Hash("flask_sessions",
                  host=config.core.redis.nonpersistent.host,
                  port=config.core.redis.nonpersistent.port,
                  db=config.core.redis.nonpersistent.db)
LOGGER = logging.getLogger('assemblyline.ui.socketio')


def authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        self = args[0]
        user_info = self.connections.get(get_request_id(request), None)
        if not user_info:
            disconnect()
        else:
            kwargs['user_info'] = user_info
            return f(*args, **kwargs)

    return wrapped


class SecureNamespace(Namespace):
    def __init__(self, namespace=None):
        self.connections_lock = threading.RLock()
        self.connections = {}
        super().__init__(namespace=namespace)

    def on_connect(self):
        info = get_user_info(request, session)

        if info.get('uname', None) is None:
            return

        sid = get_request_id(request)

        with self.connections_lock:
            self.connections[sid] = info

        LOGGER.info(f"SocketIO:{self.namespace} - {info['display']} - "
                    f"New connection establish from: {info['ip']}")

    def on_disconnect(self):
        sid = get_request_id(request)
        with self.connections_lock:
            if sid in self.connections:
                info = self.connections[get_request_id(request)]
                LOGGER.info(f"SocketIO:{self.namespace} - {info['display']} - "
                            f"User disconnected from: {info['ip']}")

            self.connections.pop(sid, None)
            self._extra_cleanup(sid)

    def _extra_cleanup(self, sid):
        pass


def get_request_id(request_p):
    if hasattr(request_p, "sid"):
        return request_p.sid
    return None


def get_user_info(request_p, session_p):
    src_ip = request_p.headers.get("X-Forward-For", request_p.remote_addr)
    sid = get_request_id(request_p)
    uname = None
    current_session = KV_SESSION.get(session_p.get("session_id", None))
    if current_session:
        if request_p.headers.get("X-Forward-For", None) == current_session.get('ip', None) and \
                request_p.headers.get("User-Agent", None) == current_session.get('user_agent', None):
            uname = current_session['username']

    user_classification = None
    if uname:
        user = datastore.user.get(uname, as_obj=False)
        if user:
            user_classification = user.get('classification', None)
    # TODO: Fake user
    else:
        uname = "FAKE"
        user_classification = classification.RESTRICTED

    return {
        'uname': uname,
        'display': f"{uname}({sid[:4]})",
        'classification': user_classification,
        'ip': src_ip,
        'sid': sid
    }
