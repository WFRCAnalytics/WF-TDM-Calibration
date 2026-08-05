"""Custom exceptions, kept specific so CLI output and logs can be precise about
what failed and why -- this matters for the framework's validation-before-execution
and traceability goals."""


class tdmcalibError(Exception):
    """Base class for all framework errors."""


class ConfigValidationError(tdmcalibError):
    """Raised when a calibration_runs/*.yaml / framework.yaml fails schema
    validation, or references something (a calibration run or baseline file)
    that does not exist."""


class VersionResolutionError(tdmcalibError):
    """Raised when the requested TDM ref cannot be resolved, the submodule
    working tree is dirty, or the resolved state cannot be verified."""


class ControlCenterError(tdmcalibError):
    """Raised when a Control Center baseline file cannot be read, or when a
    calibration run's override key does not exist in the chosen baseline."""


class ExecutionError(tdmcalibError):
    """Raised when the TDM batch entry point exits with a non-zero status."""


class OutputCollectionError(tdmcalibError):
    """Raised when a selected output file exceeds the configured size limit,
    or an output selection pattern matches nothing and is marked as required."""


class PrepScriptError(tdmcalibError):
    """Raised when a declared prep script is not found or exits non-zero."""


class DriverScriptError(tdmcalibError):
    """Raised when a declared driver_script (custom _HailMary.s) is not found."""


class RunSeedError(tdmcalibError):
    """Raised when a declared start_from_copy source calibration run has no
    successful recorded run, or its recorded working folder no longer exists
    on disk."""
