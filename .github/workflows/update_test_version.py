#!/usr/bin/env python3

import re
import json
from urllib import request
from distutils.version import StrictVersion

def latest_test_version():
    test_pypi_url = 'https://test.pypi.org/pypi/trzsz/json'
    response = request.urlopen(test_pypi_url).read().decode()
    return max(StrictVersion(s) for s in json.loads(response)['releases'].keys())

def next_test_version():
    latest_version = latest_test_version()
    assert latest_version < StrictVersion('0.3.0')
    if latest_version < StrictVersion('0.2.0'):
        return '0.2.0'
    a, b, c = latest_version.version
    return f'{a}.{b}.{c+1}'

def update_test_version(next_version):
    with open('./trzsz/__version__.py', 'r') as f:
        version_content = f.read()
    version_regex = r'([ \t]*__version__[ \t]*=[ \t]*)[\'"](\d+\.\d+\.\d+)[\'"]'
    version_content = re.sub(version_regex, f'\\1\'{next_version}\'', version_content)
    with open('./trzsz/__version__.py', 'w') as f:
        f.write(version_content)

if __name__ == '__main__':
    next_version = next_test_version()
    print(f'::set-output name=version_number::{next_version}')
    update_test_version(next_version)
