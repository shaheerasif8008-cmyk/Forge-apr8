"""Provisioner: spins up local Docker infrastructure for the employee."""

from __future__ import annotations

import structlog

from factory.models.build import Build
from factory.models.deployment import Deployment, DeploymentStatus
from factory.pipeline.evaluator.container_runner import find_free_port, start_container

logger = structlog.get_logger(__name__)


async def provision(deployment: Deployment, build: Build) -> Deployment:
    """Run the packaged employee image as a local Docker container."""
    deployment.status = DeploymentStatus.PROVISIONING
    image_tag = str(build.metadata.get("image_tag", ""))
    port = find_free_port()
    container_name = f"forge-employee-{deployment.id}"

    logger.info("provisioner_start", deployment_id=str(deployment.id), image_tag=image_tag, port=port)
    container_id = await start_container(image_tag, port, name=container_name, environment="production")
    deployment.infrastructure = {
        "provider": "local_docker",
        "container_id": container_id,
        "container_name": container_name,
        "port": port,
        "image_tag": image_tag,
    }
    deployment.access_url = f"http://127.0.0.1:{port}"
    return deployment
