# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库概况

这是一个**内容/数据仓库，不是软件项目**：目前没有源代码、解决方案文件、构建系统、测试或 lint 配置。工作目录中没有任何可运行的开发命令。git 仓库尚无任何提交（`master` 分支为空）。

仓库内容仅有一个 Arma 3 模组的完整参考实现，位于 `demo_files/douzi_SAGA_music/`。尽管目录在 `VS_Projects` 下，这里没有 Visual Studio 项目。

**写入约束：** 所有文件写入操作（创建、编辑、覆盖）仅限本仓库文件夹内，严禁写入仓库以外的任何区域（Claude 自身的记忆系统除外）。

## 仓库内容：Arma 3 音乐模组

`demo_files/douzi_SAGA_music/` 是一个 Arma 3 音乐模组（"=SAGA= 导演任务基础气氛音乐包"，作者 豆子Doge），是计划实现的 Arma 3 音乐包管理器（ArmaMusicPackManager）的参考标准。项目功能需求见 `README.md`（音频导入、专辑管理、转码 Ogg Vorbis、config.cpp 自动生成、AI 文件名翻译、UI）；当前仓库尚无实现代码。

### 目录布局

- `config.cpp` — 唯一的"源码"文件，所有模组元数据都在这里
- `Battlefield4/`、`MedalOfHonor2010/`、`MedalOfHonorWarfighter/`、`ChinaMilSongBundle1/` — 各专辑的 .ogg 文件
- `music/` — 通用（无专辑归属）曲目

### config.cpp 架构

config.cpp 包含三个顶层配置类（Arma 3 配置格式，类 + 花括号，字符串用双引号）：

1. **CfgPatches** — 模组身份与依赖。类名 `douzi_SAGA_music` 必须与包含该 config 的文件夹名一致（Arma 3 的硬性要求）。`requiredAddons[]` 声明依赖 `A3_Data_F`（Arma 3 核心）。
2. **CfgMusicClasses** — 游戏内音乐列表中的专辑分组。`displayname` 是中文显示名（如 `专辑-战地风云4`），出现在玩家 UI 中。每个 CfgMusic 条目的 `musicClass` 必须引用这里的类。
3. **CfgMusic** — 实际曲目条目，每条包含：
   - `name` — 显示名，通常带 `NN-` 前缀编号；英文曲目用英文名，中国军歌用中文名
   - `sound[]` — `{"douzi\douzi_SAGA_music\<专辑>\<文件>.ogg", 1.0, 1.0}`，后两个值是音量和音高（几乎恒为 1.0）
   - `duration` — 秒数（浮点）
   - `musicClass` — 指向 CfgMusicClasses 中的类

### 必须保持的约定

- `sound[]` 路径前缀固定为 `douzi\douzi_SAGA_music\`（config 中路径用反斜杠），对应模组文件夹结构
- 曲目类名（config 类标识符）命名模式：`douzi_<前缀>_Track_NN`（前缀：`BF4`、`MOH2010`、`MOHWF`、`Generic`）或 `douzi_CN_Mil_Song_N`
- 新增 CfgMusic 条目时若引用新专辑，必须在 CfgMusicClasses 中同步新增对应类，否则游戏会拒绝加载模组
- 专辑子文件夹、CfgMusicClasses 类、sound[] 路径中的目录名三者一一对应
- 部分文件名含撇号（如 `Jin_Jie's_Revolution.ogg`、`Dunn's_Down.ogg`、`Saa'iq.ogg`）— 在 `sound[]` 和 `name` 中原样保留，不要改写

### 音频编码约定

所有 .ogg 文件统一为 **Ogg 容器 + Vorbis 编码、44100 Hz、双声道（stereo）**。用 ffprobe 验证：

```bash
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bit_rate \
  -show_entries format=bit_rate -of default=noprint_wrappers=1 <文件.ogg>
```

实测比特率分布（按专辑）：

- `Battlefield4/`、`MedalOfHonor2010/`、`MedalOfHonorWarfighter/` — 128 kbps（统一）
- `ChinaMilSongBundle1/` — 96 kbps（统一，与 OST 专辑不同）
- `music/`（通用）— 不统一，实测混合 128 / 112 kbps

新增曲目时：编码必须是 Vorbis（Arma 3 只可靠支持 Ogg Vorbis），采样率/声道与现有文件保持一致；专辑类曲目沿用该专辑的既有比特率。

## 命令

无构建、lint、测试命令可运行。开发工作流即直接编辑 `config.cpp`、增删 .ogg 文件。在游戏内验证需要 Arma 3 模组打包工具（如 Arma 3 Tools 的 Addon Builder），此类工具不属于本仓库，不假定已安装。
