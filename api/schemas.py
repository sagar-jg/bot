# uwsbot/api/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class WhatsAppQueryRequest(BaseModel):
    """Enhanced request schema for WhatsApp queries"""
    user_id: str = Field(..., description="Unique user identifier (e.g., phone number)")
    message: str = Field(..., description="User message content", min_length=1, max_length=4000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "+919449248040",
                "message": "What are the admission requirements for Computer Science?"
            }
        }

class WhatsAppQueryResponse(BaseModel):
    """Enhanced response schema with message tracking"""
    response: str = Field(..., description="Assistant response text")
    message_id: str = Field(..., description="Unique identifier for this response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional response metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "For Computer Science at UWS, you'll need...",
                "message_id": "msg_123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2025-07-21T10:30:00Z",
                "metadata": {
                    "tools_used": ["enhanced_uws_search"],
                    "confidence_level": "high",
                    "response_time_ms": 1250
                }
            }
        }

class FeedbackRequest(BaseModel):
    """Schema for submitting feedback on assistant responses"""
    message_id: str = Field(..., description="ID of the message being rated")
    user_id: str = Field(..., description="User providing the feedback")
    feedback_type: str = Field(..., description="Type of feedback", pattern="^(thumbs_up|thumbs_down|rating|detailed)$")
    
    # Optional feedback fields
    rating: Optional[int] = Field(None, description="1-5 star rating", ge=1, le=5)
    is_helpful: Optional[bool] = Field(None, description="True if helpful, False if not helpful")
    feedback_text: Optional[str] = Field(None, description="Detailed feedback text", max_length=1000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "msg_123e4567-e89b-12d3-a456-426614174000",
                "user_id": "+919449248040",
                "feedback_type": "thumbs_up",
                "is_helpful": True,
                "rating": 5,
                "feedback_text": "Very helpful information about admission requirements!"
            }
        }

class FeedbackResponse(BaseModel):
    """Response schema for feedback submission"""
    success: bool = Field(..., description="Whether feedback was successfully recorded")
    feedback_id: str = Field(..., description="Unique identifier for the feedback record")
    message: str = Field(..., description="Confirmation message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "feedback_id": "fb_987fcdeb-51a2-43d6-b987-123456789abc",
                "message": "Thank you for your feedback!"
            }
        }

class ConversationHistoryResponse(BaseModel):
    """Schema for conversation history retrieval"""
    user_id: str = Field(..., description="User identifier")
    messages: List[Dict[str, Any]] = Field(..., description="List of conversation messages")
    total_messages: int = Field(..., description="Total number of messages in history")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "+919449248040",
                "messages": [
                    {
                        "message_id": "msg_001",
                        "sender": "user",
                        "message_text": "Hello",
                        "timestamp": "2025-07-21T10:00:00Z"
                    },
                    {
                        "message_id": "msg_002", 
                        "sender": "assistant",
                        "message_text": "Hi! How can I help you today?",
                        "timestamp": "2025-07-21T10:00:05Z"
                    }
                ],
                "total_messages": 2
            }
        }

class AnalyticsResponse(BaseModel):
    """Schema for feedback analytics"""
    period_days: int = Field(..., description="Analysis period in days")
    total_feedback: int = Field(..., description="Total feedback entries")
    positive_feedback: int = Field(..., description="Number of positive feedback")
    negative_feedback: int = Field(..., description="Number of negative feedback")
    satisfaction_rate: float = Field(..., description="Satisfaction rate (0-1)")
    average_response_time_ms: float = Field(..., description="Average response time in milliseconds")
    average_score: float = Field(..., description="Average rating score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "period_days": 30,
                "total_feedback": 150,
                "positive_feedback": 120,
                "negative_feedback": 30,
                "satisfaction_rate": 0.8,
                "average_response_time_ms": 1450.5,
                "average_score": 4.2
            }
        }