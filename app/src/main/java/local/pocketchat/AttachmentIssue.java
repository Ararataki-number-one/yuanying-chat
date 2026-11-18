package local.pocketchat;

/** A native picker outcome. Its presentation never determines its meaning. */
enum AttachmentIssue {
  PAGE_NOT_READY("网页正在切换或尚未就绪，请稍后再添加附件"),
  PAGE_CHANGED("附件所属页面已变化，请重新选择"),
  PHOTO_UNCONFIRMED("图片处理权限未确认，照片尚未上传；可重新选择或改用标准保护"),
  PHOTO_DENIED("本站已拒绝 Canvas 图片处理，照片尚未上传；可改用标准保护后重新选择"),
  PICKER_LIMIT("本次运行的文件选择次数已用尽，请重启应用后再试"),
  NO_PICKER("设备没有可用的文件选择器"),
  PICKER_ACCESS("无法打开文件选择器，请检查系统文件访问设置"),
  PICKER_FAILED("无法打开文件选择器，请稍后重试"),
  SELECTION_MOVED("对话已改变，未添加附件"),
  INVALID_SELECTION("请选择系统文件选择器中的文件"),
  READ_FAILED("无法读取所选文件，请重新选择");

  final String message;

  AttachmentIssue(String message) {
    this.message = message;
  }
}
