# main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional
import logging

# Import your schemas and services
from uwsbot.api.schemas import (
    WhatsAppQueryRequest, 
    WhatsAppQueryResponse, 
    FeedbackRequest,
    FeedbackResponse,
    ConversationHistoryResponse,
    AnalyticsResponse
)
from uwsbot.api.whatsapp_service import answer_student_query, get_bot_health_status

# Import database components
from uwsbot.api.db import (
    ConversationManager, 
    FeedbackManager, 
    get_database_stats,
    create_tables
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="UWS WhatsApp Chatbot API", 
    description="Enhanced API for UWS WhatsApp Assistant with conversation tracking and feedback",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    try:
        create_tables()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")

@app.post("/whatsapp/query", response_model=WhatsAppQueryResponse)
def whatsapp_query(request: WhatsAppQueryRequest):
    """
    Process a WhatsApp message and return an AI-generated response.
    Enhanced with conversation tracking and performance monitoring.
    """
    try:
        # Process the query with enhanced tracking
        response_text, message_id, metadata = answer_student_query(
            request.user_id, 
            request.message
        )
        
        # Return enhanced response with message tracking
        return WhatsAppQueryResponse(
            response=response_text,
            message_id=message_id,
            timestamp=datetime.utcnow(),
            metadata={
                "tools_used": metadata.tools_used,
                "response_time_ms": metadata.response_time_ms,
                "search_confidence": metadata.search_confidence,
                "search_results_count": metadata.search_results_count
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest):
    """
    Submit feedback for a specific Q&A pair (message_id = Q&A id).
    Supports multiple feedback types: thumbs up/down, ratings, and detailed text.
    """
    try:
        # Fetch both user and assistant messages for this Q&A id
        history = ConversationManager.get_conversation_history(request.user_id, limit=20)
        user_msg = None
        assistant_msg = None
        for msg in history:
            if msg["message_id"] == request.message_id:
                if msg["sender"] == "user":
                    user_msg = msg
                elif msg["sender"] == "assistant":
                    assistant_msg = msg
        if not user_msg or not assistant_msg:
            raise HTTPException(status_code=404, detail="Q&A pair not found for this message_id")
        question_text = user_msg["message_text"]
        answer_text = assistant_msg["message_text"]
        # Convert feedback to database format
        human_feedback = None
        if request.feedback_type in ["thumbs_up", "thumbs_down"]:
            human_feedback = request.feedback_type == "thumbs_up"
        elif request.is_helpful is not None:
            human_feedback = request.is_helpful
        # Add feedback to database
        feedback_id = FeedbackManager.add_feedback(
            message_id=request.message_id,
            user_id=request.user_id,
            feedback_type=request.feedback_type,
            human_feedback=human_feedback,
            human_feedback_score=request.rating,
            human_feedback_text=request.feedback_text,
            question_text=question_text,
            answer_text=answer_text
        )
        # Log feedback for monitoring
        logger.info(f"📝 Feedback received: {request.feedback_type} for Q&A message_id {request.message_id}")
        return FeedbackResponse(
            success=True,
            feedback_id=str(feedback_id),
            message="Thank you for your feedback! It helps us improve our service."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversation/{user_id}", response_model=ConversationHistoryResponse)
def get_conversation_history(
    user_id: str,
    limit: Optional[int] = Query(6, ge=1, le=20, description="Number of messages to retrieve")
):
    """
    Retrieve conversation history for a specific user.
    Returns the most recent messages in chronological order.
    """
    try:
        history = ConversationManager.get_conversation_history(user_id, limit)
        
        return ConversationHistoryResponse(
            user_id=user_id,
            messages=history,
            total_messages=len(history)
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to retrieve conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/feedback", response_model=AnalyticsResponse)
def get_feedback_analytics(
    days: Optional[int] = Query(30, ge=1, le=365, description="Analysis period in days")
):
    """
    Get feedback analytics and performance metrics.
    Useful for monitoring bot performance and user satisfaction.
    """
    try:
        analytics = FeedbackManager.get_feedback_analytics(days)
        
        if not analytics:
            raise HTTPException(status_code=404, detail="No analytics data available")
        
        return AnalyticsResponse(**analytics)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """
    Comprehensive health check endpoint for monitoring.
    Returns status of all system components.
    """
    try:
        health_status = get_bot_health_status()
        
        # Return appropriate HTTP status code
        if health_status["status"] == "healthy":
            return health_status
        elif health_status["status"] == "degraded":
            return health_status  # 200 but with warnings
        else:
            raise HTTPException(status_code=503, detail=health_status)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/database")
def get_database_statistics():
    """
    Get database statistics for monitoring and analytics.
    Requires admin access in production.
    """
    try:
        stats = get_database_stats()
        return {
            "database_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to retrieve database stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/conversation/{user_id}")
def delete_user_conversation(user_id: str):
    """
    Delete all conversation history for a specific user.
    Use with caution - this action is irreversible.
    """
    try:
        # In a production system, you'd want proper authorization here
        # For now, we'll implement a simple cleanup
        from db import get_db_session, ConversationHistory
        
        with get_db_session() as session:
            deleted_count = session.query(ConversationHistory)\
                .filter(ConversationHistory.user_id == user_id)\
                .delete(synchronize_session=False)
            
            logger.info(f"🗑️ Deleted {deleted_count} messages for user {user_id}")
            
            return {
                "success": True,
                "deleted_messages": deleted_count,
                "message": f"All conversation history deleted for user {user_id}"
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Additional utility endpoints for development and monitoring

@app.get("/message/{message_id}")
def get_message_details(message_id: str):
    """Get detailed information about a specific message including feedback"""
    try:
        message = ConversationManager.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        feedback = FeedbackManager.get_message_feedback(message_id)
        
        return {
            "message": message,
            "feedback": feedback,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve message details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    """API information and status"""
    return {
        "name": "UWS WhatsApp Chatbot API",
        "version": "2.0.0",
        "description": "Enhanced API with conversation tracking and feedback",
        "status": "operational",
        "features": [
            "Advanced CRAG search technology",
            "Conversation history tracking",
            "User feedback collection",
            "Performance analytics",
            "Real-time health monitoring"
        ],
        "endpoints": {
            "POST /whatsapp/query": "Process WhatsApp messages",
            "POST /feedback": "Submit message feedback",
            "GET /conversation/{user_id}": "Get conversation history",
            "GET /analytics/feedback": "Get feedback analytics",
            "GET /health": "System health check",
            "GET /stats/database": "Database statistics"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )