# trzsz-iterm2

`trzsz` ( trz / tsz ) is a simple file transfer tools, similar to `lrzsz` ( rz / sz ), and compatible with `tmux`.

`trzsz-iterm2` is a client tool for [trzsz](https://trzsz.github.io/) used with [iTerm2](https://iterm2.com/).

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg?style=flat)](https://choosealicense.com/licenses/mit/)
[![PyPI trzsz-iterm2](https://img.shields.io/pypi/v/trzsz-iterm2?style=flat)](https://pypi.python.org/pypi/trzsz-iterm2/)
[![中文网站](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-%E7%BD%91%E7%AB%99-blue?style=flat)](https://trzsz.github.io/cn/iterm2)


## Installation

* With Python3
  ```
  sudo python3 -m pip install --upgrade trzsz-iterm2
  ```

* With Homebrew
  ```
  brew update
  brew install trzsz
  ```

## Configuration

* Find out the absolute path where `trzsz-iterm2` is installed.
  ```sh
  which trzsz-iterm2
  ```
  Change the `/usr/local/bin/trzsz-iterm2` below to the real absolute path of `trzsz-iterm2`.

* Open `iTerm2 -> Preferences... / Settings... -> Profiles -> (select a profile on the left) -> Advanced -> Triggers -> Edit -> [+]`

  | Name | Value | Note |
  | ---- | ----- | ---- |
  | Regular Expression | `:(:TRZSZ:TRANSFER:[SRD]:\d+\.\d+\.\d+:\d+)` | <!-- avoid triple click copy a newline --> No space at the end |
  | Action | `Run Silent Coprocess...` | |
  | Parameters | `/usr/local/bin/trzsz-iterm2 \1` | <!-- avoid triple click copy a newline --> No space at the end |
  | Enabled | ✅ | Checked |

  * Don't check the `Use interpolated strings for parameters` at the bottom.

  * The `/usr/local/bin/trzsz-iterm2` should be changed to the real absolute path of `trzsz-iterm2`.

  * Note that the `Triggers` should be configured for each `Profile` in use.

  * `Triggers` allows multiple lines, but only shows one line. Make sure don't copy a newline into it.

  ![iTerm2 Trigger configuration](https://trzsz.github.io/images/config.jpg)

* Open `iTerm2 -> Preferences... / Settings... -> General -> Magic`, check `Enable Python API`.

  ![iTerm2 Enable Python API](https://trzsz.github.io/images/PythonAPI.png)

* Set `ITERM2_COOKIE` environment variable for faster startup.

  Open `iTerm2 -> Preferences... / Settings... -> Advanced`, filter by `COOKIE`, select `Yes`.

  ![iTerm2 Enable ITERM2_COOKIE](https://trzsz.github.io/images/iterm2_cookie.png)


## Progress Bar

### Option 1: The cooler text progress bar

* Screenshot of text progress bar
  ![using trzsz in iTerm2 with text progress bar](https://trzsz.github.io/images/iterm2_text.gif)

* Upgrade iTerm2 to `Build 3.5.20220503-nightly` or higher.

* Add `-p text` to the parameters of iTerm2 `Trigger`.
  ```
  /usr/local/bin/trzsz-iterm2 -p text \1
  ```
  Don't forget to change `/usr/local/bin/trzsz-iterm2` to the real absolute path of `trzsz-iterm2`.

### Option 2: The [zenity](https://github.com/ncruces/zenity) progress bar

* Screenshot of zenity progress bar
  ![using trzsz in iTerm2 with zenity progress bar](https://trzsz.github.io/images/iterm2_zenity.gif)

* Install `zenity`
  ```sh
  brew install ncruces/tap/zenity
  ```

* If `Mac M1` install fails, try to install it with `go`:
  ```sh
  brew install go
  go install 'github.com/ncruces/zenity/cmd/zenity@latest'
  sudo cp ~/go/bin/zenity /usr/local/bin/zenity
  ```

* `ls -l /usr/local/bin/zenity` should shows the `zenity` executable file or link. If not, create a soft link:
  ```sh
  sudo ln -sv $(which zenity) /usr/local/bin/zenity
  ```

* If the progress dialog doesn't pop up in front, try upgrade [zenity](https://github.com/ncruces/zenity), and don't check `iTerm2 -> Secure Keyboard Entry`.


## Default save path

If you want to automatically download files to the specified directory instead of asking each time.

e.g.: Automatically download files to `/Users/xxxxx/Downloads`

* Using text progress bar, change `/usr/local/bin/trzsz-iterm2 -p text \1` to:
  ```
  /usr/local/bin/trzsz-iterm2 -p text -d '/Users/xxxxx/Downloads' \1
  ```

* Using zenity progress bar, change `/usr/local/bin/trzsz-iterm2 \1` to:
  ```
  /usr/local/bin/trzsz-iterm2 -p zenity -d '/Users/xxxxx/Downloads' \1
  ```

Don't forget to change `/usr/local/bin/trzsz-iterm2` to the real absolute path of `trzsz-iterm2`.


## Dragging files and directories to upload

* Upgrade iTerm2 to `Build 3.5.20220806-nightly` or higher.

* Open `iTerm2 -> Preferences... / Settings... -> Advanced`, filter by `files are dropped into`, configure as:
  ```
  /usr/local/bin/trzsz-iterm2 -p text dragfiles \(filenames)
  ```

  ![iTerm2 enable drag files](https://trzsz.github.io/images/drag_config.png)

Don't forget to change `/usr/local/bin/trzsz-iterm2` to the real absolute path of `trzsz-iterm2`.
