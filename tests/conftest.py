import pytest
import os
import sys
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from api.main import app
from db.models import Base
from db.connection import get_db_session
from services import service_registry

# Test database URL (SQLite in memory)
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

# Create test session factory
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session")
def setup_test_db():
    """Create test database tables"""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session(setup_test_db):
    """Create a test database session"""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def override_get_db_session(db_session):
    """Override the database dependency"""
    def _get_test_db_session():
        return db_session
    
    return _get_test_db_session

@pytest.fixture
def client(override_get_db_session) -> Generator[TestClient, None, None]:
    """Create a test client"""
    # Override the database dependency
    app.dependency_overrides[get_db_session] = override_get_db_session
    
    # Initialize services for testing
    service_registry.initialize_all()
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "user_id": "test_user_123",
        "display_name": "Test User",
        "phone_number": "+1234567890",
        "language": "en"
    }

@pytest.fixture
def sample_message_data():
    """Sample message data for testing"""
    return {
        "user_id": "test_user_123",
        "message": "Hello, how can you help me?",
        "message_type": "text"
    }

@pytest.fixture
def sample_feedback_data():
    """Sample feedback data for testing"""
    return {
        "message_id": "test_msg_123",
        "user_id": "test_user_123",
        "feedback_type": "thumbs_up",
        "is_helpful": True
    }

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing"""
    test_env_vars = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "OPENAI_API_KEY": "test_openai_key",
        "CREWAI_API_KEY": "test_crewai_key",
        "PINECONE_API_KEY": "test_pinecone_key"
    }
    
    for key, value in test_env_vars.items():
        monkeypatch.setenv(key, value)
    
    return test_env_vars

# Test utilities
class TestHelpers:
    """Helper methods for testing"""
    
    @staticmethod
    def create_test_user(db_session, **kwargs):
        """Create a test user in the database"""
        from db.manager import UserManager
        return UserManager.create_or_update_user(
            user_id=kwargs.get('user_id', 'test_user'),
            display_name=kwargs.get('display_name', 'Test User'),
            phone_number=kwargs.get('phone_number', '+1234567890'),
            language=kwargs.get('language', 'en')
        )
    
    @staticmethod
    def create_test_conversation(db_session, user_id="test_user", messages=None):
        """Create a test conversation with messages"""
        from db.manager import ConversationManager
        from db.models import MessageSender
        
        if messages is None:
            messages = [
                ("Hello", MessageSender.USER),
                ("Hi there! How can I help you?", MessageSender.ASSISTANT)
            ]
        
        message_ids = []
        for i, (text, sender) in enumerate(messages):
            message_id = f"test_msg_{i+1}"
            ConversationManager.add_message(
                message_id=message_id,
                user_id=user_id,
                sender=sender,
                message_text=text
            )
            message_ids.append(message_id)
        
        return message_ids
    
    @staticmethod
    def create_test_feedback(db_session, message_id, user_id="test_user", **kwargs):
        """Create test feedback"""
        from db.manager import FeedbackManager
        from db.models import FeedbackType
        
        return FeedbackManager.add_feedback(
            message_id=message_id,
            user_id=user_id,
            feedback_type=kwargs.get('feedback_type', FeedbackType.THUMBS_UP),
            human_feedback=kwargs.get('human_feedback', True),
            human_feedback_score=kwargs.get('rating'),
            human_feedback_text=kwargs.get('feedback_text'),
            question_text=kwargs.get('question_text'),
            answer_text=kwargs.get('answer_text')
        )

@pytest.fixture
def test_helpers():
    """Provide test helper methods"""
    return TestHelpers

# Custom markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.slow = pytest.mark.slow
