"""Clean version of LearningModeMixin using cooperative inheritance.

This version properly inherits from aetest.Testcase to get processed by TestableMeta,
avoiding the need for the .source attribute hack.
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from pyats import aetest
from nac_test.pyats_core.reporting.types import ResultStatus
from nac_test.utils.parameters import (
    load_parameters_from_file,
    save_parameters_to_file,
)
from nac_test.utils.types import TestExecutionModeOptions

if TYPE_CHECKING:
    from nac_test.pyats_core.reporting.collector import TestResultCollector


class LearningModeMixin(aetest.Testcase):
    """Mixin that adds learning/testing mode capabilities to test classes.

    IMPORTANT: This mixin inherits from aetest.Testcase to ensure it's processed
    by PyATS's TestableMeta metaclass. This prevents the AttributeError when
    PyATS looks for .source attributes on methods.

    Usage with Multiple Inheritance:
        class YourTest(LearningModeMixin, IOSXESSHTestBase):
            # Your test implementation
            pass

    The Method Resolution Order (MRO) will be:
        YourTest -> LearningModeMixin -> IOSXESSHTestBase -> ... -> aetest.Testcase

    Since both LearningModeMixin and IOSXESSHTestBase ultimately inherit from
    aetest.Testcase, Python's MRO algorithm (C3 linearization) ensures that
    aetest.Testcase appears only once in the inheritance chain.

    IMPORTANT: When using cooperative inheritance, always call super().__init__()
    in your __init__ methods to ensure all parent classes are properly initialized.
    """

    SUPPORTS_LEARNING_MODE: bool = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the mixin with cooperative inheritance."""
        # Call parent __init__ to ensure proper initialization chain
        super().__init__(*args, **kwargs)

    # Type hints for attributes expected from base class
    if TYPE_CHECKING:
        from typing import Callable

        logger: logging.Logger
        result_collector: "TestResultCollector"

        def failed(self, reason: str) -> None:
            """Mark test as failed (provided by PyATS aetest.Testcase)."""
            ...

        def passed(self, reason: str = "") -> None:
            """Mark test as passed (provided by PyATS aetest.Testcase)."""
            ...

    def collect_current_state(self) -> Dict[str, Any]:
        """Collect the current state for learning/testing mode.

        This method should be overridden by subclasses.
        Default implementation returns an empty dict.

        Returns:
            Dictionary containing the current state to capture/verify
        """
        return {}

    def compare_states(
        self, current_state: Dict[str, Any], expected_state: Dict[str, Any]
    ) -> None:
        """Compare current state against expected state.

        This method should be overridden by subclasses.
        Default implementation does nothing (passes).

        Args:
            current_state: Current state collected from the system
            expected_state: Expected state loaded from parameters file

        Raises:
            AssertionError: If states don't match (or any other exception)
        """
        pass

    def get_test_execution_mode(self) -> str:
        """Get the test execution mode from environment.

        Returns:
            Test execution mode string: "learning" or "testing" (default: "testing")
        """
        mode_str = os.environ.get(
            "TEST_EXECUTION_MODE", TestExecutionModeOptions.TESTING.value
        ).lower()
        return mode_str

    def get_parameters_file_path(self, test_name: Optional[str] = None) -> Path:
        """Get the path to the parameters file for this test.

        Args:
            test_name: Optional test name override (defaults to test class name)

        Returns:
            Path to the parameters JSON file for this test

        Raises:
            FileNotFoundError: If TEST_PARAMETERS_DIR is not set
        """
        parameters_dir_path = os.environ.get("TEST_PARAMETERS_DIR")
        if not parameters_dir_path:
            raise FileNotFoundError(
                "Environment variable TEST_PARAMETERS_DIR is not set"
            )

        # Create test_parameters directory (and any parent directories)
        parameters_dir = Path(parameters_dir_path)
        parameters_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename based on test class name or provided name
        if test_name is None:
            test_name = self.__class__.__name__

        # For device-centric tests, include hostname in the filename
        # This allows each device to have its own learned parameters
        if hasattr(self, "hostname") and self.hostname:
            parameters_file = (
                parameters_dir / f"{test_name}_{self.hostname}_parameters.json"
            )
        else:
            parameters_file = parameters_dir / f"{test_name}_parameters.json"

        return parameters_file

    def handle_test_execution_mode(
        self,
        test_name: Optional[str] = None,
    ) -> None:
        """Handle test execution based on learning or testing mode.

        This method provides the core learning/testing mode pattern:
        - Learning mode: Calls collect_current_state() and saves it as expected baseline
        - Testing mode: Loads expected state and calls compare_states() to verify

        Args:
            test_name: Optional test name for parameters file (defaults to class name)
        """
        import asyncio

        # Get test execution mode and parameters file
        mode = self.get_test_execution_mode()
        parameters_file = self.get_parameters_file_path(test_name)

        # Collect current state by calling the overridden method
        try:
            # Check if the method is async and handle accordingly
            if asyncio.iscoroutinefunction(self.collect_current_state):
                loop = asyncio.get_event_loop()
                current_state = loop.run_until_complete(self.collect_current_state())
            else:
                current_state = self.collect_current_state()
        except NotImplementedError as e:
            result_msg = f"Test does not implement learning mode methods: {str(e)}"
            self.logger.error(result_msg)
            self.result_collector.add_result(
                status=ResultStatus.FAILED, message=result_msg
            )
            self.failed(result_msg)
            return

        # LEARNING MODE: Save the collected data to parameters file
        if mode == TestExecutionModeOptions.LEARNING.value:
            try:
                if save_parameters_to_file(current_state, parameters_file):
                    result_msg = f"Successfully learned parameters and saved to {parameters_file.name}"
                    self.logger.info(result_msg)
                    self.result_collector.add_result(
                        status=ResultStatus.PASSED, message=result_msg
                    )
                    self.passed(result_msg)
                else:
                    result_msg = f"Failed to save parameters to {parameters_file.name}"
                    self.logger.error(result_msg)
                    self.result_collector.add_result(
                        status=ResultStatus.FAILED, message=result_msg
                    )
                    self.failed(result_msg)
            except Exception as e:
                result_msg = f"Error saving parameters: {str(e)}"
                self.logger.error(result_msg)
                self.result_collector.add_result(
                    status=ResultStatus.FAILED, message=result_msg
                )
                self.failed(result_msg)

        # TESTING MODE: Verify against parameters file
        else:
            # Load expected parameters
            expected_parameters = load_parameters_from_file(parameters_file)

            if not expected_parameters:
                result_msg = (
                    f"No expected parameters found in {parameters_file.name}. "
                    "Run in learning mode first."
                )
                self.logger.error(result_msg)
                self.result_collector.add_result(
                    status=ResultStatus.FAILED, message=result_msg
                )
                self.failed(result_msg)
                return

            self.logger.info("Comparing current state to expected parameters")
            try:
                # Call the overridden comparison method
                if asyncio.iscoroutinefunction(self.compare_states):
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(
                        self.compare_states(current_state, expected_parameters)
                    )
                else:
                    self.compare_states(current_state, expected_parameters)

                result_msg = (
                    "The current state has been successfully "
                    "validated against the expected parameters."
                )
                self.logger.info(result_msg)
                self.result_collector.add_result(
                    status=ResultStatus.PASSED, message=result_msg
                )
                self.passed(result_msg)

            except NotImplementedError as e:
                result_msg = f"Test does not implement learning mode methods: {str(e)}"
                self.logger.error(result_msg)
                self.result_collector.add_result(
                    status=ResultStatus.FAILED, message=result_msg
                )
                self.failed(result_msg)

            except Exception as e:
                result_msg = f"Validation failed: {str(e)}"
                self.logger.error(result_msg)
                self.result_collector.add_result(
                    status=ResultStatus.FAILED, message=result_msg
                )
                self.failed(result_msg)
