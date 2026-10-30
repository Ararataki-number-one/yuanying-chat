package android.database;public interface Cursor extends AutoCloseable {boolean moveToNext();int getInt(int at);String getString(int at);long getLong(int at);void close();}
