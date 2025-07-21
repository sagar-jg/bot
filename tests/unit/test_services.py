import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

# Import services to test
from services.base_service import BaseService, ServiceRegistry
from services.ai_service import AIService
from services.conversation_service import ConversationService
from services.feedback_service import FeedbackService
from services.health_service import HealthService
from services.whatsapp_service import WhatsAppService

class TestBaseService:
    """Test the base service class"""
    
    def test_base_service_initialization(self):
        """Test base service initialization"""
        service = BaseService("TestService")
        assert service.service_name == "TestService"
        assert not service.is_initialized
        assert service.logger is not None
    
    def test_service_registry(self):
        """Test service registry functionality"""
        registry = ServiceRegistry()
        service = BaseService("TestService")
        
        # Test registration
        registry.register("test", service)
        retrieved_service = registry.get("test")
        assert retrieved_service is service
        
        # Test get all services
        all_services = registry.get_all_services()
        assert "test" in all_services
        assert all_services["test"] is service

class TestAIService:
    """Test the AI service"""
    
    @pytest.fixture
    def ai_service(self, mock_env_vars):
        """Create AI service for testing"""
        service = AIService()
        service.initialize()
        return service
    
    def test_ai_service_initialization(self, ai_service):
        """Test AI service initialization"""
        assert ai_service.is_initialized
        assert "fallback" in ai_service.ai_providers
        assert ai_service.ai_providers["fallback"]["available"]
    
    def test_intent_analysis(self, ai_service):
        """Test message intent analysis"""
        # Test greeting detection
        assert ai_service._analyze_intent("Hello there!") == "greeting"
        assert ai_service._analyze_intent("Hi how are you?") == "greeting"
        
        # Test question detection
        assert ai_service._analyze_intent("What is the weather like?") == "question"
        assert ai_service._analyze_intent("How can you help me?") == "question"
        
        # Test farewell detection
        assert ai_service._analyze_intent("Thanks for your help") == "farewell"
        assert ai_service._analyze_intent("Goodbye!") == "farewell"
        
        # Test general
        assert ai_service._analyze_intent("I need some information") == "request"
    
    @pytest.mark.asyncio
    async def test_generate_response(self, ai_service):
        """Test AI response generation"""
        response = await ai_service.generate_response(
            user_message="Hello, how can you help me?",
            user_id="test_user",
            conversation_context={"user_messages": [], "assistant_messages": []}
        )
        
        assert "response" in response
        assert "confidence_score" in response
        assert "tools_used" in response
        assert isinstance(response["response"], str)
        assert 0 <= response["confidence_score"] <= 1
    
    def test_provider_selection(self, ai_service):
        """Test AI provider selection logic"""
        # Test greeting intent should use fallback
        provider = ai_service._select_provider("greeting", {})
        assert provider == "fallback"
        
        # Test question intent should prefer available providers
        provider = ai_service._select_provider("question", {})
        # Should fall back to fallback since no real providers in test
        assert provider in ai_service.ai_providers
    
    def test_health_check(self, ai_service):
        """Test AI service health check"""
        health = ai_service.health_check()
        assert health["service"] == "AIService"
        assert "providers" in health
        assert "capabilities" in health
        assert health["providers"]["total"] > 0

class TestConversationService:
    """Test the conversation service"""
    
    @pytest.fixture
    def conversation_service(self, db_session):
        """Create conversation service for testing"""
        service = ConversationService()
        service.initialize()
        return service
    
    def test_conversation_service_initialization(self, conversation_service):
        """Test conversation service initialization"""
        assert conversation_service.is_initialized
        assert conversation_service.conversation_manager is not None
        assert conversation_service.user_manager is not None
    
    def test_start_conversation(self, conversation_service, test_helpers):
        """Test starting a conversation"""
        message_id = conversation_service.start_conversation(
            user_id="test_user",
            user_message="Hello, I need help",
            user_metadata={"source": "test"}
        )
        
        assert message_id is not None
        assert message_id.startswith("msg_")
    
    def test_add_assistant_response(self, conversation_service):
        """Test adding assistant response"""
        # First start a conversation
        user_message_id = conversation_service.start_conversation(
            user_id="test_user",
            user_message="Hello"
        )
        
        # Add assistant response
        assistant_message_id = conversation_service.add_assistant_response(
            user_id="test_user",
            response_text="Hello! How can I help you?",
            response_time_ms=150,
            tools_used=["ai_service"]
        )
        
        assert assistant_message_id is not None
        assert assistant_message_id.startswith("asst_")
    
    def test_get_conversation_history(self, conversation_service, test_helpers):
        """Test retrieving conversation history"""
        # Create a test conversation
        conversation_service.start_conversation("test_user", "Hello")
        conversation_service.add_assistant_response("test_user", "Hi there!")
        
        # Get history
        history = conversation_service.get_conversation_history("test_user", limit=5)
        
        assert isinstance(history, list)
        assert len(history) == 2  # User message + assistant response
        assert history[0]["sender"] == "user"
        assert history[1]["sender"] == "assistant"
    
    def test_get_conversation_context(self, conversation_service):
        """Test getting conversation context"""
        # Create some conversation history
        conversation_service.start_conversation("test_user", "Hello")
        conversation_service.add_assistant_response("test_user", "Hi!")
        conversation_service.start_conversation("test_user", "How are you?")
        conversation_service.add_assistant_response("test_user", "I'm doing well!")
        
        user_msgs, assistant_msgs = conversation_service.get_conversation_context(
            "test_user", context_length=3
        )
        
        assert isinstance(user_msgs, list)
        assert isinstance(assistant_msgs, list)
        assert len(user_msgs) <= 3
        assert len(assistant_msgs) <= 3

