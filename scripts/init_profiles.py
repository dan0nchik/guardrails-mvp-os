#!/usr/bin/env python3
"""
Initialize default rails profiles.

Run this script to generate default guardrails profiles.
"""
import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tool_proxy.registry import ToolRegistry
from app.agent.tools import register_default_tools
from app.dynamic_rails.builder import RailsProfileBuilder, create_default_profiles
import structlog

logger = structlog.get_logger()


async def main():
    """Initialize default profiles."""
    logger.info("Initializing default rails profiles")

    # Create tool registry
    registry = ToolRegistry()
    register_default_tools(registry)

    # Create builder
    profiles_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'app',
        'guardrails',
        'rails_profiles'
    )

    builder = RailsProfileBuilder(profiles_dir)

    # Create default profiles
    create_default_profiles(builder, registry)

    logger.info("Default profiles created successfully", profiles_dir=profiles_dir)


if __name__ == '__main__':
    asyncio.run(main())
