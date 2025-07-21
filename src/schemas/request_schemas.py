from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator

class WhatsAppQueryRequest(BaseModel):
    """Request schema for WhatsApp query processing"""
    
    user_id: str = Field(
        ..., 
        min_length=1, 
        max_length=255,
        description="Unique identifier for the user"
    )
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=4000,
        description="User message content"
    )
    message_type: str = Field(
        default="text",
        description="Type of message (text, image, audio, document, etc.)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the message"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context information"
    )
    user_profile: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User profile information"
    )
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('user_id cannot be empty')
        return v.strip()
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError('message cannot be empty')
        return v.strip()
    
    @validator('message_type')
    def validate_message_type(cls, v):
        allowed_types = ['text', 'image', 'audio', 'video', 'document', 'location', 'contact']
        if v not in allowed_types:
            raise ValueError(f'message_type must be one of: {", ".join(allowed_types)}')
        return v

class FeedbackRequest(BaseModel):
    """Request schema for submitting feedback"""
    
    message_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ID of the message being rated"
    )
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ID of the user submitting feedback"
    )
    feedback_type: str = Field(
        ...,
        description="Type of feedback (thumbs_up, thumbs_down, rating, text, report)"
    )
    is_helpful: Optional[bool] = Field(
        default=None,
        description="Whether the response was helpful (true/false)"
    )
    rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Rating from 1 to 5 stars"
    )
    feedback_text: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Detailed feedback text"
    )
    category: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Feedback category (bug, feature, complaint, etc.)"
    )
    
    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        allowed_types = ['thumbs_up', 'thumbs_down', 'rating', 'text', 'report']
        if v not in allowed_types:
            raise ValueError(f'feedback_type must be one of: {", ".join(allowed_types)}')
        return v
    
    @validator('feedback_text')
    def validate_feedback_text(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

class UserProfileRequest(BaseModel):
    """Request schema for updating user profile"""
    
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique user identifier"
    )
    display_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User's display name"
    )
    phone_number: Optional[str] = Field(
        default=None,
        max_length=20,
        description="User's phone number"
    )
    language: Optional[str] = Field(
        default="en",
        max_length=10,
        description="Preferred language code (e.g., en, es, fr)"
    )
    timezone: Optional[str] = Field(
        default="UTC",
        max_length=50,
        description="User's timezone"
    )
    preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User preferences and settings"
    )
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is not None:
            # Basic phone number validation (can be enhanced)
            import re
            v = v.strip()
            if not re.match(r'^\+?[1-9]\d{1,14}$', v.replace(' ', '').replace('-', '')):
                raise ValueError('Invalid phone number format')
        return v
    
    @validator('language')
    def validate_language(cls, v):
        if v is not None:
            # Basic language code validation
            import re
            if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
                raise ValueError('Language must be in format "en" or "en-US"')
        return v

class ConversationRequest(BaseModel):
    """Request schema for conversation operations"""
    
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User identifier"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of messages to retrieve"
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include response metadata"
    )
    start_date: Optional[datetime] = Field(
        default=None,
        description="Start date for filtering messages"
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="End date for filtering messages"
    )
    message_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by specific message types"
    )
    
    @validator('message_types')
    def validate_message_types(cls, v):
        if v is not None:
            allowed_types = ['text', 'image', 'audio', 'video', 'document', 'location', 'contact']
            for msg_type in v:
                if msg_type not in allowed_types:
                    raise ValueError(f'Invalid message_type: {msg_type}. Must be one of: {", ".join(allowed_types)}')
        return v
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v is not None and 'start_date' in values and values['start_date'] is not None:
            if v <= values['start_date']:
                raise ValueError('end_date must be after start_date')
        return v

class AnalyticsRequest(BaseModel):
    """Request schema for analytics queries"""
    
    period_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Analysis period in days"
    )
    metric_types: Optional[List[str]] = Field(
        default=None,
        description="Specific metrics to include"
    )
    group_by: Optional[str] = Field(
        default=None,
        description="Group results by (day, week, month, user, etc.)"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional filters to apply"
    )
    
    @validator('group_by')
    def validate_group_by(cls, v):
        if v is not None:
            allowed_values = ['day', 'week', 'month', 'user', 'message_type', 'feedback_type']
            if v not in allowed_values:
                raise ValueError(f'group_by must be one of: {", ".join(allowed_values)}')
        return v

class HealthCheckRequest(BaseModel):
    """Request schema for health check operations"""
    
    include_details: bool = Field(
        default=True,
        description="Whether to include detailed health information"
    )
    check_services: Optional[List[str]] = Field(
        default=None,
        description="Specific services to check"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout for health checks in seconds"
    )

class BulkOperationRequest(BaseModel):
    """Request schema for bulk operations"""
    
    operation_type: str = Field(
        ...,
        description="Type of bulk operation (delete, export, update, etc.)"
    )
    filters: Dict[str, Any] = Field(
        ...,
        description="Filters to determine which records to process"
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional options for the operation"
    )
    dry_run: bool = Field(
        default=True,
        description="Whether to perform a dry run (no actual changes)"
    )
    
    @validator('operation_type')
    def validate_operation_type(cls, v):
        allowed_operations = ['delete', 'export', 'update', 'archive', 'restore']
        if v not in allowed_operations:
            raise ValueError(f'operation_type must be one of: {", ".join(allowed_operations)}')
        return v
