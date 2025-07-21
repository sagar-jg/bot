import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean, Integer, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import json
from contextlib import contextmanager

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/stage_genai"
)

# Create engine with connection pooling for production
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False  # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ConversationHistory(Base):
    """
    Store conversation history with Q&A message_id (can have duplicates for Q&A pairs).
    """
    __tablename__ = "conversation_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, nullable=False, index=True)  # Q&A id, can have duplicates
    user_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    sender = Column(String, nullable=False)  # 'user' or 'assistant'
    message_text = Column(Text, nullable=False)
    message_metadata = Column(JSONB, default=dict)  # Store additional context as JSON
    
    # Composite index for efficient queries
    __table_args__ = (
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_user_sender_timestamp', 'user_id', 'sender', 'timestamp'),
        Index('idx_message_id', 'message_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'sender': self.sender,
            'message_text': self.message_text,
            'message_metadata': self.message_metadata or {}
        }

class MessageFeedback(Base):
    """
    Store feedback for Q&A pairs using message_id (Q&A id).
    """
    __tablename__ = "message_feedback"
    
    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, nullable=False, index=True)  # Q&A id
    user_id = Column(String, nullable=False, index=True)
    feedback_type = Column(String, nullable=True)
    tools_used = Column(JSONB, default=list)  # List of tools used for this message
    human_feedback = Column(Boolean, nullable=True)  # True=positive, False=negative, None=no feedback
    human_feedback_score = Column(Integer, nullable=True)  # 1-5 scale rating
    human_feedback_text = Column(Text, nullable=True)  # Optional detailed feedback
    feedback_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    response_time_ms = Column(Integer, nullable=True)  # Time taken to generate response
    confidence_level = Column(String, nullable=True)  # Search confidence level
    search_results_count = Column(Integer, nullable=True)  # Number of search results found
    question_text = Column(Text, nullable=True)  # Denormalized user question
    answer_text = Column(Text, nullable=True)    # Denormalized assistant answer
    
    # Index for analytics queries
    __table_args__ = (
        Index('idx_feedback_timestamp', 'feedback_timestamp'),
        Index('idx_user_feedback', 'user_id', 'human_feedback'),
        Index('idx_message_id_feedback', 'message_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'feedback_id': self.feedback_id,
            'message_id': self.message_id,
            'user_id': self.user_id,
            'feedback_type': self.feedback_type,
            'tools_used': self.tools_used or [],
            'human_feedback': self.human_feedback,
            'human_feedback_score': self.human_feedback_score,
            'human_feedback_text': self.human_feedback_text,
            'feedback_timestamp': self.feedback_timestamp.isoformat(),
            'response_time_ms': self.response_time_ms,
            'confidence_level': self.confidence_level,
            'search_results_count': self.search_results_count,
            'question_text': self.question_text,
            'answer_text': self.answer_text,
        }

# Create tables
def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        raise

@contextmanager
def get_db_session():
    """Context manager for database sessions with automatic cleanup"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Database session error: {e}")
        raise
    finally:
        session.close()

class ConversationManager:
    """
    High-performance conversation history manager with Q&A id logic.
    """
    @staticmethod
    def add_message(
        user_id: str,
        sender: str,
        message_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None
    ) -> str:
        """
        Add a new message to conversation history with a Q&A message_id.
        Args:
            user_id: User identifier
            sender: 'user' or 'assistant'
            message_text: The actual message content
            metadata: Optional metadata (tools used, confidence, etc.)
            message_id: Q&A id (required for both user and assistant messages)
        Returns:
            The message_id of the created message
        """
        if message_id is None:
            raise ValueError("message_id (Q&A id) must be provided for both user and assistant messages.")
        try:
            with get_db_session() as session:
                msg = ConversationHistory(
                    message_id=message_id,
                    user_id=user_id,
                    sender=sender,
                    message_text=message_text,
                    message_metadata=metadata or {}
                )
                session.add(msg)
                session.flush()
                # Clean up old messages if needed (optional)
                ConversationManager._cleanup_old_messages(session, user_id)
                return message_id
        except Exception as e:
            logger.error(f"❌ Failed to add message: {e}")
            raise
    
    @staticmethod
    def _cleanup_old_messages(session: Session, user_id: str, keep_count: int = 6):
        """
        Keep only the most recent N messages per user for performance.
        Deletes older messages and their associated feedback.
        """
        try:
            # Get message IDs to keep (most recent N)
            messages_to_keep = session.query(ConversationHistory.message_id)\
                .filter(ConversationHistory.user_id == user_id)\
                .order_by(ConversationHistory.timestamp.desc())\
                .limit(keep_count)\
                .subquery()
            
            # Delete older messages (cascade will handle feedback)
            from sqlalchemy import select
            deleted_count = session.query(ConversationHistory)\
                .filter(ConversationHistory.user_id == user_id)\
                .filter(~ConversationHistory.message_id.in_(select(messages_to_keep)))\
                .delete(synchronize_session=False)
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old messages for user {user_id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to cleanup old messages: {e}")
            raise
    
    @staticmethod
    def get_conversation_history(user_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Get the most recent conversation history for a user.
        Returns messages in chronological order (oldest first).
        
        Args:
            user_id: User identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries in chronological order
        """
        try:
            with get_db_session() as session:
                messages = session.query(ConversationHistory)\
                    .filter(ConversationHistory.user_id == user_id)\
                    .order_by(ConversationHistory.timestamp.desc())\
                    .limit(limit)\
                    .all()
                
                # Convert to dict and reverse to get chronological order
                history = [msg.to_dict() for msg in reversed(messages)]
                
                logger.info(f"📚 Retrieved {len(history)} messages for user {user_id}")
                return history
                
        except Exception as e:
            logger.error(f"❌ Failed to get conversation history: {e}")
            return []
    
    @staticmethod
    def get_context_for_ai(user_id: str) -> str:
        """
        Get formatted conversation context for AI consumption.
        Optimized format for better AI understanding.
        
        Returns:
            Formatted string with conversation context
        """
        history = ConversationManager.get_conversation_history(user_id, limit=4)  # Last 4 messages for context
        
        if not history:
            return "No previous conversation history."
        
        context_parts = ["Previous conversation context:"]
        
        for msg in history:
            timestamp = datetime.fromisoformat(msg['timestamp']).strftime("%H:%M")
            sender = "Student" if msg['sender'] == 'user' else "Assistant"
            text = msg['message_text'][:200] + "..." if len(msg['message_text']) > 200 else msg['message_text']
            
            context_parts.append(f"{timestamp} {sender}: {text}")
        
        return "\n".join(context_parts)
    
    @staticmethod
    def get_message_by_id(message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific message by its ID"""
        try:
            with get_db_session() as session:
                message = session.query(ConversationHistory)\
                    .filter(ConversationHistory.message_id == message_id)\
                    .first()
                
                return message.to_dict() if message else None
                
        except Exception as e:
            logger.error(f"❌ Failed to get message {message_id}: {e}")
            return None

class FeedbackManager:
    """
    Feedback management for Q&A pairs using message_id (Q&A id).
    """
    @staticmethod
    def add_feedback(
        message_id: str,
        user_id: str,
        feedback_type: Optional[str] = None,
        human_feedback: Optional[bool] = None,
        human_feedback_score: Optional[int] = None,
        human_feedback_text: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
        response_time_ms: Optional[int] = None,
        confidence_level: Optional[str] = None,
        search_results_count: Optional[int] = None,
        question_text: Optional[str] = None,
        answer_text: Optional[str] = None
    ) -> int:
        """
        Add or update feedback for a Q&A pair using message_id (Q&A id).
        If feedback for the same message_id and user_id exists, update it.
        Returns feedback_id (int).
        """
        try:
            with get_db_session() as session:
                existing = session.query(MessageFeedback).filter_by(message_id=message_id, user_id=user_id).first()
                if existing:
                    # Update existing feedback
                    if feedback_type is not None:
                        existing.feedback_type = feedback_type
                    if human_feedback is not None:
                        existing.human_feedback = human_feedback
                    if human_feedback_score is not None:
                        existing.human_feedback_score = human_feedback_score
                    if human_feedback_text is not None:
                        existing.human_feedback_text = human_feedback_text
                    if tools_used is not None:
                        existing.tools_used = tools_used
                    if response_time_ms is not None:
                        existing.response_time_ms = response_time_ms
                    if confidence_level is not None:
                        existing.confidence_level = confidence_level
                    if search_results_count is not None:
                        existing.search_results_count = search_results_count
                    if question_text is not None:
                        existing.question_text = question_text
                    if answer_text is not None:
                        existing.answer_text = answer_text
                    existing.feedback_timestamp = datetime.utcnow()
                    session.flush()
                    return existing.feedback_id
                else:
                    feedback = MessageFeedback(
                        message_id=message_id,
                        user_id=user_id,
                        feedback_type=feedback_type,
                        human_feedback=human_feedback,
                        human_feedback_score=human_feedback_score,
                        human_feedback_text=human_feedback_text,
                        tools_used=tools_used or [],
                        response_time_ms=response_time_ms,
                        confidence_level=confidence_level,
                        search_results_count=search_results_count,
                        question_text=question_text,
                        answer_text=answer_text
                    )
                    session.add(feedback)
                    session.flush()
                    return feedback.feedback_id
        except Exception as e:
            logger.error(f"❌ Failed to add feedback: {e}")
            raise
    
    @staticmethod
    def get_feedback_analytics(days: int = 30) -> Dict[str, Any]:
        """
        Get feedback analytics for the specified time period.
        Useful for monitoring bot performance and user satisfaction.
        """
        try:
            with get_db_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                # Basic feedback stats
                total_feedback = session.query(MessageFeedback)\
                    .filter(MessageFeedback.feedback_timestamp >= cutoff_date)\
                    .count()
                
                positive_feedback = session.query(MessageFeedback)\
                    .filter(MessageFeedback.feedback_timestamp >= cutoff_date)\
                    .filter(MessageFeedback.human_feedback == True)\
                    .count()
                
                negative_feedback = session.query(MessageFeedback)\
                    .filter(MessageFeedback.feedback_timestamp >= cutoff_date)\
                    .filter(MessageFeedback.human_feedback == False)\
                    .count()
                
                # Average response time
                avg_response_time = session.query(MessageFeedback.response_time_ms)\
                    .filter(MessageFeedback.feedback_timestamp >= cutoff_date)\
                    .filter(MessageFeedback.response_time_ms.isnot(None))\
                    .all()
                
                avg_response_time_ms = sum(r[0] for r in avg_response_time) / len(avg_response_time) if avg_response_time else 0
                
                # Average score
                scores = session.query(MessageFeedback.human_feedback_score)\
                    .filter(MessageFeedback.feedback_timestamp >= cutoff_date)\
                    .filter(MessageFeedback.human_feedback_score.isnot(None))\
                    .all()
                
                avg_score = sum(s[0] for s in scores) / len(scores) if scores else 0
                
                analytics = {
                    'period_days': days,
                    'total_feedback': total_feedback,
                    'positive_feedback': positive_feedback,
                    'negative_feedback': negative_feedback,
                    'satisfaction_rate': positive_feedback / max(1, positive_feedback + negative_feedback),
                    'average_response_time_ms': round(avg_response_time_ms, 2),
                    'average_score': round(avg_score, 2),
                    'total_messages_with_scores': len(scores)
                }
                
                logger.info(f"📊 Generated analytics for {days} days: {analytics}")
                return analytics
                
        except Exception as e:
            logger.error(f"❌ Failed to get analytics: {e}")
            return {}
    
    @staticmethod
    def get_message_feedback(message_id: str) -> Optional[Dict[str, Any]]:
        """Get feedback for a specific message"""
        try:
            with get_db_session() as session:
                feedback = session.query(MessageFeedback)\
                    .filter(MessageFeedback.message_id == message_id)\
                    .first()
                
                return feedback.to_dict() if feedback else None
                
        except Exception as e:
            logger.error(f"❌ Failed to get feedback for message {message_id}: {e}")
            return None

# Utility functions for database management
def get_database_stats() -> Dict[str, Any]:
    """Get database statistics for monitoring"""
    try:
        with get_db_session() as session:
            total_messages = session.query(ConversationHistory).count()
            total_feedback = session.query(MessageFeedback).count()
            unique_users = session.query(ConversationHistory.user_id).distinct().count()
            
            # Recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_messages = session.query(ConversationHistory)\
                .filter(ConversationHistory.timestamp >= recent_cutoff)\
                .count()
            
            return {
                'total_messages': total_messages,
                'total_feedback': total_feedback,
                'unique_users': unique_users,
                'recent_messages_24h': recent_messages,
                'timestamp': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to get database stats: {e}")
        return {}

def cleanup_old_data(days_to_keep: int = 90):
    """
    Clean up very old data beyond the rolling window.
    Run this periodically to maintain database performance.
    """
    try:
        with get_db_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Delete old messages (will cascade to feedback)
            deleted_count = session.query(ConversationHistory)\
                .filter(ConversationHistory.timestamp < cutoff_date)\
                .delete(synchronize_session=False)
            
            logger.info(f"🧹 Cleaned up {deleted_count} messages older than {days_to_keep} days")
            return deleted_count
            
    except Exception as e:
        logger.error(f"❌ Failed to cleanup old data: {e}")
        return 0

# Initialize database on import
if __name__ == "__main__":
    create_tables()
    print("✅ Database tables created successfully")
else:
    # Auto-create tables when module is imported
    try:
        create_tables()
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-create tables: {e}")