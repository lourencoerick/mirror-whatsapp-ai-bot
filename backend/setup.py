from setuptools import setup, find_packages

setup(
    name="whatsapp-ai-bot",
    package_dir={"": "app"},
    packages=find_packages(where="app"),
)
