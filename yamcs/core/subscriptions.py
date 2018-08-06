from __future__ import absolute_import

import threading

import websocket
from yamcs.core.exceptions import ConnectionFailure


class WebSocketSubscriptionManager(object):

    def __init__(self, client, subscription):
        self._client = client
        self._subscription = subscription

        self._websocket = None
        self._callback = None
        self._close_callbacks = []

        self._closing = threading.Lock()
        self._closed = False
        """True if this manager has already been closed."""

        # Thread created in ``.open()``
        self._consumer = None

    def add_close_callback(self, callback):
        """
        Schedules a callable when the manager closes.
        """
        self._close_callbacks.append(callback)

    def open(self, callback):
        """
        Begin consuming messages.
        """
        assert not self._closed

        self._callback = callback
        self._websocket = websocket.WebSocketApp(
            'ws://localhost:8090/_websocket/simulator',
            on_open=self._on_websocket_open,
            on_message=self._on_websocket_message,
            on_error=self._on_websocket_error,
        )
        self._consumer = threading.Thread(target=self._websocket.run_forever)
        # self._consumer.daemon = True

        self._consumer.start()

    def close(self, reason=None):
        """
        Stop consuming messages and perform an orderly shutdown.

        If ``reason`` is None, then this is considered a regular close.
        """
        with self._closing:
            if self._closed:
                return

            self._websocket.close()

            self._consumer.join()
            self._consumer = None

            self._websocket = None
            self._closed = True

            for cb in self._close_callbacks:
                cb(self, reason)

    def _on_websocket_open(self, ws):
        self._websocket.send('[1,1,1,{"time":"subscribe"}]')

    def _on_websocket_message(self, ws, message):
        self._callback(message)

    def _on_websocket_error(self, ws, error):

        # Generate our own exception.
        # (the default message is a bit misleading 'connection is already closed')
        if isinstance(error, websocket.WebSocketConnectionClosedException):
            error = ConnectionFailure('Connection closed')

        # Close async. This is to not get stuck in the above ``join()``.
        closer = threading.Thread(
            target=self.close,
            kwargs={'reason': error}
        )
        closer.daemon = True
        closer.start()