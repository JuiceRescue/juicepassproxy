import asyncio

import dns.resolver

from juicepassproxy import resolve_ip_external_dns


def test_resolve_nxdomain_returns_none(monkeypatch):
    def raise_nxdomain(self, *args, **kwargs):
        raise dns.resolver.NXDOMAIN()

    monkeypatch.setattr(dns.resolver.Resolver, "resolve", raise_nxdomain)
    assert asyncio.run(resolve_ip_external_dns("nonexistent.example.invalid")) is None
