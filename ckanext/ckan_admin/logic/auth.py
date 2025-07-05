from __future__ import annotations

from ckan.types import AuthResult, Context, DataDict


def ckan_admin_access(context: Context, data_dict: DataDict) -> AuthResult:
    """Only sysadmins are authorized to access admin panel"""
    return {"success": False}
