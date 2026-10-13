import pytest

from tests.fake import FakeTransport


@pytest.fixture(autouse=True)
def center(monkeypatch):
    """Never the live Commando Center or Supertext: reports and key checks go to a FakeTransport,
    in the same thread (so they see the test database)."""
    from wagtail_supertext import reporting

    transport = FakeTransport()
    monkeypatch.setattr(reporting, "transport", lambda: transport)
    monkeypatch.setattr(reporting, "BACKGROUND", False)
    monkeypatch.setenv("SUPERTEXT_REPORT_URL", "http://center.test/api/v1/report")
    monkeypatch.delenv("SUPERTEXT_VERSION_REPORTS", raising=False)
    return transport
