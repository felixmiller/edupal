def test_dep_imports():
    import pyeda
    assert hasattr(pyeda, "__version__")
