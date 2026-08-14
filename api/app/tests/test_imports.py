import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.import_job import ImportJob, ImportJobStatus
from app.models.recipe import Recipe
from app.models.recipe_translation import RecipeTranslation
from app.models.user import User
from app.routers import imports as imports_router


def _create_category(client: TestClient, name: str = "Desserts") -> int:
    return client.post("/categories", json={"name": name}).json()["id"]


def test_create_import_job_stays_pending_and_does_not_publish(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = []
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda job_id, job_type, source: published.append((job_id, job_type, source)),
    )

    response = client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "https://example.com/recipe"
    # Not picked by the requester any more — the worker resolves it from Claude's own
    # suggestion once extraction succeeds (see worker/app/handlers.py's _resolve_category_id).
    assert body["category_id"] is None
    assert body["type"] == "single"
    assert body["status"] == "pending"
    assert published == []  # not published until approved


@pytest.mark.parametrize(
    ("source", "expected_type"),
    [
        ("https://www.instagram.com/p/DPa1bP5DZhP/", "instagram"),
        ("https://instagram.com/reel/DPa1bP5DZhP/", "instagram"),
        ("https://instagr.am/p/DPa1bP5DZhP/", "instagram"),
        ("https://example.com/some-recipe", "single"),
        # A different site with "instagram" somewhere in the path/host must not false-positive.
        ("https://not-instagram.com/p/DPa1bP5DZhP/", "single"),
    ],
)
def test_create_import_job_detects_instagram_urls(
    client: TestClient, source: str, expected_type: str
) -> None:
    response = client.post("/imports", json={"source": source})

    assert response.status_code == 201
    assert response.json()["type"] == expected_type


