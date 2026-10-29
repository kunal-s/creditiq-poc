def test_package_imports():
    import copilot
    import pydantic_ai  # noqa: F401
    assert copilot.__doc__
