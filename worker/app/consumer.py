import logging
import time

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

from app.config import settings
from app.database import SessionLocal
from app.handlers import handle_import_job

logger = logging.getLogger(__name__)

IMPORT_JOBS_QUEUE = "import_jobs"


def _on_message(
    channel: BlockingChannel,
    method: Basic.Deliver,
    properties: BasicProperties,
    body: bytes,
) -> None:
    db = SessionLocal()
    try:
        handle_import_job(body, db)
    except Exception:
        logger.exception("failed to process import job")
    finally:
        db.close()
    channel.basic_ack(delivery_tag=method.delivery_tag)


def connect_with_retry(
    max_attempts: int = 10, delay_seconds: float = 3.0
) -> pika.BlockingConnection:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        except pika.exceptions.AMQPConnectionError as exc:
            last_error = exc
            logger.warning(
                "RabbitMQ not ready yet (attempt %s/%s): %s", attempt, max_attempts, exc
            )
            time.sleep(delay_seconds)
    raise RuntimeError("could not connect to RabbitMQ") from last_error


def run() -> None:
    connection = connect_with_retry()
    channel = connection.channel()
    channel.queue_declare(queue=IMPORT_JOBS_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=IMPORT_JOBS_QUEUE, on_message_callback=_on_message)

    logger.info("worker started, waiting for import jobs on %s", IMPORT_JOBS_QUEUE)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()
