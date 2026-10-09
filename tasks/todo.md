# 人类进步历程视频 — 实施计划

> 设计文档：[docs/superpowers/specs/2026-10-09-human-progress-video-design.md](../docs/superpowers/specs/2026-10-09-human-progress-video-design.md)
> 执行方式：本会话内联执行（TDD），每个任务完成后勾选并提交。

**目标：** 一条命令生成约 180 秒的横屏、竖屏两个 MP4（中文配音 + 中英双语字幕 + 铺底音）。

**架构：** 旁白稿 → 逐句 TTS（带缓存）→ 时间线 JSON → 同一份时间线驱动音频混音、SRT 和两套布局的逐帧渲染 → FFmpeg 编码。两个版本共用一份时间线，从机制上保证时长一致、字幕和配音同步。

**技术栈：** Python 3.13、Pillow 12.3.0、NumPy 2.5.3、edge-tts 7.2.8、pytest 9.1.1、FFmpeg 9.0。

运行约定：所有命令在仓库根目录执行，Python 用 `.venv/Scripts/python`。

## 文件职责

| 文件 | 职责 |
|------|------|
| `scripts/human-progress.md` | 旁白稿：每段编号、标题、年代、年份、目标时长、“中文 \| English”句子 |
| `storyboards/human-progress.md` | 分镜：每段的画面元素与动画 |
| `tools/human_progress/script.py` | 解析旁白稿 → `Section` 列表 |
| `tools/human_progress/narration.py` | 逐句 TTS（edge-tts / 离线备选）→ 48kHz 单声道 WAV，按内容哈希缓存 |
| `tools/human_progress/timeline.py` | 由每句时长排出 `Timeline`（段落起止、字幕 Cue），对数时间轴映射 |
| `tools/human_progress/audio.py` | WAV 读写、旁白摆放、铺底音合成、混音（铺底音 -18dB） |
| `tools/human_progress/subtitles.py` | 导出双语 SRT |
| `tools/human_progress/layout.py` | 横屏 / 竖屏布局参数 |
| `tools/human_progress/draw.py` | 画布（numpy 发光 + Pillow 形状/文字）、文字换行、缓动、虚线 |
| `tools/human_progress/scenes.py` | S01–S12 主画面绘制函数 |
| `tools/human_progress/frame.py` | 合成一帧：背景 + 主画面 + 标题 + 时间轴 + 字幕 |
| `tools/human_progress/render.py` | 多进程逐帧渲染 → FFmpeg 管道编码；关键帧导出；ffprobe 时长 |
| `tools/human_progress/build.py` | 一键串联全流程（`--keyframes`、`--offline`） |
| `tests/human_progress/test_*.py` | 各模块单元测试 |

## 与设计文档的差异

- 离线备选语音改用 Windows 自带的 System.Speech（通过 PowerShell 调用），不引入 pyttsx3 依赖。
- 字幕用 Pillow 直接画进画面（效果等同烧录），不用 FFmpeg 的 subtitles 滤镜：避开 Windows 路径转义问题，也便于分别控制横竖屏排版。SRT 仍单独导出。
- 段落留白：段首 1.2s、句间 0.8s、段尾 2.2s（配音已裁掉首尾静音），给画面留出呼吸感。

## 任务

### Task 1：环境
- [ ] 创建 `requirements.txt`（固定版本）、`pytest.ini`（`pythonpath = .`）、`tools/__init__.py`、`tools/human_progress/__init__.py`
- [ ] `python -m venv .venv` 并安装依赖
- [ ] 验证：`.venv/Scripts/python -c "import edge_tts, PIL, numpy"` 无报错
- [ ] 提交

### Task 2：旁白稿与分镜
- [ ] 写 `scripts/human-progress.md`：12 段，格式如下；中文按约 4 字/秒控制在目标时长内；S11 用推测语气
- [ ] 写 `storyboards/human-progress.md`：每段的主画面、动画、配色
- [ ] 提交

```
## S02 石器 | Stone Tools
- era: 约 330 万年前 | ~3.3 million years ago
- year: -3300000
- target: 12
- speculative: false

中文句子。 | English sentence.
```

### Task 3：旁白稿解析 `script.py`（TDD）
接口：`Line(zh, en)`、`Section(id, title_zh, title_en, era_zh, era_en, year: float|None, target: float, speculative: bool, lines: tuple[Line,...])`、`parse_script(text) -> list[Section]`、`load_script(path)`
- [ ] 测试：解析两段样例的字段和句子；句子缺少 ` | ` 时抛出 `ValueError` 并带行号；真实旁白稿解析出 12 段，目标时长合计 180
- [ ] 实现 → 测试通过 → 提交

### Task 4：时间线 `timeline.py`（TDD）
接口：`Cue(start, end, zh, en)`、`Span(section, start, end)`、`Timeline(spans, cues, duration)`、`build_timeline(sections, durations: dict[tuple[str,int], float]) -> Timeline`、`Timeline.span_at(t)`、`year_to_axis(year) -> float`（-3,300,000 → 0.0，2056 → 1.0，单调递增）、`save_timeline` / `load_timeline`（JSON 往返）
另有 `duration_warnings(timeline) -> list[str]`：某段实际时长偏离目标超过 50% 时返回警告（build 时打印）
- [ ] 测试：留白规则下每段起止与 Cue 时间正确；总时长；`span_at` 边界；`year_to_axis` 端点和单调性；JSON 往返一致；偏离 60% 的段落产生警告，偏离 10% 的不产生
- [ ] 实现 → 测试通过 → 提交

