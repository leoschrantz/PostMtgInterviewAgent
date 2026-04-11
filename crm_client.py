"""CRM client abstraction for fetching and updating meeting data.

This module defines an abstract CRMClient interface with pluggable
implementations. Swap MockCRMClient for DynamicsCRMClient (or another
real backend) without touching the rest of the app.

Usage:
    from crm_client import get_crm_client
    crm = get_crm_client()
    meetings = crm.get_meetings()
"""

import copy
from abc import ABC, abstractmethod

import streamlit as st

from mock_data import MOCK_MEETINGS


class CRMClient(ABC):
    """Abstract interface for any CRM backend (mock, Dynamics, Salesforce, etc.)."""

    @abstractmethod
    def get_meetings(self) -> list[dict]:
        """Return all meetings for the current user."""

    @abstractmethod
    def get_meeting(self, meeting_id: str) -> dict | None:
        """Return a single meeting by ID, or None if not found."""

    @abstractmethod
    def update_meeting(
        self,
        meeting_id: str,
        status: str | None = None,
        transcript: list | None = None,
        summary: dict | None = None,
    ) -> None:
        """Update a meeting's status and optionally store transcript/summary."""


class MockCRMClient(CRMClient):
    """In-memory mock CRM backed by Streamlit session state.

    Seeds from MOCK_MEETINGS on first access. All reads/writes go through
    session state so edits persist within a user's session.
    """

    _STATE_KEY = "meetings"

    def _store(self) -> list[dict]:
        if self._STATE_KEY not in st.session_state:
            st.session_state[self._STATE_KEY] = copy.deepcopy(MOCK_MEETINGS)
        return st.session_state[self._STATE_KEY]

    def get_meetings(self) -> list[dict]:
        return self._store()

    def get_meeting(self, meeting_id: str) -> dict | None:
        for meeting in self._store():
            if meeting["id"] == meeting_id:
                return meeting
        return None

    def update_meeting(
        self,
        meeting_id: str,
        status: str | None = None,
        transcript: list | None = None,
        summary: dict | None = None,
    ) -> None:
        for meeting in self._store():
            if meeting["id"] == meeting_id:
                if status is not None:
                    meeting["status"] = status
                if transcript is not None:
                    meeting["transcript"] = transcript
                if summary is not None:
                    meeting["summary"] = summary
                return


class DynamicsCRMClient(CRMClient):
    """Microsoft Dynamics 365 Web API client (stub).

    To implement:
    1. Use msal to acquire an access token via OAuth client credentials
    2. Call the Dataverse Web API:
       GET https://<org>.crm.dynamics.com/api/data/v9.2/appointments
       PATCH https://<org>.crm.dynamics.com/api/data/v9.2/appointments(<id>)
    3. Map Dataverse Appointment entity fields to our meeting dict schema
    4. Add the following to .streamlit/secrets.toml:
       DYNAMICS_TENANT_ID, DYNAMICS_CLIENT_ID,
       DYNAMICS_CLIENT_SECRET, DYNAMICS_ORG_URL

    Sign up for a free Power Platform Developer Plan to test against a
    real Dataverse environment:
    https://learn.microsoft.com/en-us/power-platform/developer/devenv/sign-up-developer-plan
    """

    def __init__(self, org_url: str, tenant_id: str, client_id: str, client_secret: str):
        self.org_url = org_url
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        raise NotImplementedError(
            "DynamicsCRMClient is a stub. Set CRM_BACKEND=mock in secrets "
            "or implement the Web API calls here."
        )

    def get_meetings(self) -> list[dict]:
        raise NotImplementedError

    def get_meeting(self, meeting_id: str) -> dict | None:
        raise NotImplementedError

    def update_meeting(
        self,
        meeting_id: str,
        status: str | None = None,
        transcript: list | None = None,
        summary: dict | None = None,
    ) -> None:
        raise NotImplementedError


@st.cache_resource
def get_crm_client() -> CRMClient:
    """Return the configured CRM client.

    Selection is controlled by the CRM_BACKEND secret:
    - "mock" (default): MockCRMClient with in-memory session state
    - "dynamics": DynamicsCRMClient hitting the real Dataverse Web API
    """
    backend = st.secrets.get("CRM_BACKEND", "mock").lower()

    if backend == "dynamics":
        return DynamicsCRMClient(
            org_url=st.secrets["DYNAMICS_ORG_URL"],
            tenant_id=st.secrets["DYNAMICS_TENANT_ID"],
            client_id=st.secrets["DYNAMICS_CLIENT_ID"],
            client_secret=st.secrets["DYNAMICS_CLIENT_SECRET"],
        )

    return MockCRMClient()
