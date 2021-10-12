"""Deebotozmo module."""
from typing import Tuple

from deebotozmo._api_client import _InternalApiClient
from deebotozmo.api_client import ApiClient
from deebotozmo.authentication import Authenticator
from deebotozmo.models import Configuration


def create_instances(
    config: Configuration, account_id: str, password_hash: str
) -> Tuple[Authenticator, ApiClient]:
    """Create a authenticator and api client instance."""
    internal_api_client = _InternalApiClient(config)
    authenticator = Authenticator(
        config, internal_api_client, account_id, password_hash
    )
    api_client = ApiClient(internal_api_client, authenticator)

    return authenticator, api_client
