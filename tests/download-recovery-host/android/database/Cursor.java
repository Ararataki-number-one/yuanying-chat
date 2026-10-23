package android.database;public interface Cursor extends AutoCloseable {boolean moveToFirst();String getString(int i);int getInt(int i);long getLong(int i);boolean isNull(int i);void close();}
