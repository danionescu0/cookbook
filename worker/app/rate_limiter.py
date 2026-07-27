import time
from collections.abc import Callable


class DomainRateLimiter:
    """Politeness rate limiter, keyed per domain, in-memory for the life of the process.

    Not shared across worker replicas or restarts — fine for a single worker consuming
    jobs sequentially (see docker-compose.yml). Revisit with a shared store (e.g. Redis)
    if the worker is ever scaled out.
    """

    def __init__(
        self,
        default_requests_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._default_interval = 60.0 / default_requests_per_minute
        self._last_request_at: dict[str, float] = {}
        self._clock = clock
        self._sleep = sleep

    def wait(
        self,
        domain: str,
        crawl_delay_seconds: float | None = None,
        default_requests_per_minute: int | None = None,
    ) -> None:
        if crawl_delay_seconds is not None:
            interval = crawl_delay_seconds
        elif default_requests_per_minute is not None:
            # Overrides the interval baked in at construction, so a rate change made through the
            # Settings backoffice page applies to the very next request, not just new instances.
            interval = 60.0 / default_requests_per_minute
        else:
            interval = self._default_interval

        last = self._last_request_at.get(domain)
        if last is not None:
            remaining = interval - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)

        self._last_request_at[domain] = self._clock()
