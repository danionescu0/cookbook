import json

import pika

from app.config import settings

NUTRITION_JOBS_QUEUE = "nutrition_jobs"


def publish_nutrition_job(job_id: int, recipe_id: int) -> None:
    # Used to auto-enqueue enrichment right after a successful import — see handlers.py and
    # README Design Decisions ("Ingredient nutrition").
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=NUTRITION_JOBS_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=NUTRITION_JOBS_QUEUE,
            body=json.dumps({"job_id": job_id, "recipe_id": recipe_id}),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()
