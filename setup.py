# External Libraries
from setuptools import setup, find_packages

if __name__ == '__main__':
    setup(
        name="bytecode_optimizer",
        author="martmists",
        author_email="mail@martmists.com",
        maintainer="martmists",
        maintainer_email="mail@martmists.com",
        license="MIT",
        zip_safe=False,
        version="0.1.0",
        description="A bytecode optimizer for python",
        long_description="TODO",
        url="https://github.com/Martmists/BytecodeOptimizer",
        packages=find_packages(),
        keywords=["bytecode", "optimizer", "speed"],
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Environment :: Console",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Topic :: Software Development :: Libraries :: Python Modules",
        ],
    )
