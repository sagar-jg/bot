from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .base_schemas import BaseResponse, MetadataModel

class WhatsAppQueryResponse(BaseResponse):
    """Response schema for WhatsApp query processing"""
    
    response: str = Field(
        description="AI-generated response to the user message"
    )
    message_id: str = Field(
        description="Unique identifier for this Q&A exchange"
    )
    user_id: str = Field(
        description="User identifier"
    )
    response_time_ms: Optional[int] = Field(
        default=None,
        description="Response generation time in milliseconds"
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for the response (0-1)"
    )
    tools_used: Optional[List[str]] = Field(
        default=None,
        description="List of tools/services used to generate the response"
    )
    search_results_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of search results used"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional response metadata"
    )
    suggestions: Optional[List[str]] = Field(
        default=None,
        description="Suggested follow-up questions or actions"
    )
    requires_human: bool = Field(
        default=False,
        description="Whether this query requires human intervention"
    )

class FeedbackResponse(BaseResponse):
    """Response schema for feedback submission"""
    
    feedback_id: str = Field(
        description="Unique identifier for the submitted feedback"
    )
    message: str = Field(
        description="Confirmation message"
    )
    feedback_type: str = Field(
        description="Type of feedback that was submitted"
    )
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the feedback was processed"
    )
    impact_score: Optional[float] = Field(
        default=None,
        description="Estimated impact of this feedback on system improvement"
    )

class ConversationMessage(BaseModel):
    """Schema for individual conversation messages"""
    
    message_id: str = Field(description="Unique message identifier")
    sender: str = Field(description="Message sender (user/assistant/system)")
    message_text: str = Field(description="Message content")
    message_type: str = Field(default="text", description="Type of message")
    timestamp: datetime = Field(description="Message timestamp")
    
    # Optional response metadata (for assistant messages)
    response_time_ms: Optional[int] = Field(default=None)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tools_used: Optional[List[str]] = Field(default=None)
    search_results_count: Optional[int] = Field(default=None)
    
    # Additional fields
    attachments: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Message attachments"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional message metadata"
    )
    edited: bool = Field(
        default=False,
        description="Whether the message was edited"
    )
    flagged: bool = Field(
        default=False,
        description="Whether the message was flagged for review"
    )

class ConversationHistoryResponse(BaseResponse):
    """Response schema for conversation history"""
    
    user_id: str = Field(description="User identifier")
    messages: List[ConversationMessage] = Field(
        description="List of conversation messages"
    )
    total_messages: int = Field(
        ge=0,
        description="Total number of messages in the conversation"
    )
    limit: int = Field(
        ge=1,
        description="Limit applied to the query"
    )
    include_metadata: bool = Field(
        description="Whether metadata was included"
    )
    conversation_stats: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Conversation statistics"
    )
    user_profile: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User profile information"
    )

class FeedbackSummary(BaseModel):
    """Summary of feedback metrics"""
    
    total_feedback: int = Field(ge=0, description="Total feedback received")
    positive_feedback: int = Field(ge=0, description="Positive feedback count")
    negative_feedback: int = Field(ge=0, description="Negative feedback count")
    satisfaction_rate: float = Field(
        ge=0.0, 
        le=100.0, 
        description="Satisfaction rate as percentage"
    )
    average_rating: float = Field(
        ge=0.0, 
        le=5.0, 
        description="Average rating score"
    )
    feedback_by_type: Dict[str, int] = Field(
        description="Breakdown of feedback by type"
    )
    recent_trends: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Recent feedback trends"
    )

class AnalyticsResponse(BaseResponse):
    """Response schema for analytics data"""
    
    period_days: int = Field(
        ge=1,
        description="Analysis period in days"
    )
    summary: FeedbackSummary = Field(
        description="Summary of feedback analytics"
    )
    insights: List[str] = Field(
        description="AI-generated insights from the data"
    )
    recommendations: Optional[List[str]] = Field(
        default=None,
        description="Recommended actions based on analytics"
    )
    data_quality: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Information about data quality and completeness"
    )
    export_url: Optional[str] = Field(
        default=None,
        description="URL to download detailed analytics data"
    )

