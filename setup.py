#!/usr/bin/python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

requirements = [
    'pyusb>=1.0.2',
    'numpy',
    'tqdm'
]

setup(
    name='harp-soundcard-server',
    version='0.1',
    description="""Harp Sound card TCP Server""",
    long_description="""TCP Server to interact with the Harp Sound Card board developed by the Scientific Hardware Platform at
    the Champalimaud Foundation.""",
    author='Luís Teixeira',
    author_email='micboucinha@gmail.com',
    license='MIT',
    url='https://github.com/fchampalimaud/soundcard_server/',

    packages=find_packages(exclude=['tests*']),

    install_requires=requirements,
)
