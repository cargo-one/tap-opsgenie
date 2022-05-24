#!/usr/bin/env python

from setuptools import setup

setup(name='tap-opsgenie',
      version='0.0.1',
      description='Singer.io tap for extracting data from the OpsGenie API',
      author='cargo.one',
      url='https://cargo.one',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_opsgenie'],
      install_requires=[
            'singer-python==5.12.2',
            'requests==2.27.1',
            'strict-rfc3339',
            'pendulum==2.1.2'
      ],
      entry_points='''
          [console_scripts]
          tap-opsgenie=tap_opsgenie:main
      ''',
      packages=['tap_opsgenie'],
      package_data = {
          'tap_opsgenie/schemas': [
            "alerts.json",
          ],
      },
      include_package_data=True,
)