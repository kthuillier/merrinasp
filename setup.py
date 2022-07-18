from setuptools import setup

setup(
    name='clingopt',
    version='0.0.1',
    description='clingOPT extends the solver clingo with optimisation theories over reals.',
    url='https://github.com/kthuillier/MERRIN_Generic',
    author='Kerian Thuillier',
    author_email='kerian.thuillier@irisa.fr',
    license='?',
    packages=['clingopt'],
    package_dir={'clingopt': 'src'},
    install_requires=[
        'pulp',
        'clingo',
    ],
    test_suite='nose.collector',
    tests_require=['nose'],
    include_package_data=True,
    zip_safe=False,
)

