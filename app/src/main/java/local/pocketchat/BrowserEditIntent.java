package local.pocketchat;

import org.json.JSONObject;

/** A failed candidate is owned by its template editor until explicitly retried
 * or overridden. Saving unrelated environment metadata cannot replace it. */
final class BrowserEditIntent {
  static final String EDITED="browserFieldsEdited";
  static boolean fieldsChanged(JSONObject baseline,int level,boolean desktop){return baseline!=null&&(baseline.optInt("privacyLevel")!=level||baseline.optBoolean("desktopSite")!=desktop);}
  static boolean explicitFailedOverride(boolean queueUnavailable,JSONObject values){return queueUnavailable&&Boolean.TRUE.equals(values.opt(EDITED));}
  static boolean browserIntent(boolean queueUnavailable,JSONObject values,boolean settingsDiffer,boolean applicationPending){return !preserveFailedCandidate(queueUnavailable,values)&&(settingsDiffer||applicationPending||explicitFailedOverride(queueUnavailable,values));}
  static boolean preserveFailedCandidate(boolean queueUnavailable,JSONObject values){return queueUnavailable&&values.has(EDITED)&&Boolean.FALSE.equals(values.opt(EDITED));}
}
