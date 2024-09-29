from setuptools import setup, find_packages

setup(

    packages=find_packages(where='dcnodatg'),  # Find packages in the 'src' directory
    package_dir={'': 'dcnodatg'},  # Specify the root directory for your source code
    # ... other setup arguments
)
