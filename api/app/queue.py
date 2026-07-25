import json

import pika

from app.config import settings

IMPORT_JOBS_QUEUE = "import_jobs"


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
