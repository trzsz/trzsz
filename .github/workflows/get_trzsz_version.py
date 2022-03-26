#!/usr/bin/env python3

exec(open('trzsz/__version__.py').read())

if __name__ == '__main__':
    print(f'::set-output name=version_number::{__version__}')
