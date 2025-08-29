"""Security service for workspace isolation, encryption, and access control."""

import os
import secrets
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import boto3
from botocore.exceptions import ClientError
import structlog

from api.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class SecurityService:
    """Service for security, encryption, and access control."""
    
    def __init__(self):
        self.kms_client = None
        if settings.s3_access_key and settings.s3_secret_key:
            self.kms_client = boto3.client(
                'kms',
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name='us-west-2'  # Default region
            )
        
        # Token vault for secure storage
        self.token_vault = {}
        
        # Rate limiting storage
        self.rate_limits = {}
        
        # Security policies
        self.security_policies = {
            "password_min_length": 12,
            "password_require_special": True,
            "password_require_numbers": True,
            "password_require_uppercase": True,
            "session_timeout_hours": 24,
            "max_login_attempts": 5,
            "lockout_duration_minutes": 30,
            "token_expiry_hours": 1,
            "api_rate_limit_per_minute": 100,
            "export_rate_limit_per_hour": 10
        }
    
    async def create_workspace_encryption_key(self, workspace_id: str) -> Dict[str, Any]:
        """Create per-workspace encryption key using KMS."""
        
        try:
            if self.kms_client:
                # Create KMS key for workspace
                response = self.kms_client.create_key(
                    Description=f"Encryption key for workspace {workspace_id}",
                    Usage='ENCRYPT_DECRYPT',
                    KeySpec='SYMMETRIC_DEFAULT',
                    Tags=[
                        {
                            'TagKey': 'workspace_id',
                            'TagValue': workspace_id
                        },
                        {
                            'TagKey': 'service',
                            'TagValue': 'ai-venture-architect'
                        }
                    ]
                )
                
                key_id = response['KeyMetadata']['KeyId']
                key_arn = response['KeyMetadata']['Arn']
                
                # Create alias for easier reference
                alias_name = f"alias/workspace-{workspace_id}"
                try:
                    self.kms_client.create_alias(
                        AliasName=alias_name,
                        TargetKeyId=key_id
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] != 'AlreadyExistsException':
                        raise
                
                return {
                    "key_id": key_id,
                    "key_arn": key_arn,
                    "alias": alias_name,
                    "provider": "aws_kms"
                }
            else:
                # Fallback to local encryption key
                key = Fernet.generate_key()
                return {
                    "key_id": f"local-{workspace_id}",
                    "key_data": key.decode(),
                    "provider": "local"
                }
                
        except Exception as e:
            logger.error(f"Failed to create workspace encryption key: {e}")
            # Fallback to local key
            key = Fernet.generate_key()
            return {
                "key_id": f"local-{workspace_id}",
                "key_data": key.decode(),
                "provider": "local"
            }
    
    async def encrypt_sensitive_data(
        self, 
        data: str, 
        workspace_id: str,
        key_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Encrypt sensitive data using workspace-specific key."""
        
        try:
            if key_info and key_info.get("provider") == "aws_kms" and self.kms_client:
                # Use KMS encryption
                response = self.kms_client.encrypt(
                    KeyId=key_info["key_id"],
                    Plaintext=data.encode(),
                    EncryptionContext={
                        'workspace_id': workspace_id,
                        'service': 'ai-venture-architect'
                    }
                )
                
                encrypted_data = base64.b64encode(response['CiphertextBlob']).decode()
                
                return {
                    "encrypted_data": encrypted_data,
                    "encryption_method": "aws_kms",
                    "key_id": key_info["key_id"],
                    "encrypted_at": datetime.utcnow().isoformat()
                }
            else:
                # Use local encryption
                if key_info and "key_data" in key_info:
                    key = key_info["key_data"].encode()
                else:
                    # Generate new key if not provided
                    key = Fernet.generate_key()
                
                fernet = Fernet(key)
                encrypted_data = fernet.encrypt(data.encode()).decode()
                
                return {
                    "encrypted_data": encrypted_data,
                    "encryption_method": "fernet",
                    "key_data": key.decode() if not key_info else None,
                    "encrypted_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    async def decrypt_sensitive_data(
        self, 
        encrypted_info: Dict[str, Any], 
        workspace_id: str
    ) -> str:
        """Decrypt sensitive data."""
        
        try:
            if encrypted_info.get("encryption_method") == "aws_kms" and self.kms_client:
                # Use KMS decryption
                encrypted_data = base64.b64decode(encrypted_info["encrypted_data"])
                
                response = self.kms_client.decrypt(
                    CiphertextBlob=encrypted_data,
                    EncryptionContext={
                        'workspace_id': workspace_id,
                        'service': 'ai-venture-architect'
                    }
                )
                
                return response['Plaintext'].decode()
            else:
                # Use local decryption
                key = encrypted_info.get("key_data", "").encode()
                if not key:
                    raise ValueError("Encryption key not available")
                
                fernet = Fernet(key)
                decrypted_data = fernet.decrypt(encrypted_info["encrypted_data"].encode())
                
                return decrypted_data.decode()
                
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token."""
        return secrets.token_urlsafe(length)
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        """Hash password with salt."""
        if salt is None:
            salt = os.urandom(32)
        
        # Use PBKDF2 with SHA256
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = kdf.derive(password.encode())
        
        return base64.b64encode(key).decode(), base64.b64encode(salt).decode()
    
    def verify_password(self, password: str, hashed_password: str, salt: str) -> bool:
        """Verify password against hash."""
        try:
            salt_bytes = base64.b64decode(salt.encode())
            expected_hash = base64.b64decode(hashed_password.encode())
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt_bytes,
                iterations=100000,
            )
            
            kdf.verify(password.encode(), expected_hash)
            return True
        except Exception:
            return False
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """Validate password against security policy."""
        
        issues = []
        score = 0
        
        # Length check
        if len(password) < self.security_policies["password_min_length"]:
            issues.append(f"Password must be at least {self.security_policies['password_min_length']} characters")
        else:
            score += 25
        
        # Uppercase check
        if self.security_policies["password_require_uppercase"] and not any(c.isupper() for c in password):
            issues.append("Password must contain at least one uppercase letter")
        else:
            score += 25
        
        # Numbers check
        if self.security_policies["password_require_numbers"] and not any(c.isdigit() for c in password):
            issues.append("Password must contain at least one number")
        else:
            score += 25
        
        # Special characters check
        if self.security_policies["password_require_special"]:
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                issues.append("Password must contain at least one special character")
            else:
                score += 25
        
        # Common password check (simplified)
        common_passwords = ["password", "123456", "qwerty", "admin", "letmein"]
        if password.lower() in common_passwords:
            issues.append("Password is too common")
            score = max(0, score - 50)
        
        return {
            "valid": len(issues) == 0,
            "score": score,
            "issues": issues,
            "strength": "strong" if score >= 100 else "medium" if score >= 75 else "weak"
        }
    
    async def create_signed_url(
        self, 
        resource_path: str, 
        workspace_id: str,
        expiry_hours: int = 24,
        permissions: List[str] = None
    ) -> Dict[str, Any]:
        """Create signed URL for secure resource access."""
        
        permissions = permissions or ["read"]
        
        # Generate secure token
        token = self.generate_secure_token()
        
        # Create signature
        expiry_time = datetime.utcnow() + timedelta(hours=expiry_hours)
        
        # Create payload for signing
        payload = f"{resource_path}|{workspace_id}|{expiry_time.isoformat()}|{','.join(permissions)}"
        
        # Sign with workspace key (simplified - in production use proper signing)
        signature = hashlib.sha256(f"{payload}|{settings.jwt_secret_key}".encode()).hexdigest()
        
        # Store token info
        self.token_vault[token] = {
            "resource_path": resource_path,
            "workspace_id": workspace_id,
            "permissions": permissions,
            "expires_at": expiry_time,
            "signature": signature,
            "created_at": datetime.utcnow()
        }
        
        # Create signed URL
        signed_url = f"/api/v1/secure/{token}/{resource_path}"
        
        return {
            "signed_url": signed_url,
            "token": token,
            "expires_at": expiry_time.isoformat(),
            "permissions": permissions
        }
    
    async def verify_signed_url(self, token: str, requested_path: str) -> Dict[str, Any]:
        """Verify signed URL token."""
        
        token_info = self.token_vault.get(token)
        if not token_info:
            return {"valid": False, "error": "Token not found"}
        
        # Check expiry
        if datetime.utcnow() > token_info["expires_at"]:
            # Clean up expired token
            del self.token_vault[token]
            return {"valid": False, "error": "Token expired"}
        
        # Check path
        if token_info["resource_path"] != requested_path:
            return {"valid": False, "error": "Path mismatch"}
        
        # Verify signature
        payload = f"{token_info['resource_path']}|{token_info['workspace_id']}|{token_info['expires_at'].isoformat()}|{','.join(token_info['permissions'])}"
        expected_signature = hashlib.sha256(f"{payload}|{settings.jwt_secret_key}".encode()).hexdigest()
        
        if token_info["signature"] != expected_signature:
            return {"valid": False, "error": "Invalid signature"}
        
        return {
            "valid": True,
            "workspace_id": token_info["workspace_id"],
            "permissions": token_info["permissions"],
            "expires_at": token_info["expires_at"].isoformat()
        }
    
    async def check_rate_limit(
        self, 
        identifier: str, 
        limit_type: str = "api",
        custom_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Check rate limiting for requests."""
        
        current_time = datetime.utcnow()
        
        # Get rate limit configuration
        if limit_type == "api":
            limit = custom_limit or self.security_policies["api_rate_limit_per_minute"]
            window_minutes = 1
        elif limit_type == "export":
            limit = custom_limit or self.security_policies["export_rate_limit_per_hour"]
            window_minutes = 60
        else:
            limit = custom_limit or 10
            window_minutes = 1
        
        # Initialize rate limit tracking
        if identifier not in self.rate_limits:
            self.rate_limits[identifier] = []
        
        # Clean old entries
        cutoff_time = current_time - timedelta(minutes=window_minutes)
        self.rate_limits[identifier] = [
            timestamp for timestamp in self.rate_limits[identifier]
            if timestamp > cutoff_time
        ]
        
        # Check current count
        current_count = len(self.rate_limits[identifier])
        
        if current_count >= limit:
            return {
                "allowed": False,
                "current_count": current_count,
                "limit": limit,
                "window_minutes": window_minutes,
                "reset_at": (current_time + timedelta(minutes=window_minutes)).isoformat()
            }
        
        # Add current request
        self.rate_limits[identifier].append(current_time)
        
        return {
            "allowed": True,
            "current_count": current_count + 1,
            "limit": limit,
            "window_minutes": window_minutes,
            "remaining": limit - current_count - 1
        }
    
    async def audit_log_event(
        self,
        workspace_id: str,
        user_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Log security-relevant events for audit trail."""
        
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "workspace_id": workspace_id,
            "user_id": user_id,
            "event_type": event_type,  # create, read, update, delete, export, etc.
            "resource_type": resource_type,  # idea, signal, report, etc.
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": "0.0.0.0",  # Would be populated from request
            "user_agent": "unknown"   # Would be populated from request
        }
        
        # In production, this would be stored in a secure audit log
        logger.info("Audit event", **audit_entry)
        
        return audit_entry
    
    async def implement_data_deletion(
        self,
        workspace_id: str,
        user_id: str,
        deletion_type: str = "user_data"
    ) -> Dict[str, Any]:
        """Implement secure data deletion for GDPR compliance."""
        
        deletion_tasks = []
        
        if deletion_type == "user_data":
            deletion_tasks = [
                "Delete user profile and settings",
                "Remove user from workspace memberships",
                "Anonymize user-created content",
                "Clear user session tokens",
                "Remove user from audit logs (where legally permitted)"
            ]
        elif deletion_type == "workspace_data":
            deletion_tasks = [
                "Delete all workspace signals and ideas",
                "Remove workspace reports and exports",
                "Delete workspace encryption keys",
                "Clear workspace audit logs",
                "Remove workspace from billing system"
            ]
        
        # Log deletion request
        await self.audit_log_event(
            workspace_id=workspace_id,
            user_id=user_id,
            event_type="data_deletion_requested",
            resource_type="workspace" if deletion_type == "workspace_data" else "user",
            resource_id=workspace_id if deletion_type == "workspace_data" else user_id,
            details={"deletion_type": deletion_type, "tasks": deletion_tasks}
        )
        
        return {
            "deletion_id": self.generate_secure_token(),
            "deletion_type": deletion_type,
            "status": "initiated",
            "tasks": deletion_tasks,
            "estimated_completion": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "contact_email": "privacy@ai-venture-architect.com"
        }
    
    async def export_user_data(
        self,
        workspace_id: str,
        user_id: str,
        export_format: str = "json"
    ) -> Dict[str, Any]:
        """Export user data for GDPR compliance."""
        
        # This would collect all user data from various tables
        user_data = {
            "export_info": {
                "generated_at": datetime.utcnow().isoformat(),
                "workspace_id": workspace_id,
                "user_id": user_id,
                "format": export_format
            },
            "profile": {
                "user_id": user_id,
                "created_at": "2024-01-01T00:00:00Z",
                "last_login": "2024-01-15T10:30:00Z"
            },
            "ideas_created": [],
            "reports_generated": [],
            "search_history": [],
            "audit_trail": []
        }
        
        # Log export request
        await self.audit_log_event(
            workspace_id=workspace_id,
            user_id=user_id,
            event_type="data_export_requested",
            resource_type="user",
            resource_id=user_id,
            details={"export_format": export_format}
        )
        
        return {
            "export_id": self.generate_secure_token(),
            "status": "completed",
            "data": user_data,
            "format": export_format,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers for HTTP responses."""
        
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            ),
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            )
        }


# Global security service instance
security_service = SecurityService()
