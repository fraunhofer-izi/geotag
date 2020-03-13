import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="geotag",
    version="0.0.1",
    author="Dominik Otto",
    author_email="dominik.otto@gmail.com",
    description="Python tool to tag samples from GEO.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://ribogit.izi.fraunhofer.de/Dominik/geotag",
    packages=setuptools.find_packages(),
    classifiers=[
                "Programming Language :: Python :: 3",
                "License :: OSI Approved :: GNUv3 License",
                "Operating System :: OS Independent",
            ],
    python_requires='>=3.6',
)