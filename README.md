# trzsz

trzsz is a simple file transfer tools, similar to lrzsz ( rz / sz ) but compatible with tmux.

which works with iTerm2 and has a nice progress bar.

Website: [https://trzsz.github.io](https://trzsz.github.io)

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg?style=flat)](https://choosealicense.com/licenses/mit/)
[![PyPI trzsz](https://img.shields.io/pypi/v/trzsz?style=flat)](https://pypi.python.org/pypi/trzsz/)
[![中文网站](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-%E7%BD%91%E7%AB%99-blue?style=flat)](https://trzsz.github.io/cn/)


## Why?

I love to use [iTerm2 integrating with tmux](https://iterm2.com/documentation-tmux-integration.html) to manage terminal sessions.

Sometimes, I need to transfer some files between my laptop and the remote server.

Considering `laptop -> hostA -> hostB -> docker -> tmux` , using scp to transfer files is inconvenience.

[Tmux](https://github.com/tmux/tmux) is not going to support lrzsz ( rz / sz ) ( [906](https://github.com/tmux/tmux/issues/906), [1439](https://github.com/tmux/tmux/issues/1439) ), and I found out that creating a new file transfer tools is much easier than patching tmux.

Additionally, [iTerm2-zmodem](https://github.com/RobberPhex/iTerm2-zmodem) is not supporting a progress bar. Is there something wrong happened or just need more time?


## Requirements
* [Python](https://www.python.org/)
  * Python’s standard library is good enough.
* [iTerm2](https://iterm2.com/index.html)
  * [Tmux Integration](https://iterm2.com/documentation-tmux-integration.html) and [Coprocesses](https://iterm2.com/documentation-coprocesses.html) are so cool.
  * `btw` without tmux works too.
* [zenity](https://github.com/ncruces/zenity)
  * Optional for a nice progress bar.


## Installation

### Server side

#### Install [trzsz-svr](https://pypi.org/project/trzsz-svr)
  ```
  sudo python3 -m pip install --upgrade trzsz-libs trzsz-svr
  ```
  * Also supports Python2:
    ```
    sudo pip install --upgrade trzsz-libs trzsz-svr
    ```


### Client side

#### Install [trzsz-iterm2](https://pypi.org/project/trzsz-iterm2)
  ```
  sudo python3 -m pip install --upgrade trzsz-libs trzsz-iterm2
  ```
  * Also supports Python2:
    ```
    sudo pip install --upgrade trzsz-libs trzsz-iterm2
    ```
  * After installation, `which trzsz-iterm2` should output `/usr/local/bin/trzsz-iterm2`, if not:
    * `which trzsz-iterm2` shows nothing, check the output of the previous installation.
    * `which trzsz-iterm2` shows another path, create a soft link:\
      `sudo ln -sv $(which trzsz-iterm2) /usr/local/bin/trzsz-iterm2`


#### Install [iTerm2](https://iterm2.com/index.html) and create a [Trigger](https://iterm2.com/documentation-triggers.html) as follows.

  | Name | Value |
  | ---- | ---- |
  | Regular Expression | `:(:TRZSZ:TRANSFER:[SR]:\d+\.\d+\.\d+)` |
  | Action | `Run Silent Coprocess` |
  | Parameters | `/usr/local/bin/trzsz-iterm2 \1` |
  | Enabled | ✅ Checked |
  | Use interpolated strings for parameters | ❎ Unchecked |

  ![iTerm2 Trigger configuration](https://trzsz.github.io/images/config.png)


#### `Optional` install [zenity](https://github.com/ncruces/zenity) for a nice progress bar.
  ```
  brew install ncruces/tap/zenity
  ```
  * After installation, `which zenity` should output `/usr/local/bin/zenity`, if not:
    * `which zenity` shows nothing, check the output of the previous installation.
    * `which zenity` shows another path, create a soft link:\
      `sudo ln -sv $(which zenity) /usr/local/bin/zenity`


## Manual

#### `trz` upload files to remote server
  ```
  usage: trz [-h] [-v] [-q] [-y] [path]

  Receive file(s), similar to rz but compatible with tmux.

  positional arguments:
    path             path to save file(s). (default: current directory)

  optional arguments:
    -h, --help       show this help message and exit
    -v, --version    show program's version number and exit
    -q, --quiet      quiet (hide progress bar)
    -y, --overwrite  overwrite existing file(s)
  ```

#### `tsz` download files from remote server
  ```
  usage: tsz [-h] [-v] [-q] [-y] file [file ...]

  Send file(s), similar to sz but compatible with tmux.

  positional arguments:
    file             file(s) to be sent

  optional arguments:
    -h, --help       show this help message and exit
    -v, --version    show program's version number and exit
    -q, --quiet      quiet (hide progress bar)
    -y, --overwrite  overwrite existing file(s)
  ```

## Screenshot

#### Upload files to remote server

  ![Upload files looks good](https://trzsz.github.io/images/upload.gif)

#### Download files from remote server

  ![Download files looks good](https://trzsz.github.io/images/download.gif)


## Contact

Feel free to email me <lonnywong@qq.com> (same as my PayPal account, just in case you want to deduct🤑).
