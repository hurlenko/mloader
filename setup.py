import os
from codecs import open

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

package_name = "mloader"

about = {}
with open(
    os.path.join(here, package_name, "__version__.py"), "r", "utf-8"
) as f:
    exec(f.read(), about)

with open("README.md", "r", "utf-8") as f:
    readme = f.read()


setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    long_description=readme,
    long_description_content_type="text/markdown",
    url=about["__url__"],
    packages=find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "Click>=6.2",
        "protobuf~=3.6",
        "requests>=2"
    ],
    license=about["__license__"],
    zip_safe=False,
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    project_urls={"Source": about["__url__"]},
    entry_points={
        "console_scripts": [f"{about['__title__']} = mloader.__main__:main"]
    },
)
