
from typing import Optional
import ckan.model.domain_object as domain_object


class System(domain_object.DomainObject):

    name = 'system'

    def __str__(self) -> str:
        return '<%s>' % self.__class__.__name__

    def purge(self) -> None:
        pass

    @classmethod
    def by_name(cls,
                name: str | None,
                autoflush: bool = True,
                for_update: bool = False) -> Optional["System"]:
        return System()
