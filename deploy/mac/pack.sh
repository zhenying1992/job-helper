#!/bin/zsh
set -e

# ========== 自动切换到项目根目录 ==========
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$PROJECT_ROOT"
echo "📂 项目根目录: $PROJECT_ROOT"
# ==========================================

# 配置项
APP_NAME="JobHelper"
BUNDLE_ID="com.yourname.jobhelper"
ENTITLEMENT_FILE="deploy/mac/entitlements.plist"
MAIN_SCRIPT="src/main.py"

# 1. 创建 entitlements.plist
cat > "$ENTITLEMENT_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
</dict>
</plist>
EOF

echo "✅ 已生成 $ENTITLEMENT_FILE"

# 2. 清理旧打包产物
rm -rf build dist
echo "✅ 清理旧 build/dist"

# 3. flet pack打包：移除osx-entitlements-file参数！！
flet pack "$MAIN_SCRIPT" \
-n "$APP_NAME" \
--bundle-id "$BUNDLE_ID" \
--pyinstaller-build-args="--onedir"

# 4. 【关键】对整个App Bundle重签名，注入entitlements
APP_PATH="dist/${APP_NAME}.app"
echo "🔐 对整个App进行adhoc签名，注入文件权限entitlements"
codesign --force --deep --options runtime --entitlements "$ENTITLEMENT_FILE" --sign - "$APP_PATH"

echo ""
echo "🎉 打包+签名完成！输出目录：$APP_PATH"
# open "$APP_PATH"
