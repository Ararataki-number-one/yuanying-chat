package android.content;
import android.net.Uri;import java.util.*;
public class ClipData{public static class Item{public final Uri uri;public Item(Uri uri){this.uri=uri;}}public final ArrayList<Item> items=new ArrayList<>();public static ClipData newRawUri(String label,Uri uri){ClipData clip=new ClipData();clip.items.add(new Item(uri));return clip;}public void addItem(Item item){items.add(item);}}
