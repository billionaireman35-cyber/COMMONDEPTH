from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register() -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"message-{uuid4().hex}@example.com",
            "password": "VeryStrongPassword123!",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["user_id"], body["session_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_direct_messaging_flow_and_participant_privacy():
    sender_id, sender_token = _register()
    recipient_id, recipient_token = _register()
    _, outsider_token = _register()

    created = client.post(
        "/api/v1/messages/conversations",
        headers=_headers(sender_token),
        json={"recipient_id": recipient_id},
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]

    reopened = client.post(
        "/api/v1/messages/conversations",
        headers=_headers(recipient_token),
        json={"recipient_id": sender_id},
    )
    assert reopened.status_code == 201, reopened.text
    assert reopened.json()["id"] == conversation_id

    sent = client.post(
        f"/api/v1/messages/conversations/{conversation_id}/messages",
        headers=_headers(sender_token),
        json={"body": "Hello from COMMONDEPTH."},
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["sender_id"] == sender_id
    assert sent.json()["body"] == "Hello from COMMONDEPTH."

    inbox = client.get(
        "/api/v1/messages/conversations",
        headers=_headers(recipient_token),
    )
    assert inbox.status_code == 200, inbox.text
    assert any(item["id"] == conversation_id for item in inbox.json())

    history = client.get(
        f"/api/v1/messages/conversations/{conversation_id}",
        headers=_headers(recipient_token),
    )
    assert history.status_code == 200, history.text
    assert [m["body"] for m in history.json()["messages"]] == [
        "Hello from COMMONDEPTH."
    ]

    forbidden_history = client.get(
        f"/api/v1/messages/conversations/{conversation_id}",
        headers=_headers(outsider_token),
    )
    assert forbidden_history.status_code == 404

    forbidden_send = client.post(
        f"/api/v1/messages/conversations/{conversation_id}/messages",
        headers=_headers(outsider_token),
        json={"body": "I should not be able to send this."},
    )
    assert forbidden_send.status_code == 404
