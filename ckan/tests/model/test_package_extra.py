
import pytest

from ckan import model
from ckan.tests import factories


@pytest.mark.usefixtures("non_clean_db")
class TestPackageExtra:
    def test_create_extras(self):
        pkg = model.Package(name=factories.Dataset.stub().name)

        pkg.extras = {"accuracy": "metre"}

        model.Session.add_all([pkg])
        model.Session.commit()
        model.Session.remove()

        pkg = model.Package.by_name(pkg.name)
        assert pkg.extras == {"accuracy": "metre"}

    def test_delete_extras(self):

        dataset = factories.Dataset(
            extras=[
                {"key": "subject", "value": "science"},
                {"key": "accuracy", "value": "metre"},
            ]
        )
        pkg = model.Package.by_name(dataset["name"])

        del pkg.extras["subject"]
        model.Session.commit()
        model.Session.remove()

        pkg = model.Package.by_name(dataset["name"])
        assert pkg.extras == {"accuracy": "metre"}
