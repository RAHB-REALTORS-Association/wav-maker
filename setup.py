from setuptools import setup

setup(
    name="audio-converter",
    version="1.0.0",
    py_modules=["app"],  # Explicitly list the app.py module
    include_package_data=True,
    install_requires=[
        "Flask>=2.2.0",
        "pydub>=0.25.1",
        "Werkzeug>=2.2.0",
        "gunicorn>=20.1.0",
    ],
    python_requires=">=3.8",
)