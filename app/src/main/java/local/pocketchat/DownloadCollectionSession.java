package local.pocketchat;

import java.util.WeakHashMap;

/** Native tab changes keep explicit choices without persisting file grants or retaining activities. */
final class DownloadCollectionSession {
  static final class State {final DownloadCollection files=new DownloadCollection();boolean collecting;}
  private static final WeakHashMap<Object,State> sessions=new WeakHashMap<>();
  static State get(Object activity){State state=sessions.get(activity);if(state==null){state=new State();sessions.put(activity,state);}return state;}
}