class HealthStatus(BaseModel):
    """Individual component health status"""
    
    component: str = Field(description="Component name")
    status: str = Field(description="Health status (healthy/degraded/unhealthy/critical)")
    response_time_ms: Optional[float] = Field(
        default=None,
        ge=0,
        description="Component response time"
    )
    last_checked: datetime = Field(
        description="Last health check timestamp"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed health information"
    )
    metrics: Optional[Dict[str, float]] = Field(
        default=None,
        description="Performance metrics"
    )

class SystemResources(BaseModel):
    """System resource usage information"""
    
    cpu_usage_percent: float = Field(
        ge=0.0, 
        le=100.0, 
        description="CPU usage percentage"
    )
    memory_usage_percent: float = Field(
        ge=0.0, 
        le=100.0, 
        description="Memory usage percentage"
    )
    disk_usage_percent: float = Field(
        ge=0.0, 
        le=100.0, 
        description="Disk usage percentage"
    )
    available_memory_gb: float = Field(
        ge=0.0,
        description="Available memory in GB"
    )
    available_disk_gb: float = Field(
        ge=0.0,
        description="Available disk space in GB"
    )
    network_io: Optional[Dict[str, int]] = Field(
        default=None,
        description="Network I/O statistics"
    )

class HealthResponse(BaseResponse):
    """Response schema for health checks"""
    
    status: str = Field(
        description="Overall system health status"
    )
    components: List[HealthStatus] = Field(
        description="Health status of individual components"
    )
    system_resources: Optional[SystemResources] = Field(
        default=None,
        description="System resource usage"
    )
    alerts: List[str] = Field(
        default=[],
        description="Active alerts and warnings"
    )
    uptime_seconds: Optional[float] = Field(
        default=None,
        ge=0,
        description="System uptime in seconds"
    )
    environment: str = Field(
        description="Current environment (dev/uat/prod)"
    )
    version: str = Field(
        description="Application version"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if health check failed"
    )

class UserProfileResponse(BaseResponse):
    """Response schema for user profile operations"""
    
    user_id: str = Field(description="User identifier")
    display_name: Optional[str] = Field(default=None, description="User display name")
    phone_number: Optional[str] = Field(default=None, description="User phone number")
    language: str = Field(default="en", description="User preferred language")
    timezone: str = Field(default="UTC", description="User timezone")
    status: str = Field(description="User account status")
    
    # Statistics
    total_messages: int = Field(ge=0, description="Total messages sent by user")
    first_message_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of first message"
    )
    last_message_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last message"
    )
    
    # Engagement metrics
    engagement_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="User engagement score (0-1)"
    )
    satisfaction_rating: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Average satisfaction rating"
    )
    
    # Preferences and metadata
    preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User preferences"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional user metadata"
    )

class BulkOperationResponse(BaseResponse):
    """Response schema for bulk operations"""
    
    operation_id: str = Field(description="Unique operation identifier")
    operation_type: str = Field(description="Type of operation performed")
    status: str = Field(description="Operation status (pending/running/completed/failed)")
    
    # Results
    total_records: int = Field(ge=0, description="Total records processed")
    successful_records: int = Field(ge=0, description="Successfully processed records")
    failed_records: int = Field(ge=0, description="Failed records")
    
    # Timing
    started_at: datetime = Field(description="Operation start time")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Operation completion time"
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        ge=0,
        description="Operation duration in seconds"
    )
    
    # Additional information
    errors: Optional[List[str]] = Field(
        default=None,
        description="List of errors encountered"
    )
    warnings: Optional[List[str]] = Field(
        default=None,
        description="List of warnings"
    )
    download_url: Optional[str] = Field(
        default=None,
        description="URL to download operation results"
    )
    dry_run: bool = Field(
        default=False,
        description="Whether this was a dry run"
    )

class ExportResponse(BaseResponse):
    """Response schema for data export operations"""
    
    export_id: str = Field(description="Unique export identifier")
    format: str = Field(description="Export format (csv, json, xlsx, etc.)")
    status: str = Field(description="Export status")
    
    # File information
    file_size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="File size in bytes"
    )
    download_url: Optional[str] = Field(
        default=None,
        description="URL to download the export file"
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When the download link expires"
    )
    
    # Export statistics
    record_count: int = Field(ge=0, description="Number of records exported")
    filters_applied: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Filters that were applied during export"
    )
    
    # Processing information
    processing_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Export processing time in milliseconds"
    )
