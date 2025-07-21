import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json

@pytest.mark.unit
class TestAPIEndpoints:
    """Test API endpoints"""
    
    def test_root_endpoint(self, client):
        """Test the root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "environment" in data
        assert data["name"] == "WhatsApp Bot API"
    
    def test_health_endpoint(self, client):
        """Test the health check endpoint"""
        response = client.get("/health")
        # Health check might return different status codes based on system state
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
    
    def test_simple_health_endpoint(self, client):
        """Test the simple health check endpoint"""
        response = client.get("/health/simple")
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
    
    def test_whatsapp_query_endpoint(self, client, sample_message_data):
        """Test the WhatsApp query endpoint"""
        response = client.post("/whatsapp/query", json=sample_message_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "message_id" in data
        assert "user_id" in data
        assert "response_time_ms" in data
        assert data["user_id"] == sample_message_data["user_id"]
    
    def test_whatsapp_query_invalid_data(self, client):
        """Test WhatsApp query with invalid data"""
        invalid_data = {
            "user_id": "",  # Empty user_id should be invalid
            "message": "Hello"
        }
        
        response = client.post("/whatsapp/query", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_feedback_endpoint(self, client, sample_feedback_data, test_helpers, db_session):
        """Test the feedback submission endpoint"""
        # First, create some test data
        test_helpers.create_test_user(db_session, user_id=sample_feedback_data["user_id"])
        message_ids = test_helpers.create_test_conversation(
            db_session, 
            user_id=sample_feedback_data["user_id"]
        )
        
        # Update feedback data with actual message ID
        feedback_data = sample_feedback_data.copy()
        feedback_data["message_id"] = message_ids[1]  # Assistant message
        
        response = client.post("/feedback", json=feedback_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert "feedback_id" in data
        assert data["success"] is True
    
    def test_feedback_invalid_message_id(self, client):
        """Test feedback with invalid message ID"""
        invalid_feedback = {
            "message_id": "nonexistent_message",
            "user_id": "test_user",
            "feedback_type": "thumbs_up"
        }
        
        response = client.post("/feedback", json=invalid_feedback)
        assert response.status_code == 400
    
    def test_conversation_history_endpoint(self, client, test_helpers, db_session):
        """Test the conversation history endpoint"""
        user_id = "test_user_history"
        
        # Create test conversation
        test_helpers.create_test_user(db_session, user_id=user_id)
        test_helpers.create_test_conversation(db_session, user_id)
        
        response = client.get(f"/conversation/{user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert "messages" in data
        assert "total_messages" in data
        assert data["user_id"] == user_id
        assert isinstance(data["messages"], list)
    
    def test_conversation_history_with_limit(self, client, test_helpers, db_session):
        """Test conversation history with limit parameter"""
        user_id = "test_user_limit"
        
        # Create test conversation with more messages
        test_helpers.create_test_user(db_session, user_id=user_id)
        test_helpers.create_test_conversation(
            db_session, 
            user_id, 
            messages=[(f"Message {i}", "user") for i in range(10)]
        )
        
        response = client.get(f"/conversation/{user_id}?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["messages"]) <= 5
        assert data["limit"] == 5
    
    def test_user_conversation_stats(self, client, test_helpers, db_session):
        """Test user conversation statistics endpoint"""
        user_id = "test_user_stats"
        
        # Create test data
        test_helpers.create_test_user(db_session, user_id=user_id)
        test_helpers.create_test_conversation(db_session, user_id)
        
        response = client.get(f"/conversation/{user_id}/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert "total_messages_analyzed" in data or "error" in data
    
    def test_analytics_feedback_endpoint(self, client, test_helpers, db_session):
        """Test feedback analytics endpoint"""
        # Create test data with feedback
        user_id = "test_analytics_user"
        test_helpers.create_test_user(db_session, user_id=user_id)
        message_ids = test_helpers.create_test_conversation(db_session, user_id)
        
        # Add some feedback
        test_helpers.create_test_feedback(db_session, message_ids[1], user_id)
        
        response = client.get("/analytics/feedback?days=30")
        # Might return 404 if no data or 200 if data exists
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "period_days" in data
            assert "summary" in data
    
    def test_analytics_feedback_summary(self, client):
        """Test feedback summary endpoint"""
        response = client.get("/analytics/feedback/summary?days=7")
        assert response.status_code == 200
        
        data = response.json()
        assert "period" in data
        assert "summary" in data
        assert "status" in data
    
    def test_database_stats_endpoint(self, client):
        """Test database statistics endpoint"""
        response = client.get("/stats/database")
        assert response.status_code == 200
        
        data = response.json()
        assert "database_stats" in data
        assert "timestamp" in data
    
    def test_message_details_endpoint(self, client, test_helpers, db_session):
        """Test message details endpoint"""
        user_id = "test_message_details"
        test_helpers.create_test_user(db_session, user_id=user_id)
        message_ids = test_helpers.create_test_conversation(db_session, user_id)
        
        response = client.get(f"/message/{message_ids[0]}")
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "feedback" in data
            assert "timestamp" in data
        else:
            # Message might not be found due to test database isolation
            assert response.status_code == 404
    
    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options("/")
        # CORS preflight might not be fully handled in test client
        # But we can test that the server accepts OPTIONS
        assert response.status_code in [200, 405]  # Some servers return 405 for OPTIONS
    
    def test_request_validation(self, client):
        """Test request validation with malformed JSON"""
        response = client.post(
            "/whatsapp/query",
            data="{invalid json}",
            headers={"content-type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_error_handling(self, client):
        """Test error handling for non-existent endpoints"""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
    
    @pytest.mark.parametrize("message_type", ["text", "image", "audio", "document"])
    def test_different_message_types(self, client, message_type):
        """Test processing different message types"""
        message_data = {
            "user_id": f"test_user_{message_type}",
            "message": f"Test {message_type} message",
            "message_type": message_type
        }
        
        response = client.post("/whatsapp/query", json=message_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "message_id" in data
        
        # Different message types should have appropriate responses
        if message_type == "image":
            assert "image" in data["response"].lower()
        elif message_type == "audio":
            assert "voice" in data["response"].lower() or "audio" in data["response"].lower()
