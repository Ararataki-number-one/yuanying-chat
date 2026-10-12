package org.mozilla.geckoview;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicIntegerArray;

/** Diagnostic-only SDK observer. Primitive bounded storage; no event JSON/logging. */
public final class PocketGeckoEditableTrace {
  private static final int CAPACITY=4096, WIDTH=14;
  private static final long[][] ROWS=new long[CAPACITY][WIDTH];
  private static final AtomicIntegerArray READY=new AtomicIntegerArray(CAPACITY);
  private static final AtomicInteger RESERVED=new AtomicInteger(),PUBLISHED=new AtomicInteger(),OVERFLOW=new AtomicInteger(),ACTIVE=new AtomicInteger();
  private static volatile boolean enabled;
  private PocketGeckoEditableTrace(){}
  public static boolean enabled(){return enabled;}
  public static synchronized void start(){
    enabled=false;waitWriters();RESERVED.set(0);PUBLISHED.set(0);OVERFLOW.set(0);
    for(int i=0;i<CAPACITY;i++)READY.set(i,0);enabled=true;
  }
  public static void stop(){enabled=false;waitWriters();}
  private static void waitWriters(){long deadline=System.nanoTime()+100_000_000L;while(ACTIVE.get()!=0&&System.nanoTime()<deadline)Thread.yield();}
  public static int length(CharSequence text){return text==null?-1:text.length();}
  public static void record(int code,int edge,int argStart,int argEnd,int flags,int length,int currentStart,int currentEnd,int shadowStart,int shadowEnd,int queue){
    if(!enabled)return;ACTIVE.incrementAndGet();
    try{
      if(!enabled)return;int index=RESERVED.getAndIncrement();
      if(index>=CAPACITY){OVERFLOW.incrementAndGet();return;}
      long[] row=ROWS[index];row[0]=code;row[1]=edge;row[2]=System.nanoTime();row[3]=Thread.currentThread().getId();
      row[4]=argStart;row[5]=argEnd;row[6]=flags;row[7]=length;row[8]=currentStart;row[9]=currentEnd;row[10]=shadowStart;row[11]=shadowEnd;row[12]=queue;row[13]=index;
      READY.set(index,1);PUBLISHED.incrementAndGet();
    }finally{ACTIVE.decrementAndGet();}
  }
  public static long[] summary(){return new long[]{CAPACITY,RESERVED.get(),PUBLISHED.get(),OVERFLOW.get()};}
  public static synchronized long[][] drain(){
    if(enabled)throw new IllegalStateException("Stop the diagnostic observer before draining");waitWriters();
    int size=Math.min(CAPACITY,RESERVED.get()),count=0;for(int i=0;i<size;i++)if(READY.get(i)!=0)count++;
    long[][] result=new long[count][WIDTH];int next=0;for(int i=0;i<size;i++)if(READY.get(i)!=0)System.arraycopy(ROWS[i],0,result[next++],0,WIDTH);
    return result;
  }
}
