"""POST /contact testlari (haqiqiy Telegram/SMTP'ga so'rov yuborilmaydi)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

import contact
import main

client = TestClient(main.app)
BODY = {"topic": "Savol", "name": "Ali", "contact": "+998901234567", "message": "Salom!"}


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    contact._hits.clear()
    monkeypatch.setattr(contact, "TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setattr(contact, "TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(contact, "SMTP_HOST", "")


def test_contact_sends_to_telegram(monkeypatch):
    sent = {}

    async def fake_tg(text):
        sent["text"] = text
        return True

    monkeypatch.setattr(contact, "_send_telegram", fake_tg)
    res = client.post("/contact", json=BODY)
    assert res.status_code == 200
    assert "Ali" in sent["text"] and "Salom!" in sent["text"]


def test_contact_honeypot_sends_nothing(monkeypatch):
    async def boom(text):
        raise AssertionError("yuborilmasligi kerak")

    monkeypatch.setattr(contact, "_send_telegram", boom)
    assert client.post("/contact", json={**BODY, "website": "spam.com"}).status_code == 200


def test_contact_rejects_unknown_topic():
    assert client.post("/contact", json={**BODY, "topic": "Boshqa"}).status_code == 422


def test_contact_503_when_no_channel(monkeypatch):
    monkeypatch.setattr(contact, "TELEGRAM_BOT_TOKEN", "")
    assert client.post("/contact", json=BODY).status_code == 503


def test_contact_502_when_delivery_fails(monkeypatch):
    async def fail(text):
        return False

    monkeypatch.setattr(contact, "_send_telegram", fail)
    assert client.post("/contact", json=BODY).status_code == 502


def test_contact_rate_limited(monkeypatch):
    async def ok(text):
        return True

    monkeypatch.setattr(contact, "_send_telegram", ok)
    codes = [client.post("/contact", json=BODY).status_code for _ in range(contact.PER_IP_MAX + 1)]
    assert codes[-1] == 429
