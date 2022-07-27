from setuptools import setup, find_packages

setup(
    name='clingopt',
    version='0.0.1',
    description='clingOPT extends the solver clingo with optimisation theories over reals.',
    url='https://github.com/kthuillier/MERRIN_Generic',
    author='Kerian Thuillier',
    author_email='kerian.thuillier@irisa.fr',
    license='MIT',
    include_package_data=True,
    package_dir={'clingopt': 'src'},
    packages=['clingopt', 'clingopt.theory', 'clingopt.theory.solvers'],
    install_requires=[
        'pulp',
        'clingo',
    ],
    test_suite='nose.collector',
    tests_require=['nose'],
    zip_safe=False,
    entry_points={
        'console_scripts': ['clingopt=clingopt.app:clingopt_main'],
    }
)