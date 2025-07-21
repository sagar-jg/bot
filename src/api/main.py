import os
import sys
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import services and schemas
from services import (
    WhatsAppService, 
    ConversationService, 
    FeedbackService, 
    HealthService,
    service_registry
)
from schemas import (
    WhatsAppQueryRequest,
    WhatsAppQueryResponse, 
    FeedbackRequest,
    FeedbackResponse,
    ConversationHistoryResponse,
    AnalyticsResponse,
    HealthResponse,
    ErrorResponse
)
from db.utils import create_all_tables

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/app_{os.getenv("ENVIRONMENT", "dev")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Global service instances
whatsapp_service = WhatsAppService()
conversation_service = ConversationService()
feedback_service = FeedbackService()
health_service = HealthService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("🚀 Starting WhatsApp Bot API...")
    
    # Register services
    service_registry.register('whatsapp', whatsapp_service)
    service_registry.register('conversation', conversation_service)
    service_registry.register('feedback', feedback_service)
    service_registry.register('health', health_service)
    
    # Initialize all services
    initialization_results = service_registry.initialize_all()
    
    for service_name, success in initialization_results.items():
        if success:
            logger.info(f"✅ {service_name} service initialized")
        else:
            logger.error(f"❌ {service_name} service initialization failed")
    
    # Initialize database
    try:
        create_all_tables()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛹️ Shutting down WhatsApp Bot API...")

# Create FastAPI app with environment-specific configuration
app_config = {
    'title': 'WhatsApp Bot API',
    'description': 'Advanced WhatsApp chatbot with multi-environment support',
    'version': '2.0.0',
    'lifespan': lifespan
}

# Add environment-specific configurations
environment = os.getenv('ENVIRONMENT', 'dev')
if environment == 'prod':
    # Production optimizations
    app_config['docs_url'] = None  # Disable docs in production
    app_config['redoc_url'] = None
    app_config['openapi_url'] = None
elif environment == 'dev':
    app_config['debug'] = True

app = FastAPI(**app_config)

# Add middleware

# CORS middleware
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:8000", 
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000"
]

if environment == 'prod':
    # Add production domains
    production_origins = os.getenv('ALLOWED_ORIGINS', '').split(',')
    allowed_origins.extend([origin.strip() for origin in production_origins if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if environment != 'dev' else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Trusted host middleware for production
if environment == 'prod':
    trusted_hosts = os.getenv('TRUSTED_HOSTS', 'localhost').split(',')
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[host.strip() for host in trusted_hosts]
    )

# Custom exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=f"HTTP_{exc.status_code}",
            error_message=exc.detail,
            request_id=getattr(request.state, 'request_id', None)
        ).model_dump()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="INTERNAL_SERVER_ERROR",
            error_message="An internal server error occurred",
            details={"type": type(exc).__name__} if environment == 'dev' else None,
            request_id=getattr(request.state, 'request_id', None)
        ).model_dump()
    )

# Dependency for request ID tracking
def get_request_id(request: Request) -> str:
    """Generate or get request ID for tracking"""
    import uuid
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    request.state.request_id = request_id
    return request_id

# API Routes

@app.get("/", tags=["Info"])
async def read_root():
    """API information and status"""
    return {
        "name": "WhatsApp Bot API",
        "version": "2.0.0",
        "environment": environment,
        "description": "Multi-environment WhatsApp chatbot with advanced features",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "features": [
            "Multi-environment support (dev/uat/prod)",
            "Advanced conversation tracking",
            "User feedback collection", 
            "Performance analytics",
            "Real-time health monitoring",
            "Service-oriented architecture"
        ],
        "endpoints": {
            "POST /whatsapp/query": "Process WhatsApp messages",
            "POST /feedback": "Submit message feedback",
            "GET /conversation/{user_id}": "Get conversation history",
            "GET /analytics/feedback": "Get feedback analytics",
            "GET /health": "System health check",
            "GET /health/simple": "Simple health status"
        }
    }

@app.post("/whatsapp/query", response_model=WhatsAppQueryResponse, tags=["WhatsApp"])
async def whatsapp_query(
    request: WhatsAppQueryRequest,
    request_id: str = Depends(get_request_id)
):
    """Process a WhatsApp message and return AI-generated response"""
    try:
        logger.info(f"Processing WhatsApp query from user {request.user_id}")
        
        # Process the query using WhatsApp service
        response_data = await whatsapp_service.process_message(
            user_id=request.user_id,
            message=request.message,
            message_type=getattr(request, 'message_type', 'text'),
            metadata=getattr(request, 'metadata', {})
        )
        
        return WhatsAppQueryResponse(
            **response_data,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"WhatsApp query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback", response_model=FeedbackResponse, tags=["Feedback"])
