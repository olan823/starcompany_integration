from setuptools import find_packages, setup


setup(
    name="starcompany_integration",
    version="0.1.18",
    description="Native ERPNext integration boundary for Starcompany",
    author="Skychip",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[],
)