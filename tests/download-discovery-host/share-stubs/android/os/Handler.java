package android.os;
/** Host callback boundary, deliberately inline; Android main-loop behavior is not simulated. */
public final class Handler{public boolean post(Runnable run){run.run();return true;}}
