
import logging

from flask_socketio import emit, join_room

from al_ui.socketio.base import LOGGER, SecureNamespace, authenticated_only
from assemblyline.common import forge
from assemblyline.remote.datatypes.queues.comms import CommsQueue


config = forge.get_config()
classification = forge.get_classification()

AUDIT = config.ui.audit
AUDIT_LOG = logging.getLogger('assemblyline.ui.audit')


class SubmissionMonitoringNamespace(SecureNamespace):
    def __init__(self, namespace=None):
        self.background_task_started = False
        super().__init__(namespace=namespace)

    # noinspection PyBroadException
    def monitor_submissions(self, user_info):
        sid = user_info['sid']
        q = CommsQueue('submissions', private=True)
        try:
            for msg in q.listen():
                if sid not in self.connections:
                    break

                submission = msg['msg']
                msg_type = msg['msg_type']
                if classification.is_accessible(user_info['classification'],
                                                submission.get('classification', classification.UNRESTRICTED)):
                    self.socketio.emit(msg_type, submission, room=sid, namespace=self.namespace)
                    LOGGER.info(f"SocketIO:{self.namespace} - {user_info['display']} - "
                                f"Sending {msg_type} event for submission matching ID: {submission['sid']}")
                    if AUDIT:
                        AUDIT_LOG.info(
                            f"{user_info['uname']} [{user_info['classification']}]"
                            f" :: SubmissionMonitoringNamespace.get_submission(sid={submission['sid']})")
        except Exception:
            LOGGER.exception(f"SocketIO:{self.namespace} - {user_info['display']}")
        finally:
            LOGGER.info(f"SocketIO:{self.namespace} - {user_info['display']} - "
                        f"Connection to client was terminated")
            if AUDIT:
                AUDIT_LOG.info(f"{user_info['uname']} [{user_info['classification']}]"
                               f" :: SubmissionMonitoringNamespace.on_submission(stop)")

    @authenticated_only
    def on_submission(self, data, user_info):

        LOGGER.info(f"SocketIO:{self.namespace} - {user_info['display']} - "
                    f"User as started monitoring submissions...")
        if AUDIT:
            AUDIT_LOG.info(f"{user_info['uname']} [{user_info['classification']}]"
                           f" :: SubmissionMonitoringNamespace.on_submission(start)")

        join_room(user_info['sid'])
        self.socketio.start_background_task(target=self.monitor_submissions, user_info=user_info)
        emit('monitoring', data, room=user_info['sid'], namespace=self.namespace)
