"""
LogSentry - Log Simulator main entry point.
Generates realistic log data from multiple fake microservices.
"""

import os
import sys
import json
import signal
import asyncio
import random
import logging
import httpx

from app.generators.auth_service import AuthServiceGenerator
from app.generators.payment_service import PaymentServiceGenerator
from app.generators.order_service import OrderServiceGenerator
from app.generators.user_service import UserServiceGenerator
from app.generators.notification_service import NotificationServiceGenerator
from app.scenarios import ScenarioManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIMULATOR] %(levelname)s: %(message)s",
)
logger = logging.getLogger("simulator")


class LogSimulator:
    """Main log simulator that coordinates generators and scenarios."""

    def __init__(self):
        self.ingestion_url = os.getenv("INGESTION_URL", "http://api-gateway:8000/api/ingest/batch")
        self.rate = int(os.getenv("SIMULATOR_RATE", "10"))  # logs per second
        self.running = True
        self.total_sent = 0
        self.errors = 0

        # Initialize generators
        self.generators_list = [
            AuthServiceGenerator(),
            PaymentServiceGenerator(),
            OrderServiceGenerator(),
            UserServiceGenerator(),
            NotificationServiceGenerator(),
        ]

        # Build dict keyed by service_name for ScenarioManager
        self.generators_dict = {g.service_name: g for g in self.generators_list}

        # Scenario manager
        spike_interval = int(os.getenv("SIMULATOR_ERROR_SPIKE_INTERVAL", "300"))
        self.scenario_manager = ScenarioManager(self.generators_dict)
        self.spike_interval = spike_interval

        # HTTP client
        self.client = None
        self.auth_token = None

    async def authenticate(self):
        """Get auth token for sending logs."""
        try:
            resp = await self.client.post(
                self.ingestion_url.replace("/api/ingest/batch", "/auth/login"),
                json={"username": "admin", "password": "admin123"},
            )
            if resp.status_code == 200:
                data = resp.json()
                self.auth_token = data.get("access_token")
                logger.info("Authenticated successfully")
            else:
                logger.warning(f"Auth failed ({resp.status_code}), sending without token")
        except Exception as e:
            logger.warning(f"Auth error: {e}, will retry later")

    async def run(self):
        """Main simulation loop."""
        self.client = httpx.AsyncClient(timeout=30.0)

        # Wait for API gateway to be ready
        logger.info("Waiting for API Gateway to be ready...")
        for attempt in range(60):
            try:
                resp = await self.client.get(
                    self.ingestion_url.replace("/api/ingest/batch", "/health")
                )
                if resp.status_code == 200:
                    logger.info("API Gateway is ready!")
                    break
            except Exception:
                pass
            await asyncio.sleep(5)

        await self.authenticate()

        logger.info(f"Starting log simulation at ~{self.rate} logs/sec")
        logger.info(f"Target: {self.ingestion_url}")
        logger.info(f"Services: {', '.join(g.service_name for g in self.generators_list)}")

        # Schedule periodic scenario triggers
        scenario_task = asyncio.create_task(self._scenario_loop())

        batch_interval = 2.0  # Send batch every 2 seconds
        logs_per_batch = max(1, int(self.rate * batch_interval))

        while self.running:
            try:
                # Generate batch of logs from all services
                batch = []
                for _ in range(logs_per_batch):
                    gen = random.choice(self.generators_list)
                    log = gen.generate_log()
                    batch.append(log)

                # Send batch
                await self._send_batch(batch)

                # Status update every 30 seconds
                if self.total_sent > 0 and self.total_sent % (self.rate * 30) < logs_per_batch:
                    logger.info(
                        f"📊 Sent {self.total_sent:,} logs | "
                        f"Errors: {self.errors} | "
                        f"Rate: ~{self.rate}/s"
                    )

                await asyncio.sleep(batch_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulation error: {e}")
                self.errors += 1
                await asyncio.sleep(5)

        scenario_task.cancel()
        await self.client.aclose()

    async def _scenario_loop(self):
        """Periodically trigger failure scenarios."""
        await asyncio.sleep(60)  # Wait before first scenario
        while self.running:
            try:
                name = self.scenario_manager.trigger_random()
                logger.info(f"🎲 Triggered scenario: {name}")
            except Exception as e:
                logger.debug(f"Scenario error: {e}")
            await asyncio.sleep(self.spike_interval)

    async def _send_batch(self, batch: list[dict]):
        """Send a batch of logs to the ingestion endpoint."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        payload = {"logs": batch}

        try:
            resp = await self.client.post(
                self.ingestion_url,
                json=payload,
                headers=headers,
            )

            if resp.status_code == 200 or resp.status_code == 202:
                self.total_sent += len(batch)
            elif resp.status_code == 401:
                # Re-authenticate
                await self.authenticate()
                if self.auth_token:
                    headers["Authorization"] = f"Bearer {self.auth_token}"
                    resp = await self.client.post(
                        self.ingestion_url, json=payload, headers=headers
                    )
                    if resp.status_code in (200, 202):
                        self.total_sent += len(batch)
            else:
                self.errors += 1
                if self.errors % 10 == 1:
                    logger.warning(f"Ingestion returned {resp.status_code}: {resp.text[:200]}")

        except httpx.ConnectError:
            self.errors += 1
            if self.errors % 30 == 1:
                logger.warning("Cannot connect to ingestion endpoint, retrying...")
            await asyncio.sleep(5)
        except Exception as e:
            self.errors += 1
            logger.debug(f"Send error: {e}")

    def stop(self):
        self.running = False


async def main():
    simulator = LogSimulator()

    def signal_handler(sig, frame):
        logger.info("Shutting down simulator...")
        simulator.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await simulator.run()


if __name__ == "__main__":
    asyncio.run(main())
