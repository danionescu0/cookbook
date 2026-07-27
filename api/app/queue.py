import json

import pika

from app.config import settings

IMPORT_JOBS_QUEUE = "import_jobs"
INGREDIENT_REFRESH_JOBS_QUEUE = "ingredient_refresh_jobs"


def publish_import_job(job_id: int, job_type: str, source: str) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=IMPORT_JOBS_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=IMPORT_JOBS_QUEUE,
            body=json.dumps({"job_id": job_id, "type": job_type, "source": source}),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()


def publish_ingredient_refresh_job(job_id: int) -> None:
    # Same worker container, third queue — see README Design Decisions ("Ingredient nutrition").
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=INGREDIENT_REFRESH_JOBS_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=INGREDIENT_REFRESH_JOBS_QUEUE,
            body=json.dumps({"job_id": job_id}),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()
