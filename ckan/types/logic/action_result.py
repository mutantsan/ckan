from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union
from collections.abc import Sequence

from typing_extensions import TypedDict
from typing import TypeAlias

if TYPE_CHECKING:
    import ckan.model as model
    from ckan.types import Query

AnyDict: TypeAlias = "dict[str, Any]"
###############################################################################
#                                     get                                     #
###############################################################################
PackageList = Sequence[str]
CurrentPackageListWithResources = list[AnyDict]
MemberList = list[tuple[Any, ...]]
PackageCollaboratorList = list[AnyDict]
PackageCollaboratorListForUser = PackageCollaboratorList
GroupList = list[AnyDict]
OrganizationList = list[AnyDict]
GroupListAuthz = list[AnyDict]
OrganizationListForUser = list[AnyDict]
LicenseList = list[AnyDict]
TagList = Union[list[AnyDict], list[str]]
UserList = Union[list[AnyDict], list[str], "Query[model.User]"]
PackageRelationshipsList = list[AnyDict]
PackageShow = AnyDict
ResourceShow = AnyDict
ResourceViewShow = AnyDict
ResourceViewList = list[AnyDict]
GroupShow = AnyDict
OrganizationShow = AnyDict
GroupPackageShow = list[AnyDict]
TagShow = AnyDict
UserShow = AnyDict
PackageAutocomplete = list[AnyDict]
FormatAutocomplete = list[str]
UserAutocomplete = list[AnyDict]
GroupAutocomplete = list[AnyDict]
OrganizationAutocomplete = list[AnyDict]
PackageSearch = AnyDict
ResourceSearch = AnyDict
TagSearch = AnyDict
TagAutocomplete = list[str]
TaskStatusShow = AnyDict
TermTranslationShow = list[AnyDict]
GetSiteUser = AnyDict
StatusShow = AnyDict
VocabularyList = list[AnyDict]
VocabularyShow = AnyDict
UserFollowerCount = int
DatasetFollowerCount = int
GroupFollowerCount = int
OrganizationFollowerCount = int
UserFollowerList = list[AnyDict]
DatasetFollowerList = list[AnyDict]
GroupFollowerList = list[AnyDict]
OrganizationFollowerList = list[AnyDict]
AmFollowingUser = bool
AmFollowingDataset = bool
AmFollowingGroup = bool
FolloweeCount = int
UserFolloweeCount = int
DatasetFolloweeCount = int
GroupFolloweeCount = int
OrganizationFolloweeCount = int
FolloweeList = list[AnyDict]
UserFolloweeList = list[AnyDict]
DatasetFolloweeList = list[AnyDict]
GroupFolloweeList = list[AnyDict]
OrganizationFolloweeList = list[AnyDict]
DashboardNewActivitiesCount = int
MemberRolesList = list[AnyDict]
HelpShow = Optional[str]
ConfigOptionShow = Any
ConfigOptionList = list[str]
JobList = Union[list[AnyDict], list[str]]
JobShow = AnyDict
ApiTokenList = list[AnyDict]

###############################################################################
#                                    create                                   #
###############################################################################
PackageCreate = Union[AnyDict, str]
ResourceCreate = AnyDict
ResourceViewCreate = AnyDict
ResourceCreateDefaultResourceViews = list[AnyDict]
PackageCreateDefaultResourceViews = list[AnyDict]
PackageRelationshipCreate = AnyDict
MemberCreate = AnyDict
PackageCollaboratorCreate = AnyDict
GroupCreate = Union[str, AnyDict]
OrganizationCreate = Union[str, AnyDict]
UserCreate = AnyDict
UserInvite = AnyDict
VocabularyCreate = AnyDict
TagCreate = AnyDict
FollowUser = AnyDict
FollowDataset = AnyDict
GroupOrOrgMemberCreate = AnyDict
GroupMemberCreate = AnyDict
OrganizationMemberCreate = AnyDict
FollowGroup = AnyDict
ApiTokenCreate = AnyDict

###############################################################################
#                                    delete                                   #
###############################################################################
UserDelete: TypeAlias = None
PackageDelete: TypeAlias = None
DatasetPurge: TypeAlias = None
ResourceDelete: TypeAlias = None
ResourceViewDelete: TypeAlias = AnyDict
ResourceViewClear: TypeAlias = None
PackageRelationshipDelete: TypeAlias = None
MemberDelete: TypeAlias = None
PackageCollaboratorDelete: TypeAlias = None
GroupDelete: TypeAlias = None
OrganizationDelete: TypeAlias = None
ApiTokenRevoke: TypeAlias = None

###############################################################################
#                                    patch                                    #
###############################################################################
PackagePatch = Union[str, AnyDict]
ResourcePatch = AnyDict
GroupPatch = AnyDict
OrganizationPatch = AnyDict
UserPatch = AnyDict

###############################################################################
#                                    update                                   #
###############################################################################
ResourceUpdate = AnyDict
ResourceViewUpdate = AnyDict
ResourceViewReorder = AnyDict
PackageUpdate = Union[str, AnyDict]
ConfigOptionUpdate = AnyDict
PackageRevise = AnyDict
PackageResourceReorder = AnyDict
PackageRelationshipUpdate = AnyDict
GroupUpdate = AnyDict
OrganizationUpdate = AnyDict
UserUpdate = AnyDict
UserGenerateApikey = AnyDict
TaskStatusUpdate = AnyDict
TaskStatusUpdateMany = AnyDict
TermTranslationUpdate = AnyDict
TermTranslationUpdateMany = AnyDict
VocabularyUpdate = AnyDict
DashboardMarkActivitiesOld: TypeAlias = None
SendEmailNotifications: TypeAlias = None
PackageOwnerOrgUpdate: TypeAlias = None
BulkUpdatePrivate: TypeAlias = None
BulkUpdatePublic: TypeAlias = None
BulkUpdateDelete: TypeAlias = None

###############################################################################
#                                     File                                    #
###############################################################################
class FileSearch(TypedDict):
    count: int
    results: list[FileShow]

FileCreate = dict[str, Any]
FileRegister = dict[str, Any]
FileDelete = dict[str, Any]
FileShow = dict[str, Any]
FileRename = dict[str, Any]
FilePin = dict[str, Any]
FileUnpin = dict[str, Any]
FileOwnershipTransfer = dict[str, Any]
FileOwnerScan = FileSearch
