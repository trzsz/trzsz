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
  * Can be installed without `sudo`, but need to add the installation path ( may be `~/.local/bin` ) to the PATH environment.
  * `trz -v` or `tsz -v` output the version of trzsz means successfully installed. Otherwise, check the output of the previous installation.


### Client side

#### Install [trzsz-iterm2](https://pypi.org/project/trzsz-iterm2)
  ```
  sudo python3 -m pip install --upgrade trzsz-libs trzsz-iterm2
  ```
  * Also supports Python2:
    ```
    sudo pip install --upgrade trzsz-libs trzsz-iterm2
    ```
  * `which trzsz-iterm2` output `/usr/local/bin/trzsz-iterm2` means successfully installed. if not:
    * `which trzsz-iterm2` shows nothing, check the output of the previous installation.
    * `which trzsz-iterm2` shows another path, create a soft link:\
      `sudo ln -sv $(which trzsz-iterm2) /usr/local/bin/trzsz-iterm2`


#### Install [iTerm2](https://iterm2.com/index.html) and create a [Trigger](https://iterm2.com/documentation-triggers.html) as follows.

  | Name | Value | Note |
  | ---- | ----- | ---- |
  | Regular Expression | <span style="white-space: nowrap;">`:(:TRZSZ:TRANSFER:[SR]:\d+\.\d+\.\d+:\d+)`</span> | <!-- avoid triple click copy a newline --> One line and no space at the end |
  | Action | `Run Silent Coprocess` | |
  | Parameters | <span style="white-space: nowrap;">`/usr/local/bin/trzsz-iterm2 \1`</span> | <!-- avoid triple click copy a newline --> One line and no space at the end |
  | Enabled | ✅ | Checked |
  | Use interpolated strings for parameters | ❎ | Unchecked |

  * iTerm2 Trigger configuration allows input multiple lines, but only shows one line. Make sure don't copy a newline into it.

  ![iTerm2 Trigger configuration](https://trzsz.github.io/images/config.jpg)


#### `Optional` install [zenity](https://github.com/ncruces/zenity) for a nice progress bar.
  ```
  brew install ncruces/tap/zenity
  ```
  * If `Mac M1` install fails, try to install with `go`:
    ```
    brew install go
    go install 'github.com/ncruces/zenity/cmd/zenity@latest'
    sudo cp ~/go/bin/zenity /usr/local/bin/zenity
    ```
  * `which zenity` output `/usr/local/bin/zenity` means successfully installed. if not:
    * `which zenity` shows nothing, check the output of the previous installation.
    * `which zenity` shows another path, create a soft link:\
      `sudo ln -sv $(which zenity) /usr/local/bin/zenity`


## Manual

#### `trz` upload files to remote server
  ```
  usage: trz [-h] [-v] [-q] [-y] [-b] [-e] [-B N] [-t N] [path]

  Receive file(s), similar to rz but compatible with tmux.

  positional arguments:
    path               path to save file(s). (default: current directory)

  optional arguments:
    -h, --help         show this help message and exit
    -v, --version      show program's version number and exit
    -q, --quiet        quiet (hide progress bar)
    -y, --overwrite    yes, overwrite existing file(s)
    -b, --binary       binary transfer mode, faster for binary files
    -e, --escape       escape all known control characters
    -B N, --bufsize N  buffer chunk size ( 1K <= N <= 100M ). (default: 1M)
    -t N, --timeout N  timeout ( N seconds ) for each buffer chunk.
                       N <= 0 means never timeout. (default: 100)
  ```

#### `tsz` download files from remote server
  ```
  usage: tsz [-h] [-v] [-q] [-y] [-b] [-e] [-B N] [-t N] file [file ...]

  Send file(s), similar to sz but compatible with tmux.

  positional arguments:
    file               file(s) to be sent

  optional arguments:
    -h, --help         show this help message and exit
    -v, --version      show program's version number and exit
    -q, --quiet        quiet (hide progress bar)
    -y, --overwrite    yes, overwrite existing file(s)
    -b, --binary       binary transfer mode, faster for binary files
    -e, --escape       escape all known control characters
    -B N, --bufsize N  buffer chunk size ( 1K <= N <= 100M ). (default: 1M)
    -t N, --timeout N  timeout ( N seconds ) for each buffer chunk.
                       N <= 0 means never timeout. (default: 100)
  ```

#### Trouble shooting
* If an error occurs, and `trzsz` is hanging up.
  1. Press `Command + Option + Shift + R` to stop [iTerm2 Coprocesses](https://iterm2.com/documentation-coprocesses.html).
  2. Press `Control + j` to stop `trz` or `tsz` process on the server.

* If `trz -b` binary upload fails, and login to server using `telnet` or `docker exec`.
  1. Try to escape all known control characters, e.g., `trz -eb`.

* If `trz -b` binary upload fails, and the server is using `Python3 < 3.7`.
  1. `Python3 < 3.7` supports base64 mode, just don't use `trz -b`, use `trz` instead.
  2. If you want to use `trz -b` binary upload, upgrade Python3 to above 3.7, or use Python2.

* If `trz -b` or `tsz -b` binary transfer fails, and login to server using `expect`.
  1. Try to `export LC_CTYPE=C` before the `expect` script. e.g.:
    ```
    #!/bin/sh
    export LC_CTYPE=C
    expect -c '
      spawn ssh xxx
      expect "xxx: "
      send "xxx\n"
      interact
    '
    ```

## Screenshot

#### Upload files to remote server

  ![Upload files looks good](https://trzsz.github.io/images/upload.gif)

#### Download files from remote server

  ![Download files looks good](https://trzsz.github.io/images/download.gif)


## Contact

Feel free to email me <lonnywong@qq.com> (same as my PayPal account, just in case you want to deduct🤑).
