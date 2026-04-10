import pytest

# root.after() from background threads raises RuntimeError when mainloop() is
# not running (test environment only — works fine in production with mainloop).
# Suppress the resulting PytestUnhandledThreadExceptionWarning.


def pytest_configure(config):
    config.addinivalue_line(
        "filterwarnings",
        "ignore::pytest.PytestUnhandledThreadExceptionWarning",
    )
