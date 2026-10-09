# Story — AI 视频创作项目

用 AI 工具生成、剪辑短视频。Git 只管理文本类资产（脚本、分镜、提示词、工作流、配置），成片与大素材不入库。

## 目录约定

```
Story/
├── scripts/      # 故事脚本、旁白稿
├── storyboards/  # 分镜（每镜头：画面描述、时长、运镜、对白）
├── prompts/      # 各平台提示词，按镜头编号命名，如 S01-C03.md
├── workflows/    # ComfyUI 工作流 JSON
├── tools/        # 自动化脚本（FFmpeg 批处理、API 调用）
├── assets/       # 参考图、角色设定图（小文件；大文件放网盘）
└── output/       # 渲染输出，已被 .gitignore 排除
```

## 工具链

| 工具 | 用途 | Claude 可以做什么 | 状态 |
|------|------|------------------|------|
| FFmpeg | 拼接、转码、裁切、加字幕、混音 | 直接执行命令和脚本 | 已安装（9.0） |
| 可灵 Kling | 文生视频 / 图生视频 | 写提示词；有 API Key 时可写脚本调用 API | 云端，需账号 |
| Runway | 文生视频 / 图生视频、视频编辑 | 写提示词；有 API Key 时可写脚本调用 API | 云端，需账号 |
| ComfyUI | 本地图像/视频生成工作流 | 编辑工作流 JSON；服务运行时通过其 HTTP API 提交任务 | 可选；本机未检测到 NVIDIA GPU，需显卡或云端 GPU |
| 剪映 | 人工精剪、模板、字幕 | 无官方 API，只能整理剪辑清单和字幕文件（SRT）供手动导入 | 手动使用 |

## 约定

- API Key 只放 `.env`（已被 .gitignore 排除），模板见 `.env.example`；不要把密钥写进代码或提示词文件。
- 镜头统一编号 `S<场>-C<镜头>`，脚本、分镜、提示词、输出文件名保持一致，方便对照。
- 记录每个成功镜头的平台、模型版本、提示词和参数（seed 等），便于复现。
- 成片与原始素材存网盘/对象存储，不提交到 Git（GitHub 单文件上限 100MB）。

## 常用命令

```bash
# 按列表拼接片段（list.txt 每行：file 'xxx.mp4'）
ffmpeg -f concat -safe 0 -i list.txt -c copy output/merged.mp4

# 烧录字幕
ffmpeg -i input.mp4 -vf subtitles=subs.srt -c:a copy output/subbed.mp4

# 转竖屏 1080x1920（居中裁切）
ffmpeg -i input.mp4 -vf "scale=-2:1920,crop=1080:1920" -c:a copy output/vertical.mp4
```