async def submit_feedback(
    request: FeedbackRequest,
    request_id: str = Depends(get_request_id)
):
    """Submit feedback for a specific message"""
    try:
        logger.info(f"Submitting feedback for message {request.message_id}")
        
        # Submit feedback using feedback service
        feedback_result = feedback_service.submit_feedback(
            message_id=request.message_id,
            user_id=request.user_id,
            feedback_type=request.feedback_type,
            is_helpful=getattr(request, 'is_helpful', None),
            rating=getattr(request, 'rating', None),
            feedback_text=getattr(request, 'feedback_text', None),
            category=getattr(request, 'category', None)
        )
        
        return FeedbackResponse(
            **feedback_result,
            request_id=request_id
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversation/{user_id}", response_model=ConversationHistoryResponse, tags=["Conversation"])
async def get_conversation_history(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50, description="Number of messages to retrieve"),
    include_metadata: bool = Query(default=True, description="Include response metadata"),
    request_id: str = Depends(get_request_id)
):
    """Get conversation history for a user"""
    try:
        logger.info(f"Retrieving conversation history for user {user_id}")
        
        history = conversation_service.get_conversation_history(
            user_id=user_id,
            limit=limit,
            include_metadata=include_metadata
        )
        
        return ConversationHistoryResponse(
            user_id=user_id,
            messages=history,
            total_messages=len(history),
            limit=limit,
            include_metadata=include_metadata,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversation/{user_id}/stats", tags=["Conversation"])
async def get_user_conversation_stats(
    user_id: str,
    request_id: str = Depends(get_request_id)
):
    """Get conversation statistics for a user"""
    try:
        stats = conversation_service.get_user_conversation_stats(user_id)
        return {**stats, "request_id": request_id}
        
    except Exception as e:
        logger.error(f"Failed to retrieve user stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/feedback", response_model=AnalyticsResponse, tags=["Analytics"])
async def get_feedback_analytics(
    days: int = Query(default=30, ge=1, le=365, description="Analysis period in days"),
    request_id: str = Depends(get_request_id)
):
    """Get feedback analytics and insights"""
    try:
        logger.info(f"Retrieving feedback analytics for {days} days")
        
        analytics = feedback_service.get_feedback_analytics(days)
        
        if not analytics or analytics.get('total_feedback', 0) == 0:
            raise HTTPException(status_code=404, detail="No analytics data available")
        
        return AnalyticsResponse(
            **analytics,
            request_id=request_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/feedback/summary", tags=["Analytics"])
async def get_feedback_summary(
    days: int = Query(default=7, ge=1, le=365, description="Summary period in days"),
    request_id: str = Depends(get_request_id)
):
    """Get feedback summary for a period"""
    try:
        summary = feedback_service.get_feedback_summary_for_period(days)
        return {**summary, "request_id": request_id}
        
    except Exception as e:
        logger.error(f"Failed to retrieve feedback summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(request_id: str = Depends(get_request_id)):
    """Comprehensive system health check"""
    try:
        health_data = health_service.get_system_health()
        
        # Determine HTTP status code based on health
        status_code = 200
        if health_data.get('status') == 'critical':
            status_code = 503  # Service Unavailable
        elif health_data.get('status') == 'degraded':
            status_code = 200  # OK but with warnings
        
        return JSONResponse(
            status_code=status_code,
            content=HealthResponse(
                **health_data,
                request_id=request_id
            ).model_dump()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content=HealthResponse(
                status='error',
                error=str(e),
                request_id=request_id
            ).model_dump()
        )

@app.get("/health/simple", tags=["Health"])
async def simple_health_check(request_id: str = Depends(get_request_id)):
    """Simple health status for load balancers"""
    try:
        health_status = health_service.get_simple_health_status()
        
        status_code = 200
        if health_status.get('status') == 'critical':
            status_code = 503
        elif health_status.get('critical_alerts', 0) > 0:
            status_code = 503
        
        return JSONResponse(
            status_code=status_code,
            content={**health_status, "request_id": request_id}
        )
        
    except Exception as e:
        logger.error(f"Simple health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "request_id": request_id
            }
        )

@app.get("/stats/database", tags=["Stats"])
async def get_database_statistics(request_id: str = Depends(get_request_id)):
    """Get database statistics"""
    try:
        from db.utils import get_database_stats
        stats = get_database_stats()
        
        return {
            "database_stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve database stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/message/{message_id}", tags=["Messages"])
async def get_message_details(
    message_id: str,
    request_id: str = Depends(get_request_id)
):
    """Get detailed information about a specific message"""
    try:
        # Get message details
        message = conversation_service.conversation_manager.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Get feedback for the message
        feedback = feedback_service.get_feedback_for_message(message_id)
        
        return {
            "message": message,
            "feedback": feedback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve message details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Admin endpoints (only available in dev and uat)
if environment in ['dev', 'uat']:
    
    @app.delete("/conversation/{user_id}", tags=["Admin"])
    async def delete_user_conversation(
        user_id: str,
        request_id: str = Depends(get_request_id)
    ):
        """Delete all conversation history for a user (dev/uat only)"""
        try:
            result = conversation_service.delete_user_conversation(user_id)
            return {**result, "request_id": request_id}
            
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/debug/services", tags=["Debug"])
    async def get_services_status(request_id: str = Depends(get_request_id)):
        """Get status of all registered services (dev/uat only)"""
        try:
            services_health = service_registry.health_check_all()
            services_list = list(service_registry.get_all_services().keys())
            
            return {
                "registered_services": services_list,
                "services_health": services_health,
                "environment": environment,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id
            }
            
        except Exception as e:
            logger.error(f"Failed to get services status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    # Configuration based on environment
    config = {
        'app': 'main:app',
        'host': os.getenv('HOST', '127.0.0.1'),
        'port': int(os.getenv('PORT', 8000)),
        'log_level': os.getenv('LOG_LEVEL', 'info').lower()
    }
    
    if environment == 'dev':
        config.update({
            'reload': True,
            'reload_dirs': ['src'],
            'workers': 1
        })
    else:
        config.update({
            'workers': int(os.getenv('WORKERS', 4)),
            'access_log': True
        })
    
    uvicorn.run(**config)
