# GPT × DeepSeek Q版宠物

一个零依赖的本地浏览器预览项目，包含两只 8×11、192×208 单元格的 Codex v2 精灵宠物。

## 运行

直接双击 `index.html`，或使用任意静态文件服务器打开项目根目录。

## Windows 桌面宠物

先安装依赖：

```powershell
py -m pip install -r requirements.txt
```

然后双击 `run_desktop_pet.bat`，或运行：

```powershell
py desktop_pet.py
```

宠物会出现在屏幕右下角。左键拖动，右键切换 GPT/DeepSeek、切换状态或退出；按 `Esc` 也可退出。

## 内容

- `assets/luma-gpt.webp`：Luma，银白色知识研究员风格 GPT 宠物。
- `assets/mira-deepseek.webp`：Mira，深蓝海洋探索者风格 DeepSeek 宠物。
- `assets/*.manifest.json`：图集尺寸、行列和 16 向注视映射。
- `index.html`：状态动画预览，包含休息、散步、招呼、开心、偷吃、喝水、工作、完成。

## 图集格式

两张图集均为 8 列 × 11 行、每格 192 × 208 px，WebP RGBA，兼容 spriteVersionNumber 2。

## 交付说明

此版本基于用户确认的候选预览效果。图集结构校验已经通过；方向盲测仍保留为后续可继续优化的 QA 项，不影响本地状态预览使用。
