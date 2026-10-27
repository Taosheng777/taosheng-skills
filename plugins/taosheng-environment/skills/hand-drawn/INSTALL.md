# 本地使用与检查

将本技能完整保存到当前 Codex 可发现的 skills/hand-drawn 目录。入口为 [SKILL.md](SKILL.md)。更新前保存可回滚副本，保留用户改动；不自动覆盖其他工具的技能。

```sh
python3 -B scripts/check_skill.py
python3 -B scripts/render_prompt.py --list
python3 -B scripts/run_video.py --help
```

前两项检查配方和参考文件，不产生图片费用。视频环境由项目传入，见 [本地引擎](references/本地引擎.md)，安装技能不等于已安装渲染依赖。

已有参考缓存时，通过 `HAND_DRAWN_IMAGE_CACHE` 指向当前主机实际缓存目录，`HAND_DRAWN_OFFLINE=1` 可验证离线调用。上游图床不可用不应反复下载或擅自换相似参考图；先查本地缓存并按清单校验哈希。不要把设备缓存路径写进可移植包。

`scripts/build_skill_package.py --output /实际输出/hand-drawn-skill.zip` 打包方法、脚本与配方并独立解包检查，不携带运行环境、项目素材或设备配置。参考图缓存机制见 [图像托管实现](docs/image-hosting.md)。
