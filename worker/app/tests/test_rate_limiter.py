import pytest

from app.rate_limiter import DomainRateLimiter


def test_second_call_on_same_domain_sleeps_for_remaining_interval() -> None:
    fake_time = [0.0]
    sleeps: list[float] = []

    def clock() -> float:
        return fake_time[0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        fake_time[0] += seconds

    limiter = DomainRateLimiter(60, clock=clock, sleep=sleep)  # 1 request/second

    limiter.wait("example.com")
    fake_time[0] += 0.4
    limiter.wait("example.com")

    assert sleeps == [pytest.approx(0.6)]


def test_does_not_sleep_once_enough_time_has_passed() -> None:
    fake_time = [0.0]
    sleeps: list[float] = []

    limiter = DomainRateLimiter(
        60, clock=lambda: fake_time[0], sleep=lambda s: sleeps.append(s)
    )

    limiter.wait("example.com")
    fake_time[0] += 5.0
    limiter.wait("example.com")

    assert sleeps == []


def test_different_domains_do_not_rate_limit_each_other() -> None:
    sleeps: list[float] = []
    limiter = DomainRateLimiter(60, clock=lambda: 0.0, sleep=lambda s: sleeps.append(s))

    limiter.wait("example.com")
    limiter.wait("other.com")

    assert sleeps == []


def test_crawl_delay_overrides_default_interval() -> None:
    fake_time = [0.0]
    sleeps: list[float] = []

    limiter = DomainRateLimiter(
        6000, clock=lambda: fake_time[0], sleep=lambda s: sleeps.append(s)
    )  # tiny default interval, should be overridden by crawl_delay

    limiter.wait("example.com", crawl_delay_seconds=2.0)
    fake_time[0] += 0.1
    limiter.wait("example.com", crawl_delay_seconds=2.0)

    assert sleeps == [pytest.approx(1.9)]
