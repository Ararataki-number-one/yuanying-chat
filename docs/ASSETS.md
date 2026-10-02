# 品牌素材

使用内置 `image_gen` 工具，根据用户提供设计图中的启动页插画生成单张不含文字的应用背景；未使用 CLI/API 密钥模式。

项目使用文件：`app/src/main/assets/brand-portal.png`。工作副本：`assets/brand-portal.png`。品牌文字、按钮、图标和普通界面在应用中原生绘制，便于后续调整，不烘焙到背景图中。

## 实际提示词

> Use case: background-extraction / style-transfer. Input image is the user's app design board, not an image to reproduce as a board. Extract and faithfully recreate ONLY the fantasy illustration used inside the FIRST startup/brand phone screen: luminous electric blue circular portal in a star-filled indigo night sky, craggy blue mountains, a single small dark robed silhouette standing before the portal. Deliver ONE clean portrait 9:16 background artwork for an Android launch screen. Retain the reference art's blue/cyan/violet palette, composition and dark magical atmosphere. Crisp finished illustration. Top 25 percent should be dark starfield with room for a native logo/title overlay, the portal dominates the central/lower middle, bottom 20 percent remains dark for native copy/buttons. Remove ALL text, Chinese lettering, logos, UI controls, headings, phone borders, status bars, other panels, watermark and all design-board content. This is a production background asset, not a mockup or collage. No added figures. Opaque background.

原生小图标在已有 `Ui.Icon` 图标体系中扩展。启动图标为 `app/src/main/res/drawable/ic_brand.xml`，可编辑的矢量资源。
