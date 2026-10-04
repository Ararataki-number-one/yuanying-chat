# 1.5.13 Oil UI 原生界面校准

沿用用户确定的 AdsPower 管理方向与现有 HTML 参考。会话页以真实网页为主，环境页以环境名称和管理操作为主，网络页以窗口线路与真实状态为主。本轮只调整原生界面的视觉层级和尺寸，正式版本为 1.5.13 / code 39。

## 页面变化

- 统一主蓝色、文字颜色、圆角、按钮、输入框和底部导航。普通字号的底部导航从 68 dp 调整为 60 dp，会话顶部沿用前版的 72 dp。保留系统状态栏、导航栏和键盘安全区处理。
- 环境名称更突出，卡片的“打开环境”改为浅蓝，页面的新建保留实心蓝色。序号改为普通辅助文字，“更多”收为菜单图标并提供完整无障碍名称。未核验、未知地区、等待应用等判断信息继续显示。
- 设置行减少重复边框，辅助说明提高可读性。会话“简洁 / 原网页”去掉外层重复描边，切换行为保持原有实现。
- 居中弹窗的标题允许两行，内容区域按实际标题、按钮和可用屏幕高度计算。系统大字体下，Tab 可以横向滚动，选中项自动可见；弹窗底部按钮纵排。环境编辑页的大字体布局将主保存按钮放到第二行。

## 修改文件

| 文件 | 修改与原因 |
| --- | --- |
| `app/src/main/java/local/pocketchat/DesignUi.java` | 统一共享颜色、卡片、按钮、输入框、状态标签与设置行；委托同一套页签和导航样式，减少跨模块差异。 |
| `app/src/main/java/local/pocketchat/ReferenceUi.java` | 复用共享视觉变量，压缩导航并保留不传出按钮数组的既有调用方式；改进居中弹窗测量、标题换行与大字体按钮排列；页签在大字体下可滚动。 |
| `app/src/main/java/local/pocketchat/WindowHomeActivity.java` | 降低卡片操作和序号的视觉重量，突出名称，常规字体下合并标题与新建操作，去掉重复总数；筛选改为简洁文字按钮，保留既有筛选和菜单回调。 |
| `app/src/main/java/local/pocketchat/DesignChrome.java` | 会话显示模式使用一层浅蓝容器，去掉重复描边；真实网页与切换逻辑保持原有实现。 |
| `app/src/main/java/local/pocketchat/EnvironmentEditorUi.java` | 调整大字体下底部按钮排列，统一下拉项字色和字号、改善全屏编辑状态栏对比，保留取消、存草稿与保存的处理。 |
| `app/src/main/java/local/pocketchat/EntryPickerUi.java` | 当前入口允许换行；大字体下先显示当前候选与重新随机，再显示节点列表；修正节点行触摸高度为 48 dp；精简说明并保留地区来自名称的来源提示。 |
| `app/src/main/java/local/pocketchat/NetworkWorkspaceUi.java` | 将筛选收进标题区，压缩窗口列表顶部留白；代理地址示例放到可换行说明，保留原连接与保存逻辑。 |
| `app/src/main/java/local/pocketchat/BrowserDisplayUi.java` | 显示方式选择器复用共享字色与字号，选项及选择结果保持原样。 |
| `app/build.gradle`、`app/src/main/AndroidManifest.xml` | 更新正式应用版本。内核扩展没有改动，扩展版本保留。 |
| `tests/gecko/UiVisualIntegrationActivity.java`、`tests/gecko/AndroidManifest.xml` | 在独立测试包内打开生产原生控件，使用本地合成环境与订阅记录，不读取正式账号或发起真实网络配置。 |
| `tests/gecko/run_ui_visuals.py` | 在 Android 实例上保存原生截图与控件树，覆盖会话外壳、管理页面、两种手机宽度和大字体；失败时保留已取得的证据。 |
| `tools/gecko/build_ui_baseline.py` | 仅恢复八个视觉源文件构建对照样式，其他核心源码、版本、数据和测试签名一致；随后还原当前源码与测试 APK。 |
| `.github/workflows/gecko-integration.yml`、`tools/gecko/publish_ci.py` | 构建并保存原生前后对比画面，清除测试数据后显式处理测试通知权限，先取得画面再执行已有回归；正式 ARM64 包不使用对照源码构建。 |
| `tools/sign-apk.py`、`tools/publish-gecko-release.py` | 确认测试视觉页面没有进入正式 APK；发布前要求匹配源码的原生回归和视觉取证报告。 |
| `docs/ui/OIL-UI-DIRECTION.md`、`docs/RELEASE-v1.5.13.md` | 记录设计方向、共享尺寸、减法与版本说明。 |

删除了序号的蓝色装饰、设置行内部描边、模式切换重复边框、卡片上重复出现的实心主按钮，以及“最近使用 ·”与“尚未使用”等辅助文字。环境名称、状态、地区来源、IP、核验与主要操作保留。

本轮没有改变浏览器生命周期、官方网页组件、账号数据、环境隔离、代理实现和后台回复服务。完整方向见 [设计说明](ui/OIL-UI-DIRECTION.md)，实际画面与评审记录见 [版本验证](../verification/oil-ui-v1.5.13/README.md)。
