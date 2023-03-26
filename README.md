# trzsz

`trzsz` ( trz / tsz ) is a simple file transfer tools, similar to `lrzsz` ( rz / sz ), and compatible with `tmux`.

Website: [https://trzsz.github.io](https://trzsz.github.io)

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg?style=flat)](https://choosealicense.com/licenses/mit/)
[![PyPI trzsz](https://img.shields.io/pypi/v/trzsz?style=flat)](https://pypi.python.org/pypi/trzsz/)
[![中文网站](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-%E7%BD%91%E7%AB%99-blue?style=flat)](https://trzsz.github.io/cn/)


## Why?

Considering `laptop -> hostA -> hostB -> docker -> tmux`, using `scp` or `sftp` is inconvenience.

In this case, `lrzsz` ( rz / sz ) is convenient to use, but unfortunately it's not compatible with `tmux`.

`tmux` is not going to support rz / sz ( [906](https://github.com/tmux/tmux/issues/906), [1439](https://github.com/tmux/tmux/issues/1439) ), and creating a new tools is much easier than patching `tmux`.


## Advantage

* Support **tmux**, including tmux normal mode, and tmux command mode integrated with iTerm2.
* Support **transfer directories**, `trz -d` to upload directories, `tsz -d xxx` to download xxx directories.
* Support **Windows server**, not only can run on Windows client, but also can run on Windows ssh server.
* Support **native terminal**, does not require terminal to support, just use `trzsz ssh x.x.x.x` to login.
* Support **web terminal**, transfer files and directories between local and remote servers over the web.
* Support **drag to upload**, drag and drop files and directories to the terminal to upload to the remote server.
* Support **progress bar**, shows the current transferring file name, progress, size, speed, remaining time, etc.
* Better **interactive experience**, shows the transfer results or errors friendly, `ctrl + c` to stop gracefully.


## Installation

### On the server

* with Python3
  ```
  sudo python3 -m pip install --upgrade trzsz
  ```

* with Python2
  ```
  sudo python2 -m pip install --upgrade trzsz
  ```

* with Homebrew
  ```
  brew update
  brew install trzsz
  ```

* with Node.js
  ```
  sudo npm install -g trzsz
  ```

* or install trzsz written in Go

  Check [https://github.com/trzsz/trzsz-go](https://github.com/trzsz/trzsz-go)


&nbsp;&nbsp;Can be installed without `sudo`, just add the installation path ( e.g. `~/.local/bin` ) to the `PATH` environment.


### Supported Terminals

* [iTerm2](https://iterm2.com/) -- check [the trzsz-iterm2 installation](https://trzsz.github.io/iterm2).

* [tabby](https://tabby.sh/) -- install the [tabby-trzsz](https://github.com/trzsz/tabby-trzsz) plugin.

* [electerm](https://electerm.github.io/electerm/) -- upgrade to `1.19.0` or higher.

* [ttyd](https://github.com/tsl0922/ttyd) -- upgrade to `1.7.3` or higher, and start with `-t enableTrzsz=true`, use `https` unless localhost.

* [trzsz-go](https://github.com/trzsz/trzsz-go) -- supports all terminals that support a local shell.

* [trzsz.js](https://github.com/trzsz/trzsz.js) -- making webshell in browser and electron terminal supports `trzsz`.

&nbsp;&nbsp;*Does your terminal supports `trzsz` as well? Please let me know. I would love to have it on the list.*


## Trzsz Manual

#### `trz` upload files to the remote server
  ```
  usage: trz [-h] [-v] [-q] [-y] [-b] [-e] [-d] [-B N] [-t N] [path]

  Receive file(s), similar to rz and compatible with tmux.

  positional arguments:
    path               path to save file(s). (default: current directory)

  optional arguments:
    -h, --help         show this help message and exit
    -v, --version      show program's version number and exit
    -q, --quiet        quiet (hide progress bar)
    -y, --overwrite    yes, overwrite existing file(s)
    -b, --binary       binary transfer mode, faster for binary files
    -e, --escape       escape all known control characters
    -d, --directory    transfer directories and files
    -B N, --bufsize N  max buffer chunk size (1K<=N<=1G). (default: 10M)
    -t N, --timeout N  timeout ( N seconds ) for each buffer chunk.
                       N <= 0 means never timeout. (default: 20)
  ```

#### `tsz` download files from the remote server
  ```
  usage: tsz [-h] [-v] [-q] [-y] [-b] [-e] [-d] [-B N] [-t N] file [file ...]

  Send file(s), similar to sz and compatible with tmux.

  positional arguments:
    file               file(s) to be sent

  optional arguments:
    -h, --help         show this help message and exit
    -v, --version      show program's version number and exit
    -q, --quiet        quiet (hide progress bar)
    -y, --overwrite    yes, overwrite existing file(s)
    -b, --binary       binary transfer mode, faster for binary files
    -e, --escape       escape all known control characters
    -d, --directory    transfer directories and files
    -B N, --bufsize N  max buffer chunk size (1K<=N<=1G). (default: 10M)
    -t N, --timeout N  timeout ( N seconds ) for each buffer chunk.
                       N <= 0 means never timeout. (default: 20)
  ```

#### Trouble shooting
* If `tmux` is not running on the remote server, but on the local computer, or on a middle server.
  * Option 1: Use `tmux -CC` integration with iTerm2, please refer to [iTerm2 tmux Integration](https://trzsz.github.io/tmuxcc).
  * Option 2: Install [trzsz-go](https://github.com/trzsz/trzsz-go) on the local computer, and `alias ssh="trzsz ssh"` for convenience.

* If an error occurs, and `trzsz` is hanging up.
  * Press `control + c` to stop `trz` or `tsz` process on the server.
  * For iTerm2 users, press `command + option + shift + r` to stop [iTerm2 Coprocesses](https://iterm2.com/documentation-coprocesses.html).

* If `trz -b` binary upload fails, and login to server using `telnet` or `docker exec`.
  * Try to escape all known control characters, e.g., `trz -eb`.

* If `trz -b` or `tsz -b` binary transfer fails, and login to server using `expect`.
  * Try to `export LC_CTYPE=C` before the `expect` script. e.g.:
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

#### Using trzsz in iTerm2 with `text` progress bar

  ![using trzsz in iTerm2 with text progress bar](https://trzsz.github.io/images/iterm2_text.gif)


#### Using trzsz in iTerm2 with `zenity` progress bar

  ![using trzsz in iTerm2 with zenity progress bar](https://trzsz.github.io/images/iterm2_zenity.gif)


#### Using trzsz in tabby with `tabby-trzsz` plugin

  ![using trzsz in tabby with tabby-trzsz plugin](https://trzsz.github.io/images/tabby_trzsz.gif)


## Contact

Feel free to email me <lonnywong@qq.com>.
