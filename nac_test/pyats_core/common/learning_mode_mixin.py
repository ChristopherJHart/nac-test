"""Mixin for tests that support learning/testing mode."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Type hints for attributes this mixin expects from the base class
    # These will be provided by NACTestBase (or its subclasses like SSHTestBase, APITestBase)
    from nac_test.pyats_core.reporting.collector import TestResultCollector


class LearningModeMixin:
    """Mixin that adds learning/testing mode capabilities to test classes.

    This mixin can be combined with any test base class (NACTestBase, SSHTestBase,
    APITestBase, etc.) to add learning mode capabilities. Tests can capture current
    network state (learning mode) and later verify against it (testing mode).

    Subclasses must implement:
    - collect_current_state(): Return dict with current state to capture/verify
    - compare_states(current, expected): Compare states, raise exception if mismatch

    The SUPPORTS_LEARNING_MODE marker allows the orchestrator to filter tests when
    running in learning mode - only tests using this mixin will execute in learning mode.

    Expected attributes from base class:
    - logger: logging.Logger - For logging messages
    - result_collector: TestResultCollector - For tracking test results
    - failed(msg): Method to mark test as failed
    - passed(msg): Method to mark test as passed

    Example:
        >>> class BGPOperationalTest(LearningModeMixin, SSHTestBase):
        ...     '''Test that captures and verifies BGP operational state.'''
        ...
        ...     def collect_current_state(self):
        ...         return {
        ...             "bgp_peers": self._get_bgp_peers(),
        ...             "routes": self._get_route_count(),
        ...         }
        ...
        ...     def compare_states(self, current, expected):
        ...         if current["bgp_peers"] != expected["bgp_peers"]:
        ...             raise AssertionError("BGP peer mismatch")
        ...         if current["routes"] != expected["routes"]:
        ...             raise AssertionError("Route count mismatch")
        ...
        ...     @aetest.test
        ...     def verify_bgp_operational_state(self):
        ...         self.handle_test_execution_mode()

    Note:
        Tests that don't use this mixin will be skipped when running in learning mode,
        but will execute normally in testing mode (using data models only).
    """

    SUPPORTS_LEARNING_MODE: bool = True

    # Type hints for attributes expected from base class (duck typing)
    if TYPE_CHECKING:
        logger: logging.Logger
        result_collector: "TestResultCollector"

        def failed(self, reason: str) -> None:
            """Mark test as failed (provided by PyATS aetest.Testcase)."""
            ...

        def passed(self, reason: str = "") -> None:
            """Mark test as passed (provided by PyATS aetest.Testcase)."""
            ...

    # =========================================================================
    # ABSTRACT METHODS - Must be implemented by subclasses
    # =========================================================================

    def collect_current_state(self) -> Dict[str, Any]:
        """Collect the current state for learning/testing mode.

        This method must be overridden by subclasses that use LearningModeMixin.
        It should return a dictionary representing the current state of the system
        that will be saved (in learning mode) or compared (in testing mode).

        Returns:
            Dictionary containing the current state to capture/verify

        Raises:
            NotImplementedError: If the subclass doesn't implement this method

        Example:
            >>> def collect_current_state(self):
            ...     return {
            ...         "bgp_peers": self._get_bgp_peers(),
            ...         "routes": self._get_routes(),
            ...         "interfaces": self._get_interfaces(),
            ...     }
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement collect_current_state(). "
            f"This method is required for learning/testing mode."
        )

    def compare_states(
        self, current_state: Dict[str, Any], expected_state: Dict[str, Any]
    ) -> None:
        """Compare current state against expected state.

        This method must be overridden by subclasses that use LearningModeMixin.
        It should compare the current state against the expected state and raise
        an exception if there are differences.

        Args:
            current_state: Current state collected from the system
            expected_state: Expected state loaded from parameters file

        Raises:
            AssertionError: If states don't match (or any other exception)
            NotImplementedError: If the subclass doesn't implement this method

        Example:
            >>> def compare_states(self, current, expected):
            ...     if current["bgp_peers"] != expected["bgp_peers"]:
            ...         raise AssertionError(
            ...             f"BGP peer count mismatch: {current['bgp_peers']} != {expected['bgp_peers']}"
            ...         )
            ...     if current["routes"] != expected["routes"]:
            ...         raise AssertionError("Route count mismatch")
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement compare_states(). "
            f"This method is required for learning/testing mode."
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def get_test_execution_mode(self) -> str:
        """Get the test execution mode from environment.

        Returns:
            Test execution mode string: "learning" or "testing" (default: "testing")

        Note:
            Returns a string value to maintain compatibility with file-based comparisons.
            The environment variable is set by the orchestrator from TestExecutionModeOptions enum.
        """
        from nac_test.utils.types import TestExecutionModeOptions

        mode_str = os.environ.get(
            "TEST_EXECUTION_MODE", TestExecutionModeOptions.TESTING.value
        ).lower()
        return mode_str

    def get_parameters_file_path(self, test_name: Optional[str] = None) -> Path:
        """Get the path to the parameters file for this test.

        The parameters file is stored in a test_parameters directory within
        the data directory (parent of the merged data model file).

        Args:
            test_name: Optional test name override (defaults to test class name)

        Returns:
            Path to the parameters JSON file for this test
        """
        # Get data directory from merged data model path
        data_file_path = os.environ.get("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH")
        if not data_file_path:
            raise FileNotFoundError(
                "Environment variable MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH is not set"
            )

        data_file = Path(data_file_path)
        data_dir = data_file.parent

        # Create test_parameters directory under data directory
        parameters_dir = data_dir / "test_parameters"
        parameters_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename based on test class name or provided name
        if test_name is None:
            test_name = self.__class__.__name__

        parameters_file = parameters_dir / f"{test_name}_parameters.json"

        return parameters_file

    # =========================================================================
    # MAIN ORCHESTRATION METHOD
    # =========================================================================

    def handle_test_execution_mode(
        self,
        test_name: Optional[str] = None,
    ) -> None:
        """Handle test execution based on learning or testing mode.

        This method provides the core learning/testing mode pattern by calling
        the abstract methods that subclasses must override:
        - Learning mode: Calls collect_current_state() and saves it as expected baseline
        - Testing mode: Loads expected state and calls compare_states() to verify

        Args:
            test_name: Optional test name for parameters file (defaults to class name)

        The method automatically handles:
        - Getting test execution mode from environment
        - Getting/creating parameters file path
        - Saving parameters in learning mode
        - Loading and comparing parameters in testing mode
        - Adding results to the result collector

        Example usage in test method:
            >>> @aetest.test
            >>> def verify_network_state(self):
            ...     self.handle_test_execution_mode()
        """
        from nac_test.pyats_core.reporting.types import ResultStatus
        from nac_test.utils.parameters import (
            load_parameters_from_file,
            save_parameters_to_file,
        )
        from nac_test.utils.types import TestExecutionModeOptions

        # Get test execution mode and parameters file
        mode = self.get_test_execution_mode()
        parameters_file = self.get_parameters_file_path(test_name)

        # Collect current state by calling the overridden method
        try:
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
