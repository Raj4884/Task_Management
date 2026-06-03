"""Failure-scenario manager for the log simulator.

Defines several realistic failure scenarios that temporarily modify
generator behaviour to produce error spikes, latency surges, cascading
failures, memory leaks, deployment restarts, and rate-limit storms.

Each scenario runs in a background thread so the main loop's log
generation is not blocked.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.generators.base import BaseLogGenerator

logger = logging.getLogger("simulator.scenarios")


class ScenarioManager:
    """Manages and triggers failure scenarios against log generators.

    Parameters
    ----------
    generators:
        Mapping of ``service_name`` → ``BaseLogGenerator`` instance.
    """

    def __init__(self, generators: dict[str, "BaseLogGenerator"]) -> None:
        self.generators = generators
        self._active_scenarios: list[threading.Thread] = []
        self._service_names: list[str] = list(generators.keys())

        # Registry of scenario functions
        self._scenarios = [
            self.error_spike,
            self.latency_surge,
            self.cascading_failure,
            self.memory_leak,
            self.deployment_restart,
            self.rate_limit_storm,
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trigger_random(self) -> str:
        """Pick and execute a random scenario, return its name."""
        scenario_fn = random.choice(self._scenarios)
        name = scenario_fn.__name__
        service = random.choice(self._service_names)

        logger.info("🎲 Triggering scenario '%s' on '%s'", name, service)

        # Run scenario in a background daemon thread so it doesn't block
        t = threading.Thread(
            target=self._run_scenario,
            args=(scenario_fn, service),
            daemon=True,
            name=f"scenario-{name}-{service}",
        )
        t.start()
        self._active_scenarios.append(t)

        # Clean up finished threads
        self._active_scenarios = [
            th for th in self._active_scenarios if th.is_alive()
        ]

        return f"{name} → {service}"

    @property
    def active_count(self) -> int:
        """Number of currently running scenarios."""
        self._active_scenarios = [
            th for th in self._active_scenarios if th.is_alive()
        ]
        return len(self._active_scenarios)

    # ------------------------------------------------------------------
    # Scenario implementations
    # ------------------------------------------------------------------

    def error_spike(self, service: str, duration_sec: int = 30) -> None:
        """Dramatically increase error rate for *service*.

        During the spike the error probability is raised to 60-80%,
        producing a visible burst of ERROR and FATAL logs.
        """
        gen = self.generators[service]
        original_rate = gen._error_rate_override  # noqa: SLF001
        spike_rate = random.uniform(0.6, 0.8)

        logger.warning(
            "⚡ ERROR SPIKE on %s: error_rate=%.0f%% for %ds",
            service, spike_rate * 100, duration_sec,
        )
        gen.set_error_rate(spike_rate)
        time.sleep(duration_sec)

        # Restore
        if original_rate is not None:
            gen.set_error_rate(original_rate)
        else:
            gen.reset()
        logger.info("✅ Error spike on %s resolved", service)

    def latency_surge(self, service: str, duration_sec: int = 60) -> None:
        """Multiply response times for *service* to simulate slowdowns.

        The latency factor is raised to 5–15×, so logs show very high
        ``duration_ms`` values.
        """
        gen = self.generators[service]
        factor = random.uniform(5.0, 15.0)

        logger.warning(
            "🐢 LATENCY SURGE on %s: factor=%.1fx for %ds",
            service, factor, duration_sec,
        )
        gen.set_latency_factor(factor)

        # Also bump warnings slightly
        gen.set_error_rate(0.15)
        time.sleep(duration_sec)

        gen.reset()
        logger.info("✅ Latency surge on %s resolved", service)

    def cascading_failure(self, service: str, delay_sec: int = 5) -> None:
        """Simulate a cascading failure starting from *service*.

        The failure propagates to 2-3 other services with a delay
        between each one.  All services experience elevated error rates
        for 30 seconds after the cascade completes.
        """
        cascade_targets = random.sample(
            [s for s in self._service_names if s != service],
            k=min(random.randint(2, 3), len(self._service_names) - 1),
        )

        chain = [service] + cascade_targets
        logger.warning(
            "🔥 CASCADING FAILURE: %s (delay=%ds each)",
            " → ".join(chain), delay_sec,
        )

        for svc in chain:
            gen = self.generators[svc]
            gen.set_error_rate(random.uniform(0.4, 0.7))
            gen.inject_messages([
                ("ERROR", f"Downstream dependency failure detected – {svc} degraded"),
                ("ERROR", f"Circuit breaker OPEN for upstream service"),
                ("WARN", f"Request queue backing up: cascade from {service}"),
            ])
            time.sleep(delay_sec)

        # Hold for a while then recover
        time.sleep(30)

        for svc in chain:
            self.generators[svc].reset()
            self.generators[svc].inject_messages([
                ("INFO", f"Service {svc} recovered – circuit breaker CLOSED"),
            ])
        logger.info("✅ Cascading failure resolved: %s", " → ".join(chain))

    def memory_leak(self, service: str, duration_sec: int = 120) -> None:
        """Simulate gradually increasing memory usage leading to OOM.

        Over the duration, warning messages about memory usage are
        injected with increasing severity, culminating in an OOM fatal
        error.
        """
        gen = self.generators[service]
        steps = max(duration_sec // 10, 4)
        step_sleep = duration_sec / steps

        logger.warning(
            "🧠 MEMORY LEAK on %s: %d steps over %ds",
            service, steps, duration_sec,
        )

        for i in range(steps):
            usage_pct = min(50 + (i * 50 // steps), 99)
            heap_mb = 256 + (i * 3800 // steps)
            gen.inject_messages([
                ("WARN", f"Memory usage at {usage_pct}%: heap={heap_mb}MB, "
                         f"GC frequency increasing"),
            ])
            if usage_pct > 85:
                gen.set_error_rate(0.2 + (usage_pct - 85) * 0.03)
                gen.inject_messages([
                    ("ERROR", f"GC overhead limit exceeded: {usage_pct}% heap used"),
                ])
            time.sleep(step_sleep)

        # OOM crash
        gen.inject_messages([
            ("FATAL", f"OutOfMemoryError: Java heap space – service {service} "
                      f"terminated (heap=4096MB)"),
            ("ERROR", f"Process {service} exited with code 137 (OOM killed)"),
        ])
        gen.set_error_rate(0.9)
        time.sleep(5)

        # Recovery
        gen.reset()
        gen.inject_messages([
            ("INFO", f"Service {service} restarted after OOM – heap limit increased to 6144MB"),
            ("INFO", f"Health check passed for {service} – back in rotation"),
        ])
        logger.info("✅ Memory leak scenario on %s resolved", service)

    def deployment_restart(self, service: str) -> None:
        """Simulate a rolling deployment restart for *service*.

        The service briefly goes down (high error rate), then comes back
        with startup logs.
        """
        gen = self.generators[service]

        logger.warning("🚀 DEPLOYMENT RESTART for %s", service)

        # Pre-deploy drain
        gen.inject_messages([
            ("INFO", f"Deployment initiated for {service} – draining connections"),
            ("WARN", f"Service {service} entering maintenance mode"),
        ])
        time.sleep(3)

        # Shutdown
        gen.inject_messages([
            ("INFO", f"Graceful shutdown initiated for {service}"),
            ("INFO", f"Closed {random.randint(10, 200)} active connections"),
            ("INFO", f"Flushed metrics buffer: {random.randint(500, 5000)} data points"),
        ])
        gen.set_error_rate(0.8)
        time.sleep(5)

        # Brief downtime
        gen.inject_messages([
            ("ERROR", f"Connection refused: {service} is not accepting connections"),
            ("ERROR", f"Health check failed: {service} returned HTTP 503"),
        ])
        time.sleep(3)

        # Startup
        gen.reset()
        version = f"{random.randint(1, 5)}.{random.randint(0, 99)}.{random.randint(0, 999)}"
        gen.inject_messages([
            ("INFO", f"Starting {service} v{version} (pid={random.randint(1, 65535)})"),
            ("INFO", f"Configuration loaded from environment"),
            ("INFO", f"Database connection pool initialised: size=20"),
            ("INFO", f"Redis connection established"),
            ("INFO", f"Registered {random.randint(5, 30)} HTTP routes"),
            ("INFO", f"Health endpoint /healthz responding OK"),
            ("INFO", f"Service {service} v{version} ready – accepting traffic"),
        ])
        logger.info("✅ Deployment restart for %s completed (v%s)", service, version)

    def rate_limit_storm(self, service: str, duration_sec: int = 20) -> None:
        """Simulate a burst of 429 rate-limit errors.

        The service receives a flood of rate-limited requests, resulting
        in many WARN/ERROR logs.
        """
        gen = self.generators[service]

        logger.warning(
            "🚦 RATE LIMIT STORM on %s for %ds",
            service, duration_sec,
        )

        gen.set_error_rate(0.5)
        burst_count = random.randint(50, 200)

        rate_messages: list[tuple[str, str]] = []
        for _ in range(burst_count):
            rate_messages.append((
                random.choice(["WARN", "ERROR"]),
                f"Rate limit exceeded: HTTP 429 returned to client "
                f"(bucket={service}:api, retry_after={random.randint(1, 60)}s)",
            ))

        # Inject in chunks to spread over the duration
        chunk_size = max(burst_count // max(duration_sec // 2, 1), 5)
        for i in range(0, len(rate_messages), chunk_size):
            gen.inject_messages(rate_messages[i:i + chunk_size])
            time.sleep(2)

        gen.reset()
        gen.inject_messages([
            ("INFO", f"Rate limit storm subsided for {service} – normal traffic resumed"),
        ])
        logger.info("✅ Rate limit storm on %s resolved", service)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _run_scenario(
        scenario_fn: "type[ScenarioManager.error_spike]",  # noqa: PYI019
        service: str,
    ) -> None:
        """Execute a scenario function, catching any exceptions."""
        try:
            scenario_fn(service)
        except Exception:
            logger.exception("Scenario %s failed for %s", scenario_fn.__name__, service)
