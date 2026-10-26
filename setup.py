from setuptools import setup

setup(
    name="wav-maker",
    version="1.0.0",
    py_modules=["app"],  # Explicitly list the app.py module
    include_package_data=True,
    install_requires=[
        "Flask>=3.1.3",
        "pydub>=0.25.1",
        "audioop-lts>=0.2.2; python_version >= '3.13'",
        "Werkzeug>=3.1.9",
        "gunicorn>=26.2.0",
    ],
    python_requires=">=3.11",
)
