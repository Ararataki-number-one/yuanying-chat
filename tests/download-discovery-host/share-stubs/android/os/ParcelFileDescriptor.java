package android.os;
public class ParcelFileDescriptor implements AutoCloseable{public static int closed;public void close(){closed++;}}
