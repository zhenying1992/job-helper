.PHONY: run build clean

# 虚拟环境里的 flet 路径
FLET := .venv/bin/flet

# 先加载环境变量（解决 IDE 里运行找不到 flutter/pod 的问题）
ENV := source ~/.zshrc &&

# 开发模式启动（带热重载）
run:
	$(ENV) $(FLET) run -r main.py

# 构建 macOS 应用
build: clean
	$(ENV) $(FLET) build macos

# 清理构建产物
clean:
	rm -rf build/
