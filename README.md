# trzsz
A simple file transfer tools, similar to rz/sz but compatible with tmux (control mode), which works with iTerm2 and has a nice progress bar.


## Why?

I love to use [iTerm2 integrating with tmux](https://iterm2.com/documentation-tmux-integration.html) to manage terminal sessions.

Sometimes, I need to transfer some files between my laptop and the remote server.

Considering `laptop --> hostA --> hostB --> docker --> tmux ` , using scp to transfer files is inconvenience.

[Tmux](https://github.com/tmux/tmux) is not going to support rz/sz ( [906](https://github.com/tmux/tmux/issues/906), [1439](https://github.com/tmux/tmux/issues/1439) ), and I found out that creating a new file transfer tools is much easier than patching tmux.

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

* Install [trzsz-svr](https://pypi.org/project/trzsz-svr)
  * `python3 -m pip install --upgrade trzsz-svr`


### Client side

* Install [trzsz-iterm2](https://pypi.org/project/trzsz-iterm2)
  * `python3 -m pip install --upgrade trzsz-iterm2`

* Install [iTerm2](https://iterm2.com/index.html) and create a [Trigger](https://iterm2.com/documentation-triggers.html) as follows.

  | Name | Value |
  | ---- | ---- |
  | Regular Expression | `:(:TRZSZ:TRANSFER:[SR]:\d+\.\d+\.\d+)` |
  | Actions | `Run Silent Coprocess` |
  | Parameters | `/usr/local/bin/trzsz-iterm2 \1` |
  | Enabled | ✅ |

  ![](https://github.com/lonnywong/trzsz/blob/main/screen-shot/config.png?raw=true)
    

* `Optional` install [zenity](https://github.com/ncruces/zenity) for a nice progress bar.
  * should be placed at `/usr/local/bin/zenity`


## Manual

* `trz` upload files to remote server
  ```
  usage: trz [-h] [-v] [path]

  Receive file(s), similar to rz but compatible with tmux (control mode).

  positional arguments:
    path           Path to save file(s). (default: current directory)

  optional arguments:
    -h, --help     show this help message and exit
    -v, --version  show program's version number and exit
  ```

* `tsz` download files from remote server
  ```
  usage: tsz [-h] [-v] file [file ...]

  Send file(s), similar to sz but compatible with tmux (control mode).

  positional arguments:
    file           File(s) to be sent.

  optional arguments:
    -h, --help     show this help message and exit
    -v, --version  show program's version number and exit
  ```

## Screenshot

* Upload files to remote server.

  ![](https://github.com/lonnywong/trzsz/blob/main/screen-shot/upload.gif?raw=true)
  
* Download files from remote server.

  ![](https://github.com/lonnywong/trzsz/blob/main/screen-shot/download.gif?raw=true)


## Contact

Feel free to email me <lonnywong@qq.com> (same as my PayPal account, just in case you want to deduct🤑).
