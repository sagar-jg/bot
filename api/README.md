# UWS WhatsApp Chatbot API

This API provides a REST endpoint for interacting with the UWS WhatsApp Assistant using FastAPI.

## How to Run

1. Install dependencies (from the uwsbot directory):

   ```bash
   pip install -r requirements.txt
   ```

2. Start the API server:
   ```bash
   uvicorn uwsbot.api.main:app --reload
   ```

## Quick Start with Bash Script

1. Make the script executable:
   ```bash
   chmod +x uwsbot/api/start.sh
   ```
2. Run the script:
   ```bash
   ./uwsbot/api/start.sh
   ```

This will create a virtual environment (if needed), install dependencies, and start the FastAPI server.

## Endpoint

### POST `/whatsapp/query`

**Request Body:**

```json
{
  "user_id": "+919449248040",
  "message": "Whats the application process?"
}
```

**Response:**

```json
{
  "response": "<WhatsApp-friendly reply>"
}
```

## Folder Structure

- `schemas.py`: Pydantic models for request/response
- `whatsapp_service.py`: Core logic for answering queries
- `main.py`: FastAPI app and endpoint

---

For more details, see the code in each file.
