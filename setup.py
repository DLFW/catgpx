#!/usr/bin/env python
# -*- coding: utf-8 -*-
#head#

"""
@author: Daniel Llin Ferrero
"""


from distutils.core import setup


setup(
        name='catgpx',
        version='0.0.1',
        description='Python script to process GPX tracks',
        author='DLF',
        package_dir={'': 'src'},
        packages=['catgpx', 'catgpx.test'],
        package_data={'catgpx.test': ['track.gpx']},
        scripts=['scripts/catgpx.py'],
        requires=['gpxpy', 'piexif'],
        license='GPL 3  (http://www.gnu.org/licenses/gpl-3.0)',
        classifiers=[
                'Environment :: Console',
        ],
)
