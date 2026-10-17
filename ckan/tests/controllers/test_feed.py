
import pytest

from ckan.lib.helpers import url_for

import ckan.tests.helpers as helpers
import ckan.tests.factories as factories


@pytest.mark.usefixtures("clean_db")
class TestFeeds:
    @pytest.mark.parametrize("page", [0, -2, "abc"])
    def test_atom_feed_incorrect_page_gives_error(self, page, app):
        group = factories.Group()
        offset = url_for(
            "feeds.group", id=group["name"]
        ) + f"?page={page}"
        res = app.get(offset, status=400)
        assert (
            "&#34;page&#34; parameter must be a positive integer" in res
        ), res

    def test_general_atom_feed_works(self, app):
        dataset = factories.Dataset(notes="Test\x0c Notes")
        offset = url_for("feeds.general")
        res = app.get(offset)
        assert helpers.body_contains(res, "<title>{0}</title>".format(dataset["title"]))
        assert helpers.body_contains(res, "<content>Test Notes</content>")

    def test_general_atom_feed_works_with_no_notes(self, app):
        dataset = factories.Dataset(notes=None)
        offset = url_for("feeds.general")
        res = app.get(offset)
        assert helpers.body_contains(res, "<title>{0}</title>".format(dataset["title"]))
        assert helpers.body_contains(res, "<content/>")

    def test_group_atom_feed_works(self, app):
        group = factories.Group()
        dataset = factories.Dataset(groups=[{"id": group["id"]}])
        offset = url_for("feeds.group", id=group["name"])
        res = app.get(offset)

        assert helpers.body_contains(res, "<title>{0}</title>".format(dataset["title"]))

    def test_organization_atom_feed_works(self, app):
        group = factories.Organization()
        dataset = factories.Dataset(owner_org=group["id"])
        offset = url_for("feeds.organization", id=group["name"])
        res = app.get(offset)

        assert helpers.body_contains(res, "<title>{0}</title>".format(dataset["title"]))

    def test_custom_atom_feed_works(self, app):
        dataset1 = factories.Dataset(
            title="Test weekly",
            extras=[{"key": "frequency", "value": "weekly"}],
        )
        dataset2 = factories.Dataset(
            title="Test daily",
            extras=[{"key": "frequency", "value": "daily"}],
        )

        offset = url_for("feeds.custom")
        params = {"q": "frequency:weekly"}

        res = app.get(offset, query_string=params)

        assert helpers.body_contains(res, "<title>{0}</title>".format(dataset1["title"]))

        assert not helpers.body_contains(res, '<title">{0}</title>'.format(dataset2["title"]))