### Task 5：字幕 `subtitles.py`（TDD）
接口：`format_ts(seconds) -> "HH:MM:SS,mmm"`、`to_srt(cues) -> str`（每条两行：中文、英文）
- [ ] 测试：`format_ts(3661.5) == "01:01:01,500"`；两条 Cue 的 SRT 完整文本
- [ ] 实现 → 测试通过 → 提交

### Task 6：音频 `audio.py`（TDD）
接口：`SR = 48000`、`read_wav` / `write_wav`（float32 单声道）、`place_narration(timeline, clips: dict[key, np.ndarray]) -> np.ndarray`、`ambient(duration, seed=7) -> np.ndarray`、`mix(narration, bed, bed_db=-18.0) -> np.ndarray`（峰值限制在 0.98）
- [ ] 测试：旁白片段落在 Cue 起点的采样位置；总长度 = 时长 × SR；`ambient` 长度正确且结果可复现；`mix` 峰值 ≤ 0.98；WAV 往返
- [ ] 实现 → 测试通过 → 提交

### Task 7：配音 `narration.py`（TDD，网络部分手动验证）
接口：`cache_key(text, voice, rate) -> str`、`synthesize(sections, cache_dir, voice="zh-CN-YunxiNeural", rate="+0%", offline=False) -> dict[key, Path]`（edge-tts 输出 mp3 → FFmpeg 转 48kHz 单声道 WAV；失败重试 3 次；`offline=True` 时调用 System.Speech）、`clip_duration(path) -> float`
- [ ] 测试：`cache_key` 稳定，文本或语音不同则结果不同；缓存命中时不调用合成函数（注入假合成函数）
- [ ] 实现 → 测试通过
- [ ] 手动验证：合成一句真实语音并试听时长
- [ ] 提交

### Task 8：布局与绘图 `layout.py` + `draw.py`（TDD）
接口：`Layout(name, w, h, stage_cx, stage_cy, unit, title_y, title_zh_size, title_en_size, axis_y, axis_x0, axis_x1, sub_y, sub_zh_size, sub_en_size, sub_max_w)`、`LANDSCAPE`、`PORTRAIT`；`ease(x)`、`fade(t, start, dur)`、`add_glow(arr, cx, cy, r, color, strength)`（只计算 3r 包围盒）、`wrap_text(text, font, max_w) -> list[str]`（中文按字、英文按词）、`font(size, bold=False)`（带缓存）
- [ ] 测试：两套布局元素都在画面内且不重叠；`ease` / `fade` 的端点；`add_glow` 只改动包围盒内像素；`wrap_text` 每行宽度 ≤ max_w，拼回去等于原文
- [ ] 实现 → 测试通过 → 提交

### Task 9：场景与单帧合成 `scenes.py` + `frame.py`（TDD + 关键帧目检）
接口：`SCENES: dict[str, Callable[[Ctx], None]]`，`Ctx(img, draw, light, layout, t, dur, p)`（`p` = 段内进度 0–1）；`render_frame(timeline, layout, t) -> np.ndarray[h, w, 3] uint8`
- 每帧组成：深色背景（亮度随历史推进逐渐提高）→ 主画面 → 段落标题（年代 + 中英标题）→ 底部对数时间轴（已经过的节点点亮，当前节点发光；未来段为虚线）→ 双语字幕；段落切换时 0.5s 淡入淡出
- [ ] 测试：12 个 id 都有对应场景；两套布局在每段的开头、中间、结尾渲染出尺寸正确的帧，且画面不是全黑
- [ ] 实现 S01–S12
- [ ] 导出关键帧并目检排版（文字不越界、不被字幕遮挡），有问题就修
- [ ] 提交

### Task 10：渲染与一键构建 `render.py` + `build.py`
接口：`render_video(timeline, layout, audio_path, out_path, fps=30, workers=os.cpu_count())`（多进程逐帧 → FFmpeg rawvideo 管道，libx264 CRF 20 + AAC 192k）、`export_keyframes(timeline, layout, out_dir)`、`probe_duration(path)`；`python -m tools.human_progress.build [--keyframes] [--offline] [--only landscape|portrait]`
- [ ] 测试：用 2 秒的假时间线渲染出 MP4，ffprobe 得到的时长约为 2 秒，分辨率正确
- [ ] 实现 → 测试通过 → 提交

### Task 11：完整构建与验证
- [ ] 运行完整构建，生成两个 MP4、WAV 和 SRT
- [ ] ffprobe：两个版本时长差 ≤ 0.1 秒，分辨率分别为 1920×1080 和 1080×1920
- [ ] 抽查字幕和配音同步（≤ 0.3 秒）：比对 Cue 时间和旁白片段位置；抽 5 个字幕切换点截帧核对
- [ ] 按时间点逐段抽帧，把两个成片完整过一遍
- [ ] 在本文件末尾写“审查”小节：结果、已知问题
- [ ] 更新 `CLAUDE.md` 的常用命令，提交并推送
