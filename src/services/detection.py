"""Service detection functions for external dependencies."""

import asyncio
import logging
import subprocess
from datetime import datetime
from typing import Any

import httpx

from src.models.installation import ServiceStatus

logger = logging.getLogger(__name__)


class ServiceDetectionService:
    """Service for detecting availability of external services."""

    def __init__(self, timeout: int = 5):
        """Initialize service detection with timeout."""
        self.timeout = timeout

    def check_docker(self) -> ServiceStatus:
        """Check Docker availability via docker version command."""
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                version = result.stdout.strip()
                return ServiceStatus(
                    name="docker",
                    available=True,
                    version=version,
                    endpoint="unix:///var/run/docker.sock",
                    last_checked=datetime.now(),
                    error_message=None,
                    setup_completed=True
                )
            else:
                error = result.stderr.strip() if result.stderr else "Docker command failed"
                return ServiceStatus(
                    name="docker",
                    available=False,
                    version=None,
                    endpoint=None,
                    last_checked=datetime.now(),
                    error_message=error,
                    setup_completed=False
                )

        except subprocess.TimeoutExpired:
            return ServiceStatus(
                name="docker",
                available=False,
                version=None,
                endpoint=None,
                last_checked=datetime.now(),
                error_message="Docker command timed out",
                setup_completed=False
            )
        except FileNotFoundError:
            return ServiceStatus(
                name="docker",
                available=False,
                version=None,
                endpoint=None,
                last_checked=datetime.now(),
                error_message="Docker not found in PATH",
                setup_completed=False
            )
        except Exception as e:
            return ServiceStatus(
                name="docker",
                available=False,
                version=None,
                endpoint=None,
                last_checked=datetime.now(),
                error_message=f"Docker check failed: {str(e)}",
                setup_completed=False
            )

    async def check_ollama(self, endpoint: str = "http://localhost:11434") -> ServiceStatus:
        """Check Ollama availability via HTTP endpoint."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # First check if service is running
                response = await client.get(f"{endpoint}/api/tags")

                if response.status_code == 200:
                    # Try to get version from version endpoint
                    version = "unknown"
                    try:
                        version_response = await client.get(f"{endpoint}/api/version")
                        if version_response.status_code == 200:
                            version_data = version_response.json()
                            version = version_data.get("version", "unknown")
                    except Exception:
                        # If version endpoint fails, keep "unknown"
                        pass

                    return ServiceStatus(
                        name="ollama",
                        available=True,
                        version=version,
                        endpoint=endpoint,
                        last_checked=datetime.now(),
                        error_message=None,
                        setup_completed=True
                    )
                else:
                    return ServiceStatus(
                        name="ollama",
                        available=False,
                        version=None,
                        endpoint=endpoint,
                        last_checked=datetime.now(),
                        error_message=f"HTTP {response.status_code}: {response.text}",
                        setup_completed=False
                    )

        except httpx.TimeoutException:
            return ServiceStatus(
                name="ollama",
                available=False,
                version=None,
                endpoint=endpoint,
                last_checked=datetime.now(),
                error_message="Ollama endpoint timed out",
                setup_completed=False
            )
        except httpx.ConnectError:
            return ServiceStatus(
                name="ollama",
                available=False,
                version=None,
                endpoint=endpoint,
                last_checked=datetime.now(),
                error_message="Cannot connect to Ollama service",
                setup_completed=False
            )
        except Exception as e:
            return ServiceStatus(
                name="ollama",
                available=False,
                version=None,
                endpoint=endpoint,
                last_checked=datetime.now(),
                error_message=f"Ollama check failed: {str(e)}",
                setup_completed=False
            )


    async def check_qdrant(self, endpoint: str = "http://localhost:6333") -> ServiceStatus:
        """Check Qdrant availability via HTTP health endpoint."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{endpoint}/health")

                if response.status_code == 200:
                    # Try to get version from health response
                    try:
                        health_data = response.json()
                        version = health_data.get("version", "unknown")
                    except (ValueError, KeyError, TypeError):
                        version = "unknown"

                    return ServiceStatus(
                        name="qdrant",
                        available=True,
                        version=version,
                        endpoint=endpoint,
                        last_checked=datetime.now(),
                        error_message=None,
                        setup_completed=True
                    )
                else:
                    return ServiceStatus(
                        name="qdrant",
                        available=False,
                        version=None,
                        endpoint=endpoint,
                        last_checked=datetime.now(),
                        error_message=f"HTTP {response.status_code}: {response.text}",
                        setup_completed=False
                    )

        except httpx.TimeoutException:
            return ServiceStatus(
                name="qdrant",
                available=False,
                version=None,
                endpoint=endpoint,
                last_checked=datetime.now(),
                error_message="Qdrant endpoint timed out",
                setup_completed=False
            )
        except httpx.ConnectError:
            return ServiceStatus(
                name="qdrant",
                available=False,
                version=None,
                endpoint=endpoint,
                last_checked=datetime.now(),
                error_message="Cannot connect to Qdrant service",
                setup_completed=False
            )
        except Exception as e:
            return ServiceStatus(
                name="qdrant",
                available=False,
                version=None,
                endpoint=endpoint,
                last_checked=datetime.now(),
                error_message=f"Qdrant check failed: {str(e)}",
                setup_completed=False
            )

    async def check_all_services(
        self,
        endpoints: dict[str, str] | None = None
    ) -> dict[str, ServiceStatus]:
        """Check all services and return their status."""
        if endpoints is None:
            endpoints = {
                "ollama": "http://localhost:11434",
                "qdrant": "http://localhost:6333"
            }

        results = {}

        # Check Docker synchronously
        results["docker"] = self.check_docker()

        # Check HTTP/async services
        ollama_task = self.check_ollama(endpoints.get("ollama", "http://localhost:11434"))
        qdrant_task = self.check_qdrant(endpoints.get("qdrant", "http://localhost:6333"))

        ollama_status, qdrant_status = await asyncio.gather(
            ollama_task, qdrant_task, return_exceptions=True
        )

        # Handle any exceptions from async tasks
        if isinstance(ollama_status, Exception):
            results["ollama"] = ServiceStatus(
                name="ollama",
                available=False,
                version=None,
                endpoint=endpoints.get("ollama"),
                last_checked=datetime.now(),
                error_message=f"Ollama check exception: {str(ollama_status)}",
                setup_completed=False
            )
        else:
            results["ollama"] = ollama_status

        if isinstance(qdrant_status, Exception):
            results["qdrant"] = ServiceStatus(
                name="qdrant",
                available=False,
                version=None,
                endpoint=endpoints.get("qdrant"),
                last_checked=datetime.now(),
                error_message=f"Qdrant check exception: {str(qdrant_status)}",
                setup_completed=False
            )
        else:
            results["qdrant"] = qdrant_status

        return results

    def get_service_summary(self, statuses: dict[str, ServiceStatus]) -> dict[str, Any]:
        """Get a summary of service statuses for display."""
        summary = {
            "total_services": len(statuses),
            "available_services": sum(1 for s in statuses.values() if s.available),
            "setup_completed_services": sum(1 for s in statuses.values() if s.setup_completed),
            "services": {}
        }

        for name, status in statuses.items():
            summary["services"][name] = {
                "available": status.available,
                "version": status.version,
                "setup_completed": status.setup_completed,
                "error": status.error_message if not status.available else None
            }

        return summary
