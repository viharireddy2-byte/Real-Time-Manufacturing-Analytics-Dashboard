"""Thread-safe, reusable Event Hubs producer; synchronous acknowledgement semantics."""
import json
import threading
from typing import Any, Iterable


class EventHubService:
    """Serialize access to the synchronous SDK client shared by asset threads.

    send_event retains its original public signature. send_events batches up to
    the SDK byte limit. SDK retries are retained; callers must expect at-least-once
    delivery after an ambiguous transport failure and retain the event Id.
    """

    def __init__(self, fully_qualified_namespace: str, event_hub_name: str,
                 *, producer=None, credential=None, event_factory=None):
        self.fully_qualified_namespace = fully_qualified_namespace
        self.event_hub_name = event_hub_name
        self._owns_credential = producer is None and credential is None
        if producer is None:
            from azure.eventhub import EventHubProducerClient
            if credential is None:
                from azure.identity import AzureCliCredential
                credential = AzureCliCredential()
            producer = EventHubProducerClient(
                fully_qualified_namespace=fully_qualified_namespace,
                eventhub_name=event_hub_name, credential=credential,
                retry_total=3, retry_backoff_factor=0.8)
        if event_factory is None:
            from azure.eventhub import EventData
            event_factory = EventData
        self.credential = credential
        self._producer = producer
        self._event_factory = event_factory
        self._lock = threading.Lock()
        self._closed = False
        self.events_sent = 0
        self.batches_sent = 0

    def send_event(self, data: Any) -> None:
        self.send_events([data])

    def send_events(self, records: Iterable[Any], *, partition_key=None, on_batch_sent=None) -> int:
        """Send a bounded stream of records; return acknowledged record count.

        If a later batch fails, earlier batches remain committed. An oversized
        single record raises ValueError instead of being silently dropped.
        No application retry is added on top of the SDK retry policy.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError('EventHubService is closed')
            options = {} if partition_key is None else {'partition_key': partition_key}
            batch = self._producer.create_batch(**options)
            pending = sent = 0
            for record in records:
                event = self._event_factory(json.dumps(record, allow_nan=False, separators=(',', ':')))
                event.properties = {'content-type': 'application/json', 'source': 'FactoryPulse'}
                try:
                    batch.add(event)
                except ValueError:
                    if not pending:
                        raise
                    self._producer.send_batch(batch)
                    self.events_sent += pending
                    self.batches_sent += 1
                    sent += pending
                    if on_batch_sent is not None:
                        on_batch_sent(pending)
                    batch = self._producer.create_batch(**options)
                    pending = 0
                    batch.add(event)
                pending += 1
            if pending:
                self._producer.send_batch(batch)
                self.events_sent += pending
                self.batches_sent += 1
                sent += pending
                if on_batch_sent is not None:
                    on_batch_sent(pending)
            return sent

    def close(self):
        with self._lock:
            if not self._closed:
                try:
                    self._producer.close()
                finally:
                    self._closed = True
                    if self._owns_credential and self.credential is not None:
                        self.credential.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
