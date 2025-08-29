"""Role-Based Access Control using Casbin."""

import os
from typing import List, Optional

import casbin
from casbin_sqlalchemy_adapter import Adapter
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.core.database import engine

settings = get_settings()

# Casbin model configuration
CASBIN_MODEL = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
"""


class RBACManager:
    """Role-Based Access Control manager using Casbin."""
    
    def __init__(self):
        self.enforcer: Optional[casbin.Enforcer] = None
        self.adapter: Optional[Adapter] = None
    
    async def initialize(self):
        """Initialize the RBAC system."""
        # Create Casbin adapter
        self.adapter = Adapter(engine.sync_engine)
        
        # Create model file
        model_path = "/tmp/casbin_model.conf"
        with open(model_path, "w") as f:
            f.write(CASBIN_MODEL)
        
        # Create enforcer
        self.enforcer = casbin.Enforcer(model_path, self.adapter)
        
        # Load default policies
        await self.load_default_policies()
    
    async def load_default_policies(self):
        """Load default RBAC policies."""
        if not self.enforcer:
            return
        
        # Define role hierarchy
        self.enforcer.add_grouping_policy("admin", "member")
        self.enforcer.add_grouping_policy("owner", "admin")
        
        # Define permissions for different resources
        resources = [
            "signals", "ideas", "reports", "workspaces", "users"
        ]
        
        actions = ["read", "write", "delete", "admin"]
        
        # Owner can do everything
        for resource in resources:
            for action in actions:
                self.enforcer.add_policy("owner", resource, action)
        
        # Admin can read/write but not admin actions on users/workspaces
        for resource in resources:
            if resource in ["users", "workspaces"]:
                self.enforcer.add_policy("admin", resource, "read")
                self.enforcer.add_policy("admin", resource, "write")
            else:
                for action in ["read", "write", "delete"]:
                    self.enforcer.add_policy("admin", resource, action)
        
        # Member can read/write their own data
        for resource in ["signals", "ideas", "reports"]:
            self.enforcer.add_policy("member", resource, "read")
            self.enforcer.add_policy("member", resource, "write")
        
        # Viewer can only read
        for resource in resources:
            self.enforcer.add_policy("viewer", resource, "read")
        
        # Save policies
        self.enforcer.save_policy()
    
    def check_permission(self, user_role: str, resource: str, action: str) -> bool:
        """Check if a user role has permission for a resource action."""
        if not self.enforcer:
            return False
        
        return self.enforcer.enforce(user_role, resource, action)
    
    def add_role_for_user(self, user_id: str, role: str, workspace_id: str) -> bool:
        """Add a role for a user in a workspace."""
        if not self.enforcer:
            return False
        
        subject = f"{user_id}:{workspace_id}"
        return self.enforcer.add_grouping_policy(subject, role)
    
    def remove_role_for_user(self, user_id: str, role: str, workspace_id: str) -> bool:
        """Remove a role for a user in a workspace."""
        if not self.enforcer:
            return False
        
        subject = f"{user_id}:{workspace_id}"
        return self.enforcer.remove_grouping_policy(subject, role)
    
    def get_roles_for_user(self, user_id: str, workspace_id: str) -> List[str]:
        """Get all roles for a user in a workspace."""
        if not self.enforcer:
            return []
        
        subject = f"{user_id}:{workspace_id}"
        return self.enforcer.get_roles_for_user(subject)


# Global RBAC manager instance
rbac_manager = RBACManager()
