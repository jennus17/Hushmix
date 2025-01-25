from setuptools import setup, find_packages

setup(
    name="hushmix",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pycaw==20181226',
        'comtypes==1.2.0',
        'pyserial==3.5',
        'psutil==5.9.5',
        'pystray==0.19.4',
        'Pillow==10.0.0',
        'pywin32==306',
    ],
    entry_points={
        'console_scripts': [
            'hushmix=src.main:main',
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A volume control application for Windows",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    keywords="volume control, audio, windows",
    url="https://github.com/yourusername/hushmix",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires='>=3.7',
) 