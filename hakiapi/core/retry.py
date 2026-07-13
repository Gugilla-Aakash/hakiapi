from typing import Collection

from requests.adapters import HTTPAdapter
from urllib3.util import Retry


def create_retry_adapter(
    total_retries: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: Collection[int] | None = None,
    allowed_methods: Collection[str] | None = None,
) -> HTTPAdapter:
    """
    Creates an HTTPAdapter configured with exponential backoff and retry behavior.
    """

    if status_forcelist is None:
        status_forcelist = [429, 500, 502, 503, 504]

    retry_strategy = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,  # Explicitly expose method filtering
        raise_on_status=False,  # Defer error handling to HakiAPI exceptions
    )

    return HTTPAdapter(max_retries=retry_strategy)
