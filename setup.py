from setuptools import setup


def readme():
    with open('README.md') as f:
        return f.read()


setup(name='anthill_tools',
      version='0.1.1',
      description='Tool set to communicate with anthill platform',
      long_description=readme(),
      url='https://github.com/anthill-platform/anthill-tools',
      author='desertkun',
      author_email='desertkun@gmail.com',
      license='MIT',
      packages=['anthill_tools', 'anthill_tools.admin', 'anthill_tools.admin.dlc', 'anthill_tools.admin.game'],
      zip_safe=False,
      install_requires=['requests'])
