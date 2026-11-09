package local.pocketchat;

import android.graphics.Matrix;
import android.graphics.Path;
import android.graphics.RectF;

/** Cached 24-unit workspace symbols. Color and stroke treatment belong to Ui.Icon. */
final class WorkspaceGlyphs {
  private WorkspaceGlyphs() {}

  /** Builds recognized symbols only; an unknown name leaves both paths untouched. */
  static boolean build(String name,Path outline,Path ink) {
    if(name==null)return false;
    switch(name){
      case "env-orbit":clear(outline,ink);orbit(outline,ink);return true;
      case "env-grid":clear(outline,ink);grid(outline);return true;
      case "env-layers":clear(outline,ink);layers(outline);return true;
      case "env-diamond":clear(outline,ink);diamond(outline,ink);return true;
      case "env-flower":clear(outline,ink);flower(outline,ink);return true;
      case "env-rings":clear(outline,ink);rings(outline);return true;
      case "env-hex":clear(outline,ink);hex(outline,ink);return true;
      case "env-arc":clear(outline,ink);arch(outline,ink);return true;
      case "file-pdf":clear(outline,ink);document(outline);pdf(outline);return true;
      case "file-text":clear(outline,ink);document(outline);text(outline);return true;
      case "file-archive":clear(outline,ink);document(outline);archive(outline,ink);return true;
      case "node":clear(outline,ink);node(outline,ink);return true;
      case "source":clear(outline,ink);source(outline,ink);return true;
      default:return false;
    }
  }

  private static void clear(Path outline,Path ink) {
    outline.rewind();ink.rewind();
    outline.setFillType(Path.FillType.WINDING);ink.setFillType(Path.FillType.WINDING);
  }

  private static void orbit(Path outline,Path ink) {
    outline.addOval(new RectF(3.5f,7f,20.5f,17f),Path.Direction.CW);
    Matrix tilt=new Matrix();tilt.setRotate(-30f,12f,12f);outline.transform(tilt);
    ink.addCircle(12f,12f,1.8f,Path.Direction.CW);
    ink.addCircle(19.36f,7.75f,1.65f,Path.Direction.CW);
  }

  private static void grid(Path outline) {
    outline.addRoundRect(new RectF(3.5f,3.5f,10f,10f),1.7f,1.7f,Path.Direction.CW);
    outline.addRoundRect(new RectF(14f,3.5f,20.5f,10f),1.7f,1.7f,Path.Direction.CW);
    outline.addRoundRect(new RectF(3.5f,14f,10f,20.5f),1.7f,1.7f,Path.Direction.CW);
    outline.addRoundRect(new RectF(14f,14f,20.5f,20.5f),1.7f,1.7f,Path.Direction.CW);
  }

  private static void layers(Path outline) {
    outline.moveTo(4.3f,7.1f);outline.lineTo(11.2f,3.7f);
    outline.quadTo(12f,3.3f,12.8f,3.7f);outline.lineTo(19.7f,7.1f);
    outline.quadTo(20.5f,7.7f,19.7f,8.3f);outline.lineTo(12.8f,11.7f);
    outline.quadTo(12f,12.1f,11.2f,11.7f);outline.lineTo(4.3f,8.3f);
    outline.quadTo(3.5f,7.7f,4.3f,7.1f);outline.close();
    outline.moveTo(3.8f,12f);outline.lineTo(11.2f,15.8f);
    outline.quadTo(12f,16.2f,12.8f,15.8f);outline.lineTo(20.2f,12f);
    outline.moveTo(3.8f,16.4f);outline.lineTo(11.2f,20.2f);
    outline.quadTo(12f,20.6f,12.8f,20.2f);outline.lineTo(20.2f,16.4f);
  }

  private static void diamond(Path outline,Path ink) {
    outline.moveTo(11f,4.5f);outline.quadTo(12f,3.5f,13f,4.5f);
    outline.lineTo(19.5f,11f);outline.quadTo(20.5f,12f,19.5f,13f);
    outline.lineTo(13f,19.5f);outline.quadTo(12f,20.5f,11f,19.5f);
    outline.lineTo(4.5f,13f);outline.quadTo(3.5f,12f,4.5f,11f);outline.close();
    ink.moveTo(11.4f,9f);ink.quadTo(12f,8.4f,12.6f,9f);
    ink.lineTo(15f,11.4f);ink.quadTo(15.6f,12f,15f,12.6f);
    ink.lineTo(12.6f,15f);ink.quadTo(12f,15.6f,11.4f,15f);
    ink.lineTo(9f,12.6f);ink.quadTo(8.4f,12f,9f,11.4f);ink.close();
  }

  private static void flower(Path outline,Path ink) {
    outline.moveTo(12f,5.5f);
    outline.cubicTo(10.1f,2.8f,6.1f,2.8f,5.2f,5.2f);
    outline.cubicTo(2.8f,6.1f,2.8f,10.1f,5.5f,12f);
    outline.cubicTo(2.8f,13.9f,2.8f,17.9f,5.2f,18.8f);
    outline.cubicTo(6.1f,21.2f,10.1f,21.2f,12f,18.5f);
    outline.cubicTo(13.9f,21.2f,17.9f,21.2f,18.8f,18.8f);
    outline.cubicTo(21.2f,17.9f,21.2f,13.9f,18.5f,12f);
    outline.cubicTo(21.2f,10.1f,21.2f,6.1f,18.8f,5.2f);
    outline.cubicTo(17.9f,2.8f,13.9f,2.8f,12f,5.5f);outline.close();
    ink.addCircle(12f,12f,1.5f,Path.Direction.CW);
  }

