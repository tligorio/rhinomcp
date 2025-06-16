import pytest
import logging
import tempfile
from pathlib import Path

@pytest.fixture(scope="session")
def test_log_dir():
    """Create a temporary directory for test logs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture(scope="function")
def test_logger(test_log_dir):
    """Create a test logger instance."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Create a test log file
    log_file = test_log_dir / "test.log"
    
    # Create a file handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    
    # Create a formatter
    formatter = logging.Formatter("%(asctime)s  %(message)s")
    fh.setFormatter(formatter)
    
    # Add the handler to the logger
    logger.addHandler(fh)
    
    yield logger
    
    # Cleanup
    logger.handlers = []
    if log_file.exists():
        log_file.unlink() 