class TestFeedbackService:
    """Test the feedback service"""
    
    @pytest.fixture
    def feedback_service(self, db_session):
        """Create feedback service for testing"""
        service = FeedbackService()
        service.initialize()
        return service
    
    def test_feedback_service_initialization(self, feedback_service):
        """Test feedback service initialization"""
        assert feedback_service.is_initialized
        assert feedback_service.feedback_manager is not None
        assert feedback_service.conversation_manager is not None
    
    def test_submit_feedback(self, feedback_service, test_helpers, db_session):
        """Test submitting feedback"""
        # Create test data
        test_helpers.create_test_user(db_session, user_id="test_user")
        message_ids = test_helpers.create_test_conversation(db_session, "test_user")
        
        # Submit feedback
        result = feedback_service.submit_feedback(
            message_id=message_ids[1],  # Assistant message
            user_id="test_user",
            feedback_type="thumbs_up",
            is_helpful=True
        )
        
        assert result["success"] is True
        assert "feedback_id" in result
        assert result["feedback_type"] == "thumbs_up"
    
    def test_get_feedback_analytics(self, feedback_service, test_helpers, db_session):
        """Test getting feedback analytics"""
        # Create test data
        test_helpers.create_test_user(db_session, user_id="test_user")
        message_ids = test_helpers.create_test_conversation(db_session, "test_user")
        
        # Submit some feedback
        feedback_service.submit_feedback(
            message_ids[1], "test_user", "thumbs_up", is_helpful=True
        )
        
        # Get analytics
        analytics = feedback_service.get_feedback_analytics(days=30)
        
        if analytics.get('total_feedback', 0) > 0:
            assert "satisfaction_rate" in analytics
            assert "insights" in analytics
            assert isinstance(analytics["insights"], list)

class TestHealthService:
    """Test the health service"""
    
    @pytest.fixture
    def health_service(self):
        """Create health service for testing"""
        service = HealthService()
        service.initialize()
        return service
    
    def test_health_service_initialization(self, health_service):
        """Test health service initialization"""
        assert health_service.is_initialized
        assert health_service.system_info is not None
        assert isinstance(health_service.system_info, dict)
    
    def test_get_system_health(self, health_service):
        """Test getting system health"""
        health_data = health_service.get_system_health()
        
        assert "status" in health_data
        assert "timestamp" in health_data
        assert "system" in health_data
        assert health_data["status"] in ["healthy", "degraded", "critical", "unknown"]
    
    def test_get_simple_health_status(self, health_service):
        """Test getting simple health status"""
        status = health_service.get_simple_health_status()
        
        assert "status" in status
        assert "timestamp" in status
        assert status["status"] in ["healthy", "degraded", "critical", "unknown"]

class TestWhatsAppService:
    """Test the WhatsApp service"""
    
    @pytest.fixture
    def whatsapp_service(self, mock_env_vars):
        """Create WhatsApp service for testing"""
        service = WhatsAppService()
        service.initialize()
        return service
    
    def test_whatsapp_service_initialization(self, whatsapp_service):
        """Test WhatsApp service initialization"""
        assert whatsapp_service.is_initialized
        assert whatsapp_service.conversation_service is not None
        assert whatsapp_service.ai_service is not None
        assert len(whatsapp_service.message_processors) > 0
    
    def test_get_supported_message_types(self, whatsapp_service):
        """Test getting supported message types"""
        types = whatsapp_service.get_supported_message_types()
        
        assert isinstance(types, list)
        assert "text" in types
        assert len(types) > 0
    
    @pytest.mark.asyncio
    async def test_process_message(self, whatsapp_service):
        """Test processing a WhatsApp message"""
        response = await whatsapp_service.process_message(
            user_id="test_user",
            message="Hello, how can you help me?",
            message_type="text",
            metadata={"source": "test"}
        )
        
        assert "response" in response
        assert "message_id" in response
        assert "user_id" in response
        assert "response_time_ms" in response
        assert response["user_id"] == "test_user"
        assert isinstance(response["response_time_ms"], int)
        assert response["response_time_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_process_image_message(self, whatsapp_service):
        """Test processing an image message"""
        response = await whatsapp_service.process_message(
            user_id="test_user",
            message="[Image]",
            message_type="image"
        )
        
        assert "response" in response
        assert "I can see you've sent an image" in response["response"]
        assert "image_handler" in response.get("tools_used", [])
    
    def test_health_check(self, whatsapp_service):
        """Test WhatsApp service health check"""
        health = whatsapp_service.health_check()
        
        assert health["service"] == "WhatsAppService"
        assert "dependent_services" in health
        assert "message_processors" in health
        assert "capabilities" in health
        assert health["message_processors"]["count"] > 0