  private static void rings(Path outline) {
    outline.addCircle(8.5f,9.5f,5f,Path.Direction.CW);
    outline.addCircle(15.5f,14.5f,5f,Path.Direction.CW);
  }

  private static void hex(Path outline,Path ink) {
    outline.moveTo(11.1f,3.9f);outline.quadTo(12f,3.4f,12.9f,3.9f);
    outline.lineTo(19.1f,7.5f);outline.quadTo(20f,8f,20f,9f);
    outline.lineTo(20f,15f);outline.quadTo(20f,16f,19.1f,16.5f);
    outline.lineTo(12.9f,20.1f);outline.quadTo(12f,20.6f,11.1f,20.1f);
    outline.lineTo(4.9f,16.5f);outline.quadTo(4f,16f,4f,15f);
    outline.lineTo(4f,9f);outline.quadTo(4f,8f,4.9f,7.5f);outline.close();
    ink.addCircle(12f,12f,2f,Path.Direction.CW);
  }

  private static void arch(Path outline,Path ink) {
    outline.moveTo(4f,19.8f);outline.lineTo(4f,11.5f);
    outline.cubicTo(4f,7.1f,7.6f,3.5f,12f,3.5f);
    outline.cubicTo(16.4f,3.5f,20f,7.1f,20f,11.5f);outline.lineTo(20f,19.8f);
    outline.moveTo(8f,19.8f);outline.lineTo(8f,11.5f);
    outline.cubicTo(8f,9.3f,9.8f,7.5f,12f,7.5f);
    outline.cubicTo(14.2f,7.5f,16f,9.3f,16f,11.5f);outline.lineTo(16f,19.8f);
    ink.addRoundRect(new RectF(10.9f,13f,13.1f,19.8f),1.1f,1.1f,Path.Direction.CW);
  }

  private static void document(Path outline) {
    outline.moveTo(6.4f,3.5f);outline.lineTo(13.6f,3.5f);
    outline.quadTo(14.15f,3.5f,14.55f,3.9f);outline.lineTo(18.85f,8.2f);
    outline.quadTo(19.25f,8.6f,19.25f,9.15f);outline.lineTo(19.25f,18.85f);
    outline.quadTo(19.25f,20.5f,17.6f,20.5f);outline.lineTo(6.4f,20.5f);
    outline.quadTo(4.75f,20.5f,4.75f,18.85f);outline.lineTo(4.75f,5.15f);
    outline.quadTo(4.75f,3.5f,6.4f,3.5f);outline.close();
    outline.moveTo(13.5f,3.8f);outline.lineTo(13.5f,7.25f);
    outline.quadTo(13.5f,9f,15.25f,9f);outline.lineTo(18.9f,9f);
  }

  /** A curve mark remains legible without trying to fit three tiny letters. */
  private static void pdf(Path outline) {
    outline.moveTo(7.7f,17.5f);
    outline.cubicTo(9.3f,16.5f,10.6f,14f,11.1f,11.4f);
    outline.cubicTo(11.5f,14.4f,12.8f,16.8f,15.7f,17.5f);
    outline.moveTo(8.3f,16.1f);outline.cubicTo(10.6f,15.2f,13.3f,15.1f,16.1f,15.7f);
  }

  private static void text(Path outline) {
    outline.moveTo(8f,12f);outline.lineTo(16f,12f);
    outline.moveTo(8f,15f);outline.lineTo(16f,15f);
    outline.moveTo(8f,18f);outline.lineTo(12.8f,18f);
  }

  private static void archive(Path outline,Path ink) {
    ink.addRoundRect(new RectF(10.35f,10.5f,12.15f,11.9f),.3f,.3f,Path.Direction.CW);
    ink.addRoundRect(new RectF(11.85f,12.1f,13.65f,13.5f),.3f,.3f,Path.Direction.CW);
    ink.addRoundRect(new RectF(10.35f,13.7f,12.15f,15.1f),.3f,.3f,Path.Direction.CW);
    outline.addRoundRect(new RectF(10.2f,15.7f,13.8f,18.4f),.7f,.7f,Path.Direction.CW);
  }

  private static void node(Path outline,Path ink) {
    outline.moveTo(9.6f,9.4f);outline.lineTo(5f,5.5f);
    outline.moveTo(14.4f,9.4f);outline.lineTo(19f,5.5f);
    outline.moveTo(12f,15.1f);outline.lineTo(12f,19.5f);
    outline.addCircle(12f,11.8f,3.3f,Path.Direction.CW);
    ink.addCircle(5f,5.5f,2f,Path.Direction.CW);
    ink.addCircle(19f,5.5f,2f,Path.Direction.CW);
    ink.addCircle(12f,19.5f,2f,Path.Direction.CW);
  }

  private static void source(Path outline,Path ink) {
    outline.moveTo(7f,3.5f);outline.lineTo(18.5f,3.5f);
    outline.quadTo(20.5f,3.5f,20.5f,5.5f);outline.lineTo(20.5f,17f);
    outline.addRoundRect(new RectF(3.5f,6.5f,17.5f,20.5f),2.3f,2.3f,Path.Direction.CW);
    ink.addCircle(6.8f,10.9f,.85f,Path.Direction.CW);
    ink.addCircle(6.8f,15.8f,.85f,Path.Direction.CW);
    outline.moveTo(9.6f,10.9f);outline.lineTo(14.2f,10.9f);
    outline.moveTo(9.6f,15.8f);outline.lineTo(14.2f,15.8f);
  }
}
