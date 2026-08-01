# Arma 3 音乐包管理器（ArmaMusicPackManager）

将源音频整理为符合 Arma 3 规范的 Ogg 音乐包（专辑目录 + config.cpp）的桌面管理器。

## 功能需求

1. **音频导入与管理** — 导入源音频文件（支持主流格式），集中管理：查看、预览、批量操作
2. **专辑管理** — 创建/编辑专辑（对应 `CfgMusicClasses` 分类与模组子目录），将曲目划入专辑
3. **音频转码** — 按用户设置的转码参数（编码、码率、采样率、声道等）将源音频转码为 Ogg Vorbis，输出到模组目录
4. **config.cpp 自动生成** — 根据专辑与曲目信息自动生成符合 Arma 3 规范的 config.cpp（CfgPatches / CfgMusicClasses / CfgMusic，自动计算 duration）
5. **AI 文件名翻译** — 接入在线 AI API，将英文曲目名翻译为中文显示名（`name` 字段）
6. **UI** — 简洁、紧凑、美观的图形界面

## 参考实现

`demo_files/douzi_SAGA_music/` 是一个完整的 Arma 3 音乐模组范例（=SAGA= 导演任务基础气氛音乐包，作者 豆子Doge），作为管理器输出格式的参考标准。其结构契约见 `CLAUDE.md`：

- config.cpp 三部分：CfgPatches（模组身份）、CfgMusicClasses（专辑分类）、CfgMusic（曲目条目）
- `sound[]` 路径前缀固定为 `douzi\douzi_SAGA_music\`
- 音频统一 Ogg Vorbis / 44100 Hz / 双声道
- 专辑子文件夹、CfgMusicClasses 类、sound[] 路径目录名三者一一对应
