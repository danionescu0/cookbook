from sqlalchemy.orm import Session

from app.models.recipe import Recipe
from app.models.recipe_translation import RecipeTranslation
from app.slugify import generate_unique_slug, slugify


class TestSlugify:
    def test_lowercases_and_hyphenates(self) -> None:
        assert slugify("Pui cu legume la tigaie") == "pui-cu-legume-la-tigaie"

    def test_strips_romanian_comma_below_diacritics(self) -> None:
        assert slugify("Ciorbă de burtă cu smântână și usturoi") == "ciorba-de-burta-cu-smantana-si-usturoi"

    def test_strips_romanian_cedilla_variant_diacritics(self) -> None:
        # ş/ţ (cedilla, U+015F/U+0163) are the visually-identical variant of ș/ț some fonts/
        # keyboards produce instead of the comma-below forms — both must map the same way.
        assert slugify("Pâine cu ceafă") == "paine-cu-ceafa"

    def test_strips_generic_accents_via_nfkd(self) -> None:
        assert slugify("Crème brûlée") == "creme-brulee"

    def test_falls_back_to_recipe_for_a_title_with_no_alphanumeric_characters(self) -> None:
        assert slugify("!!!") == "recipe"

    def test_truncates_long_titles_at_a_word_boundary(self) -> None:
        result = slugify("word " * 30)
        assert len(result) <= 100
        assert not result.endswith("-")


class TestGenerateUniqueSlug:
    def test_first_use_returns_the_base_slug(self, db_session: Session) -> None:
        assert generate_unique_slug(db_session, "en", "Lemon Tart") == "lemon-tart"

    def test_collision_appends_a_numeric_suffix(self, db_session: Session) -> None:
        recipe = Recipe(category_id=1, owner_user_id=1)
        recipe.translations.append(RecipeTranslation(language="en", title="Lemon Tart", slug="lemon-tart"))
        db_session.add(recipe)
        db_session.commit()

        assert generate_unique_slug(db_session, "en", "Lemon Tart") == "lemon-tart-2"

    def test_second_collision_increments_further(self, db_session: Session) -> None:
        first = Recipe(category_id=1, owner_user_id=1)
        first.translations.append(RecipeTranslation(language="en", title="Lemon Tart", slug="lemon-tart"))
        second = Recipe(category_id=1, owner_user_id=1)
        second.translations.append(
            RecipeTranslation(language="en", title="Lemon Tart 2", slug="lemon-tart-2")
        )
        db_session.add_all([first, second])
        db_session.commit()

        assert generate_unique_slug(db_session, "en", "Lemon Tart") == "lemon-tart-3"

    def test_collision_is_scoped_per_language(self, db_session: Session) -> None:
        recipe = Recipe(category_id=1, owner_user_id=1)
        recipe.translations.append(RecipeTranslation(language="en", title="Lemon Tart", slug="lemon-tart"))
        db_session.add(recipe)
        db_session.commit()

        # Same slug text is fine in a different language's own namespace.
        assert generate_unique_slug(db_session, "ro", "Lemon Tart") == "lemon-tart"

    def test_exclude_translation_id_lets_a_translation_keep_its_own_slug(self, db_session: Session) -> None:
        recipe = Recipe(category_id=1, owner_user_id=1)
        translation = RecipeTranslation(language="en", title="Lemon Tart", slug="lemon-tart")
        recipe.translations.append(translation)
        db_session.add(recipe)
        db_session.commit()
        db_session.refresh(translation)

        result = generate_unique_slug(
            db_session, "en", "Lemon Tart", exclude_translation_id=translation.id
        )
        assert result == "lemon-tart"
