import json
import logging
import time

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

from app.config import settings
from app.database import SessionLocal
from app.email_handlers import handle_email_job
from app.handlers import handle_import_job
from app.ingredient_refresh_handlers import handle_ingredient_refresh_job
from app.models import (
    EmailJob,
    EmailJobStatus,
    ImportJob,
    ImportJobStatus,
    IngredientRefreshJob,
    IngredientRefreshJobStatus,
    NutritionJob,
    NutritionJobStatus,
    TranslationSyncJob,
    TranslationSyncJobStatus,
)
from app.nutrition_handlers import handle_nutrition_job
from app.translation_sync_handlers import handle_translation_sync_job

logger = logging.getLogger(__name__)

IMPORT_JOBS_QUEUE = "import_jobs"
NUTRITION_JOBS_QUEUE = "nutrition_jobs"
INGREDIENT_REFRESH_JOBS_QUEUE = "ingredient_refresh_jobs"
TRANSLATION_SYNC_JOBS_QUEUE = "translation_sync_jobs"
EMAIL_JOBS_QUEUE = "email_jobs"


def _on_message(
    channel: BlockingChannel,
    method: Basic.Deliver,
    properties: BasicProperties,
    body: bytes,
) -> None:
    db = SessionLocal()
    try:
        handle_import_job(body, db)
    except Exception as exc:
        # handle_import_job already catches and records the failure modes it knows about
        # (fetch errors, robots.txt, malformed Claude responses, ...). Anything that escapes
        # here is unexpected — a job must never end up silently stuck with no trace (this is
        # exactly how a past enum-drift bug left a job stuck at "queued" forever): record it
        # as failed too, so it's visible and retriable in the back office instead.
        logger.exception("unhandled error processing import job")
        db.rollback()
        try:
            payload = json.loads(body)
            job = db.get(ImportJob, payload.get("job_id"))
            if job is not None:
                job.status = ImportJobStatus.FAILED
                job.error = f"worker crashed while processing: {exc}"
                db.commit()
        except Exception:
            logger.exception("failed to record job failure after crash")
    finally:
        db.close()
    channel.basic_ack(delivery_tag=method.delivery_tag)


def _on_nutrition_message(
    channel: BlockingChannel,
    method: Basic.Deliver,
    properties: BasicProperties,
    body: bytes,
) -> None:
    db = SessionLocal()
    try:
        handle_nutrition_job(body, db)
    except Exception as exc:
        # Same reasoning as _on_message above: handle_nutrition_job already catches the failure
        # modes it knows about, so anything escaping here is unexpected and must still be
        # recorded rather than leaving the job stuck at "processing" forever.
        logger.exception("unhandled error processing nutrition job")
        db.rollback()
        try:
            payload = json.loads(body)
            job = db.get(NutritionJob, payload.get("job_id"))
            if job is not None:
                job.status = NutritionJobStatus.FAILED
                job.error = f"worker crashed while processing: {exc}"
                db.commit()
        except Exception:
            logger.exception("failed to record nutrition job failure after crash")
    finally:
        db.close()
    channel.basic_ack(delivery_tag=method.delivery_tag)


def _on_ingredient_refresh_message(
    channel: BlockingChannel,
    method: Basic.Deliver,
    properties: BasicProperties,
    body: bytes,
) -> None:
    db = SessionLocal()
    try:
        handle_ingredient_refresh_job(body, db)
    except Exception as exc:
        # Same reasoning as the other two callbacks above.
        logger.exception("unhandled error processing ingredient refresh job")
        db.rollback()
        try:
            payload = json.loads(body)
            job = db.get(IngredientRefreshJob, payload.get("job_id"))
            if job is not None:
                job.status = IngredientRefreshJobStatus.FAILED
                job.error = f"worker crashed while processing: {exc}"
                db.commit()
        except Exception:
            logger.exception("failed to record ingredient refresh job failure after crash")
    finally:
        db.close()
    channel.basic_ack(delivery_tag=method.delivery_tag)


def _on_translation_sync_message(
    channel: BlockingChannel,
    method: Basic.Deliver,
    properties: BasicProperties,
    body: bytes,
) -> None:
    db = SessionLocal()
    try:
        handle_translation_sync_job(body, db)
    except Exception as exc:
        # Same reasoning as the other callbacks above.
        logger.exception("unhandled error processing translation sync job")
        db.rollback()
        try:
            payload = json.loads(body)
            job = db.get(TranslationSyncJob, payload.get("job_id"))
            if job is not None:
                job.status = TranslationSyncJobStatus.FAILED
                job.error = f"worker crashed while processing: {exc}"
                db.commit()
        except Exception:
            logger.exception("failed to record translation sync job failure after crash")
    finally:
        db.close()
    channel.basic_ack(delivery_tag=method.delivery_tag)


def _on_email_message(
    channel: BlockingChannel,
    method: Basic.Deliver,
    properties: BasicProperties,
    body: bytes,
) -> None:
    db = SessionLocal()
    try:
        handle_email_job(body, db)
    except Exception as exc:
        # Same reasoning as the other callbacks above.
        logger.exception("unhandled error processing email job")
        db.rollback()
        try:
            payload = json.loads(body)
            job = db.get(EmailJob, payload.get("job_id"))
            if job is not None:
                job.status = EmailJobStatus.FAILED
                job.error = f"worker crashed while processing: {exc}"
                db.commit()
        except Exception:
            logger.exception("failed to record email job failure after crash")
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
    channel.queue_declare(queue=NUTRITION_JOBS_QUEUE, durable=True)
    channel.queue_declare(queue=INGREDIENT_REFRESH_JOBS_QUEUE, durable=True)
    channel.queue_declare(queue=TRANSLATION_SYNC_JOBS_QUEUE, durable=True)
    channel.queue_declare(queue=EMAIL_JOBS_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=IMPORT_JOBS_QUEUE, on_message_callback=_on_message)
    channel.basic_consume(queue=NUTRITION_JOBS_QUEUE, on_message_callback=_on_nutrition_message)
    channel.basic_consume(
        queue=INGREDIENT_REFRESH_JOBS_QUEUE, on_message_callback=_on_ingredient_refresh_message
    )
    channel.basic_consume(
        queue=TRANSLATION_SYNC_JOBS_QUEUE, on_message_callback=_on_translation_sync_message
    )
    channel.basic_consume(queue=EMAIL_JOBS_QUEUE, on_message_callback=_on_email_message)

    # One worker process/container consumes all five queues on the same connection — see README
    # Design Decisions ("Ingredient nutrition") for why this wasn't split into a separate service.
    logger.info(
        "worker started, waiting for jobs on %s, %s, %s, %s, and %s",
        IMPORT_JOBS_QUEUE,
        NUTRITION_JOBS_QUEUE,
        INGREDIENT_REFRESH_JOBS_QUEUE,
        TRANSLATION_SYNC_JOBS_QUEUE,
        EMAIL_JOBS_QUEUE,
    )
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()
