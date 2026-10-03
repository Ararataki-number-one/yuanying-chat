package local.pocketchat;

/** User work blocks a settings change; navigation and retry timers can be replaced. */
final class BrowserSettingsPolicy {
  static String reason(boolean pending,boolean submitting,boolean operation,boolean download,boolean upload,boolean reply){
    if(pending||submitting)return "当前提问还未处理完，请先在发送记录中确认结果，再保存";
    if(operation)return "网页操作正在进行，完成后再保存";
    if(download)return "文件正在下载，完成或暂停下载后再保存";
    if(upload)return "附件正在上传，完成后再保存";
    if(reply)return "网页正在回复，回复结束后再保存";
    return "";
  }
  static boolean currentReply(boolean chatPage,boolean samePage,boolean busy,long observedEpoch,long currentEpoch){
    return chatPage&&samePage&&busy&&observedEpoch==currentEpoch;
  }
}
