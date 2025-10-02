# -*- coding: utf-8 -*-

"""Common type definitions for the nac-test framework.

This module contains shared types, enums, and type aliases used across
the nac-test framework for configuration, orchestration, and test execution.
"""

from enum import Enum


class TestExecutionModeOptions(str, Enum):
    """Test execution mode options for learning and testing phases.

    - LEARNING: Capture current state and save as expected baseline
    - TESTING: Compare current state against previously captured baseline
    """

    LEARNING = "learning"
    TESTING = "testing"
