import json

import pika

from app.config import settings

IMPORT_JOBS_QUEUE = "import_jobs"
TRANSLATION_SYNC_JOBS_QUEUE = "translation_sync_jobs"
INGREDIENT_REFRESH_JOBS_QUEUE = "ingredient_refresh_jobs"
EMAIL_JOBS_QUEUE = "email_jobs"
RECIPE_REPARSE_JOBS_QUEUE = "recipe_reparse_jobs"
CONTACT_MESSAGE_JOBS_QUEUE = "contact_message_jobs"


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


def publish_translation_sync_job(job_id: int, recipe_id: int) -> None:
    # Triggered whenever PUT /recipes/{id} edits a translation — the worker propagates the
    # edited language to every other supported language via Claude, then re-enriches nutrition
    # once they're back in sync. See app.models.translation_sync_job.
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=TRANSLATION_SYNC_JOBS_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=TRANSLATION_SYNC_JOBS_QUEUE,
            body=json.dumps({"job_id": job_id, "recipe_id": recipe_id}),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()


def publish_email_job(job_id: int, user_id: int) -> None:
    # Triggered by signup — the worker sends the actual verification email via SMTP. See
    # worker/app/email_handlers.py.
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=EMAIL_JOBS_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=EMAIL_JOBS_QUEUE,
            body=json.dumps({"job_id": job_id, "user_id": user_id}),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()


def publish_reparse_job(job_id: int, recipe_id: int) -> None:
    # Triggered by an admin's "Reparse" click (or the bulk "reparse all imported" action) — the
    # worker re-scrapes the recipe's existing source_url and updates its translations in place.
    # See app.models.recipe_reparse_job.
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=RECIPE_REPARSE_JOBS_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=RECIPE_REPARSE_JOBS_QUEUE,
            body=json.dumps({"job_id": job_id, "recipe_id": recipe_id}),
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


def publish_contact_message_job(job_id: int) -> None:
    # Triggered by the public /contact form — the worker emails the submission to
    # app_settings.contact_recipient_email. See worker/app/contact_handlers.py.
    connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=CONTACT_MESSAGE_JOBS_QUEUE, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=CONTACT_MESSAGE_JOBS_QUEUE,
            body=json.dumps({"job_id": job_id}),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()
