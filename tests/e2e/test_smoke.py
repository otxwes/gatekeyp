"""End-to-end smoke: server boots isolated, home renders, console clean."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_server_is_up_and_isolated(server):
    assert server.db_path.endswith("keys.db")
    assert "gkp-e2e-" in server.db_path
    # Fernet key from .env.dev (deterministic dev secrets)
    assert server.organizer_key


def test_home_view_renders(attendee_context, server):
    page = attendee_context.new_page()
    page.goto(server.base_url)
    expect(page.locator(".brand-name")).to_have_text("cellar")
    expect(page.locator("nav.topnav a[href='#/organize']")).to_be_visible()
