
import pytest

from ckan import model
from ckan.tests import factories


@pytest.mark.usefixtures("non_clean_db")
class TestPackage:
    def test_create(self):
        # Demonstrate creating a package.
        #
        # In practice this is done by a combination of:
        # * ckan.logic.action.create:package_create
        # * ckan.lib.dictization.model_save.py:package_dict_save
        # etc

        pkg = model.Package(name=factories.Dataset.stub().name)
        pkg.notes = "Some notes"
        pkg.author = "bob"
        pkg.license_id = "odc-by"

        model.Session.add(pkg)
        model.Session.commit()
        model.Session.remove()

        pkg = model.Package.by_name(pkg.name)
        assert pkg.notes == "Some notes"
        assert pkg.author == "bob"
        assert pkg.license_id == "odc-by"
        assert pkg.license.title == "Open Data Commons Attribution License"

    def test_as_dict(self):
        pkg = model.Package.by_name(
            factories.Dataset(license_id="cc-by")["name"]
        )
        out = pkg.as_dict()
        assert out["name"] == pkg.name
        assert out["license"] == pkg.license.title
        assert out["license_id"] == pkg.license.id
        assert out["tags"] == [tag.name for tag in pkg.get_tags()]
        assert out["metadata_modified"] == pkg.metadata_modified.isoformat()
        assert out["metadata_created"] == pkg.metadata_created.isoformat()
        assert out["notes"] == pkg.notes

    def test_update(self):
        dataset = factories.Dataset()
        pkg = model.Package.by_name(dataset["name"])

        pkg.author = "bob"
        model.Session.commit()
        model.Session.remove()

        pkg = model.Package.by_name(dataset["name"])
        assert pkg.author == "bob"

    def test_delete(self):
        group = factories.Group()
        dataset = factories.Dataset(
            groups=[{"id": group["id"]}],
            tags=[{"name": factories.Tag.stub().name}],
            extras=[{"key": "subject", "value": "science"}],
        )
        pkg = model.Package.by_name(dataset["name"])

        pkg.delete()
        model.Session.commit()
        model.Session.remove()

        pkg = model.Package.by_name(dataset["name"])
        assert pkg.state == "deleted"

        # it is removed from the group
        group = model.Group.get(group["id"])
        assert [p.name for p in group.packages()] == []

        # other related objects don't change
        package_tag = (
            model.Session.query(model.PackageTag)
            .filter_by(package_id=pkg.id)
            .all()[0]
        )
        assert package_tag.state == "active"

        # it is removed from the tag
        tag = (
            model.Session.query(model.Tag)
            .filter_by(id=package_tag.tag_id)
            .all()[0]
        )
        assert [p.name for p in tag.packages] == []

    def test_purge(self):
        org = factories.Organization()
        group = factories.Group()
        tag_name = factories.Tag.stub().name
        dataset = factories.Dataset(
            resources=[
                {
                    "url": "http://example.com/image.png",
                    "format": "png",
                    "name": "Image 1",
                }
            ],
            tags=[{"name": tag_name}],
            extras=[{"key": "subject", "value": "science"}],
            groups=[{"id": group["id"]}],
            owner_org=org["id"],
        )
        pkg = model.Package.by_name(dataset["name"])

        pkg.purge()
        model.Session.commit()
        model.Session.remove()

        assert (
            not model.Session.query(model.Package).filter_by(id=pkg.id).all()
        )
        # the purge cascades to some objects
        assert (
            not model.Session.query(model.PackageTag)
            .filter_by(package_id=pkg.id)
            .all()
        )
        assert (
            not model.Session.query(model.Resource)
            .filter_by(package_id=pkg.id)
            .all()
        )
        # org remains, just not attached to the package
        org = model.Group.get(org["id"])
        assert org.packages() == []
        # tag object remains, just not attached to the package
        tag = model.Session.query(model.Tag).filter_by(name=tag_name).all()[0]
        assert tag.packages == []
        # group object remains, just not attached to the package
        group = model.Group.get(group["id"])
        assert group.packages() == []
