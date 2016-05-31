from setuptools import setup
from os import path, getcwd

if not path.dirname(__file__):  # setup.py without /path/to/
    _dirname = getcwd()  # /path/to/
else:
    _dirname = path.dirname(path.dirname(__file__))


def read(name, default=None, debug=True):
    try:
        filename = path.join(_dirname, name)
        with open(filename) as f:
            return f.read()
    except Exception as e:
        err = "%s: %s" % (type(e), str(e))
        if debug:
            print(err)
        return default


def lines(name):
    txt = read(name)
    return map(
        lambda l: l.lstrip().rstrip(),
        filter(lambda t: not t.startswith('#'), txt.splitlines() if txt else [])
    )


install_requires = [i for i in lines("requirements.txt") if '-e' not in i]

setup(name='generic_crud',
      version='1.0.1',
      author='Om Jangir',
      author_email='omjangir2006@gmail.com',
      description='It create crud tcp apis',
      packages=['generic_crud'], install_requires=install_requires)