def test_create_import_job_rejects_url_already_imported_as_a_recipe(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    category_id = _create_category(client)
    recipe = Recipe(
        category_id=category_id, source_url="https://example.com/recipe", owner_user_id=admin_user.id
    )
    recipe.translations.append(RecipeTranslation(language="en", title="Existing", slug="existing"))
    db_session.add(recipe)
    db_session.commit()

    response = client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 409


def test_create_import_job_rejects_url_already_in_the_queue(client: TestClient) -> None:
    client.post("/imports", json={"source": "https://example.com/recipe"})

    response = client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 409


def test_create_import_job_allows_resubmission_after_deleting_previous_job(
    client: TestClient,
) -> None:
    created = client.post("/imports", json={"source": "https://example.com/recipe"}).json()
    client.delete(f"/imports/{created['id']}")

    response = client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 201


def test_create_import_job_allows_resubmission_after_deleting_the_resulting_recipe(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    # Real bug report: importing a URL, deleting the resulting recipe, then trying to import the
    # same URL again permanently 409'd with "already in the import queue" — the completed
    # ImportJob row from the first import was never cleaned up when the recipe it produced was
    # deleted, so the duplicate-URL guard kept blocking the exact same URL forever, even though
    # nothing was actually queued or imported any more.
    category_id = _create_category(client)
    recipe = Recipe(
        category_id=category_id, source_url="https://example.com/recipe", owner_user_id=admin_user.id
    )
    recipe.translations.append(RecipeTranslation(language="en", title="Existing", slug="existing"))
    db_session.add(recipe)
    db_session.add(
        ImportJob(
            source="https://example.com/recipe",
            status=ImportJobStatus.DONE,
            created_by_user_id=admin_user.id,
        )
    )
    db_session.commit()
    db_session.refresh(recipe)

    delete_response = client.delete(f"/recipes/{recipe.id}")
    assert delete_response.status_code == 204

    response = client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 201


def test_create_import_job_rejects_when_lifetime_limit_reached(
    user_client: TestClient, client: TestClient, db_session: Session, regular_user: User
) -> None:
    client.patch("/settings", json={"max_imports_per_user": 2})
    regular_user.imported_recipes_count = 2
    db_session.commit()

    response = user_client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 403
    assert "2/2" in response.json()["detail"]


def test_create_import_job_allows_up_to_but_not_over_the_limit(
    user_client: TestClient, client: TestClient, db_session: Session, regular_user: User
) -> None:
    client.patch("/settings", json={"max_imports_per_user": 2})
    regular_user.imported_recipes_count = 1
    db_session.commit()

    response = user_client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 201


def test_create_import_job_exempts_admins_from_the_limit(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    client.patch("/settings", json={"max_imports_per_user": 1})
    admin_user.imported_recipes_count = 50
    db_session.commit()

    response = client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 201


def test_import_limit_counter_is_unaffected_by_recipe_deletion(
    client: TestClient, db_session: Session, regular_user: User
) -> None:
    # The whole point of a lifetime counter: deleting the recipe an import produced must not
    # free up quota. This doesn't exercise the worker's increment (see
    # worker/app/handlers.py::_finish_import) — it just confirms nothing in the recipe-delete
    # path touches imported_recipes_count.
    category_id = _create_category(client)
    recipe = Recipe(
        category_id=category_id,
        source_url="https://example.com/recipe",
        owner_user_id=regular_user.id,
    )
    recipe.translations.append(RecipeTranslation(language="en", title="Gone", slug="gone"))
    db_session.add(recipe)
    regular_user.imported_recipes_count = 5
    db_session.commit()
    recipe_id = recipe.id

    response = client.delete(f"/recipes/{recipe_id}")
    assert response.status_code == 204

    db_session.refresh(regular_user)
    assert regular_user.imported_recipes_count == 5


def test_approve_import_job_publishes_and_marks_queued(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.post("/imports", json={"source": "https://example.com/recipe"}).json()
    published = []
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda job_id, job_type, source: published.append((job_id, job_type, source)),
    )

    response = client.post(f"/imports/{created['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert published == [(created["id"], "single", "https://example.com/recipe")]


def test_approve_import_job_marks_failed_when_publish_raises(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.post("/imports", json={"source": "https://example.com/recipe"}).json()

    def _raise(job_id: int, job_type: str, source: str) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(imports_router, "publish_import_job", _raise)

    response = client.post(f"/imports/{created['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "connection refused" in body["error"]


def test_approve_import_job_can_retry_a_failed_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.post("/imports", json={"source": "https://example.com/recipe"}).json()
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda *args: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    client.post(f"/imports/{created['id']}/approve")  # first attempt fails

    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)
    response = client.post(f"/imports/{created['id']}/approve")  # retry succeeds

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["error"] is None


def test_approve_import_job_rejects_already_queued_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.post("/imports", json={"source": "https://example.com/recipe"}).json()
    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)
    client.post(f"/imports/{created['id']}/approve")

    response = client.post(f"/imports/{created['id']}/approve")

    assert response.status_code == 400


def test_approve_import_job_not_found(client: TestClient) -> None:
    response = client.post("/imports/999/approve")

    assert response.status_code == 404


def test_delete_import_job(client: TestClient) -> None:
    created = client.post("/imports", json={"source": "https://example.com/recipe"}).json()

    delete_response = client.delete(f"/imports/{created['id']}")
    get_response = client.get(f"/imports/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_list_import_jobs(client: TestClient) -> None:
    client.post("/imports", json={"source": "https://example.com/a"})
    client.post("/imports", json={"source": "https://example.com/b"})

    response = client.get("/imports")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_import_job_not_found(client: TestClient) -> None:
    response = client.get("/imports/999")

    assert response.status_code == 404


def test_create_import_job_shows_the_creators_email(client: TestClient) -> None:
    response = client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.json()["created_by_email"] == "admin@example.com"


def test_non_admin_import_queues_and_publishes_immediately(
    client: TestClient, user_client: TestClient, regular_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No public-exposure review is needed for a private import — unlike an admin's own job,
    # which stays "pending" until explicitly approved.
    published = []
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda job_id, job_type, source: published.append((job_id, job_type, source)),
    )

    response = user_client.post("/imports", json={"source": "https://example.com/recipe"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["created_by_user_id"] == regular_user.id
    # The raw email is admin-only, same nulling pattern as ImportJobRead.error — a non-admin
    # caller doesn't get it back even for their own job.
    assert body["created_by_email"] is None
    assert published == [(body["id"], "single", "https://example.com/recipe")]


def test_two_different_users_can_import_the_same_url(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Imports are private per owner now, so this isn't a duplicate — each gets their own copy.
    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)

    first = client.post("/imports", json={"source": "https://example.com/shared-recipe"})
    second = user_client.post("/imports", json={"source": "https://example.com/shared-recipe"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_non_admin_only_sees_their_own_import_jobs(
    client: TestClient, user_client: TestClient
) -> None:
    client.post("/imports", json={"source": "https://example.com/admins"})
    mine = user_client.post("/imports", json={"source": "https://example.com/mine"}).json()

    response = user_client.get("/imports")

    assert [job["id"] for job in response.json()] == [mine["id"]]


def test_admin_sees_every_users_import_jobs(client: TestClient, user_client: TestClient) -> None:
    client.post("/imports", json={"source": "https://example.com/admins"})
    user_client.post("/imports", json={"source": "https://example.com/mine"})

    response = client.get("/imports")

    assert len(response.json()) == 2


def test_non_admin_cannot_see_or_modify_someone_elses_import_job(
    client: TestClient, user_client: TestClient
) -> None:
    admins_job = client.post("/imports", json={"source": "https://example.com/admins-only"}).json()

    assert user_client.get(f"/imports/{admins_job['id']}").status_code == 404
    assert user_client.post(f"/imports/{admins_job['id']}/approve").status_code == 404
    assert user_client.delete(f"/imports/{admins_job['id']}").status_code == 404


def test_non_admin_can_retry_their_own_failed_job(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        imports_router, "publish_import_job", lambda *args: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    created = user_client.post("/imports", json={"source": "https://example.com/retry-me"}).json()
    assert created["status"] == "failed"  # the immediate publish attempt failed

    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)
    response = user_client.post(f"/imports/{created['id']}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_admin_can_see_a_non_admins_import_job(
    client: TestClient, db_session: Session, regular_user: User
) -> None:
    # An admin isn't limited by the ownership check that applies to everyone else.
    job = ImportJob(source="https://example.com/x", created_by_user_id=regular_user.id)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.get(f"/imports/{job.id}")

    assert response.status_code == 200


def _fail_a_job(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(
        imports_router, "publish_import_job", lambda *args: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    return client.post("/imports", json={"source": "https://example.com/fails"}).json()


def test_dismiss_failed_import_job(
    user_client: TestClient, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _fail_a_job(user_client, monkeypatch)
    assert failed["status"] == "failed"

    response = user_client.post(f"/imports/{failed['id']}/dismiss")

    assert response.status_code == 200
    assert response.json()["dismissed_at"] is not None


def test_dismiss_rejects_a_job_that_has_not_failed(client: TestClient) -> None:
    pending = client.post("/imports", json={"source": "https://example.com/still-pending"}).json()
    assert pending["status"] == "pending"

    response = client.post(f"/imports/{pending['id']}/dismiss")

    assert response.status_code == 400


def test_non_owner_non_admin_cannot_dismiss(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An admin's own job doesn't auto-publish on creation (see create_import_job), so it has to
    # fail via approve/retry instead of _fail_a_job's create-time failure.
    created = client.post("/imports", json={"source": "https://example.com/admins-failure"}).json()
    monkeypatch.setattr(
        imports_router, "publish_import_job", lambda *args: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    failed = client.post(f"/imports/{created['id']}/approve").json()
    assert failed["status"] == "failed"

    response = user_client.post(f"/imports/{failed['id']}/dismiss")

    # Same "don't confirm it exists" 404, not 403 — matches _get_owned_or_404 everywhere else.
    assert response.status_code == 404


def test_admin_dismissing_does_not_require_ownership(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _fail_a_job(user_client, monkeypatch)

    response = client.post(f"/imports/{failed['id']}/dismiss")

    assert response.status_code == 200


def test_non_admin_never_sees_the_raw_error_only_error_kind(
    user_client: TestClient, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _fail_a_job(user_client, monkeypatch)

    assert failed["error"] is None
    assert failed["error_kind"] == "technical"

    response = user_client.get(f"/imports/{failed['id']}")
    assert response.json()["error"] is None
    assert response.json()["error_kind"] == "technical"


def test_admin_sees_the_raw_error(
    user_client: TestClient, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _fail_a_job(user_client, monkeypatch)

    response = client.get(f"/imports/{failed['id']}")

    assert response.json()["error"] is not None
    assert "boom" in response.json()["error"]


def test_list_import_jobs_paginates_when_limit_is_given(client: TestClient) -> None:
    for i in range(3):
        client.post("/imports", json={"source": f"https://example.com/{i}"})

    response = client.get("/imports", params={"limit": 2, "offset": 0})

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "3"
    assert len(response.json()) == 2

    second_page = client.get("/imports", params={"limit": 2, "offset": 2})
    assert len(second_page.json()) == 1


def test_list_import_jobs_without_limit_returns_everything_unheadered(client: TestClient) -> None:
    for i in range(3):
        client.post("/imports", json={"source": f"https://example.com/{i}"})

    response = client.get("/imports")

    assert len(response.json()) == 3
    assert "X-Total-Count" not in response.headers


def test_list_import_jobs_filters_by_status(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _fail_a_job(user_client, monkeypatch)
    client.post("/imports", json={"source": "https://example.com/still-pending"})

    response = client.get("/imports", params={"status": "failed", "limit": 10, "offset": 0})

    assert response.headers["X-Total-Count"] == "1"
    assert [job["id"] for job in response.json()] == [failed["id"]]


def test_mark_reviewed_requires_admin(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _fail_a_job(user_client, monkeypatch)

    response = user_client.post(f"/imports/{failed['id']}/mark-reviewed")

    assert response.status_code == 403


def test_mark_reviewed_sets_the_timestamp_and_does_not_touch_dismissed_at(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _fail_a_job(user_client, monkeypatch)

    response = client.post(f"/imports/{failed['id']}/mark-reviewed")

    assert response.status_code == 200
    body = response.json()
    assert body["admin_reviewed_at"] is not None
    assert body["dismissed_at"] is None


def test_mark_reviewed_rejects_a_job_that_has_not_failed(client: TestClient) -> None:
    pending = client.post("/imports", json={"source": "https://example.com/still-pending"}).json()

    response = client.post(f"/imports/{pending['id']}/mark-reviewed")

    assert response.status_code == 400


def test_owner_dismissing_does_not_affect_admin_reviewed_at(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed = _fail_a_job(user_client, monkeypatch)
    client.post(f"/imports/{failed['id']}/mark-reviewed")

    response = user_client.post(f"/imports/{failed['id']}/dismiss")

    assert response.status_code == 200
    assert response.json()["dismissed_at"] is not None
    # Reviewed-by-admin state survives the owner's own, independent dismissal.
    admin_view = client.get(f"/imports/{failed['id']}")
    assert admin_view.json()["admin_reviewed_at"] is not None


def test_list_import_jobs_filters_by_admin_reviewed(
    client: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed = _fail_a_job(user_client, monkeypatch)
    client.post(f"/imports/{reviewed['id']}/mark-reviewed")
    monkeypatch.setattr(
        imports_router, "publish_import_job", lambda *args: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    unreviewed = user_client.post(
        "/imports", json={"source": "https://example.com/still-unreviewed"}
    ).json()

    response = client.get(
        "/imports", params={"status": "failed", "admin_reviewed": "false", "limit": 10, "offset": 0}
    )

    assert response.headers["X-Total-Count"] == "1"
    assert [job["id"] for job in response.json()] == [unreviewed["id"]]


_BOOKMARK_HTML = """
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
    <DT><A HREF="https://example.com/cake">Chocolate Cake</A>
    <DT><A HREF="https://example.com/soup">Soup</A>
    <DT><A HREF="javascript:void(0)">Not a real link</A>
</DL><p>
"""


def _upload_bookmarks(client: TestClient, html: str = _BOOKMARK_HTML):
    return client.post(
        "/imports/bookmark/parse",
        files={"file": ("bookmarks.html", html.encode("utf-8"), "text/html")},
    )


def test_parse_bookmark_file_returns_candidate_links(client: TestClient) -> None:
    response = _upload_bookmarks(client)

    assert response.status_code == 200
    body = response.json()
    urls = [link["url"] for link in body["links"]]
    assert "https://example.com/cake" in urls
    assert "https://example.com/soup" in urls
    assert not any(url.startswith("javascript:") for url in urls)


def test_parse_bookmark_file_reports_unlimited_quota_for_admin(client: TestClient) -> None:
    response = _upload_bookmarks(client)

    assert response.json()["remaining_quota"] is None


def test_parse_bookmark_file_reports_remaining_quota_for_non_admin(
    user_client: TestClient, client: TestClient, db_session: Session, regular_user: User
) -> None:
    client.patch("/settings", json={"max_imports_per_user": 10})
    regular_user.imported_recipes_count = 7
    db_session.commit()

    response = _upload_bookmarks(user_client)

    assert response.json()["remaining_quota"] == 3


def test_parse_bookmark_file_flags_a_link_already_imported_as_a_recipe(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    category_id = _create_category(client)
    recipe = Recipe(
        category_id=category_id, source_url="https://example.com/cake", owner_user_id=admin_user.id
    )
    recipe.translations.append(RecipeTranslation(language="en", title="Cake", slug="cake"))
    db_session.add(recipe)
    db_session.commit()

    response = _upload_bookmarks(client)

    by_url = {link["url"]: link for link in response.json()["links"]}
    assert by_url["https://example.com/cake"]["already_imported"] is True
    assert by_url["https://example.com/soup"]["already_imported"] is False


def test_parse_bookmark_file_flags_a_link_already_queued(client: TestClient) -> None:
    client.post("/imports", json={"source": "https://example.com/soup"})

    response = _upload_bookmarks(client)

    by_url = {link["url"]: link for link in response.json()["links"]}
    assert by_url["https://example.com/soup"]["already_imported"] is True


def test_parse_bookmark_file_requires_auth(unauthenticated_client: TestClient) -> None:
    response = _upload_bookmarks(unauthenticated_client)

    assert response.status_code == 401


def test_import_bookmark_selection_creates_a_job_per_url(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)

    response = client.post(
        "/imports/bookmark",
        json={"urls": ["https://example.com/cake", "https://example.com/soup"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert {job["source"] for job in body["created"]} == {
        "https://example.com/cake",
        "https://example.com/soup",
    }
    assert all(job["type"] == "bookmark" for job in body["created"])
    assert body["skipped_duplicate"] == []


def test_import_bookmark_selection_admin_jobs_stay_pending(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = []
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda job_id, job_type, source: published.append((job_id, job_type, source)),
    )

    response = client.post("/imports/bookmark", json={"urls": ["https://example.com/cake"]})

    assert response.json()["created"][0]["status"] == "pending"
    assert published == []


def test_import_bookmark_selection_non_admin_queues_and_publishes_immediately(
    user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    published = []
    monkeypatch.setattr(
        imports_router,
        "publish_import_job",
        lambda job_id, job_type, source: published.append((job_id, job_type, source)),
    )

    response = user_client.post("/imports/bookmark", json={"urls": ["https://example.com/cake"]})

    assert response.json()["created"][0]["status"] == "queued"
    assert published == [(response.json()["created"][0]["id"], "bookmark", "https://example.com/cake")]


def test_import_bookmark_selection_rejects_selection_over_remaining_quota(
    user_client: TestClient, client: TestClient, db_session: Session, regular_user: User
) -> None:
    client.patch("/settings", json={"max_imports_per_user": 10})
    regular_user.imported_recipes_count = 8
    db_session.commit()

    response = user_client.post(
        "/imports/bookmark",
        json={"urls": ["https://example.com/a", "https://example.com/b", "https://example.com/c"]},
    )

    assert response.status_code == 400
    assert "2" in response.json()["detail"]  # only 2 of the 3 selected fit the remaining quota


def test_import_bookmark_selection_allows_exactly_the_remaining_quota(
    user_client: TestClient, client: TestClient, db_session: Session, regular_user: User
) -> None:
    client.patch("/settings", json={"max_imports_per_user": 10})
    regular_user.imported_recipes_count = 8
    db_session.commit()

    response = user_client.post(
        "/imports/bookmark", json={"urls": ["https://example.com/a", "https://example.com/b"]}
    )

    assert response.status_code == 200
    assert len(response.json()["created"]) == 2


def test_import_bookmark_selection_exempts_admin_from_the_quota(
    client: TestClient, admin_user: User, db_session: Session
) -> None:
    client.patch("/settings", json={"max_imports_per_user": 1})
    admin_user.imported_recipes_count = 50
    db_session.commit()

    response = client.post(
        "/imports/bookmark",
        json={"urls": ["https://example.com/a", "https://example.com/b", "https://example.com/c"]},
    )

    assert response.status_code == 200
    assert len(response.json()["created"]) == 3


def test_import_bookmark_selection_skips_already_imported_urls_without_erroring(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    category_id = _create_category(client)
    recipe = Recipe(
        category_id=category_id, source_url="https://example.com/cake", owner_user_id=admin_user.id
    )
    recipe.translations.append(RecipeTranslation(language="en", title="Cake", slug="cake"))
    db_session.add(recipe)
    db_session.commit()

    response = client.post(
        "/imports/bookmark",
        json={"urls": ["https://example.com/cake", "https://example.com/soup"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["skipped_duplicate"] == ["https://example.com/cake"]
    assert [job["source"] for job in body["created"]] == ["https://example.com/soup"]


def test_import_bookmark_selection_skipped_duplicates_do_not_count_against_quota(
    user_client: TestClient, client: TestClient, db_session: Session, regular_user: User
) -> None:
    # Already-imported/queued URLs are filtered out before the quota check, not after — otherwise
    # a duplicate in the selection would needlessly eat into (or block) a slot it doesn't need.
    client.patch("/settings", json={"max_imports_per_user": 10})
    regular_user.imported_recipes_count = 9
    db_session.commit()
    user_client.post("/imports", json={"source": "https://example.com/already-queued"})

    response = user_client.post(
        "/imports/bookmark",
        json={"urls": ["https://example.com/already-queued", "https://example.com/new-one"]},
    )

    assert response.status_code == 200
    assert response.json()["skipped_duplicate"] == ["https://example.com/already-queued"]
    assert [job["source"] for job in response.json()["created"]] == ["https://example.com/new-one"]


def test_import_bookmark_selection_dedupes_repeated_urls_within_the_request(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(imports_router, "publish_import_job", lambda *args: None)

    response = client.post(
        "/imports/bookmark",
        json={"urls": ["https://example.com/cake", "https://example.com/cake"]},
    )

    assert len(response.json()["created"]) == 1


def test_import_bookmark_selection_requires_auth(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/imports/bookmark", json={"urls": ["https://example.com/cake"]}
    )

    assert response.status_code == 401
