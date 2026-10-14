"""Execute the actual fixture's Java coordinate method on the host JVM.

These checks cover coordinate arithmetic, captured tap targets, and rejection only. They do not
execute Android, Gecko, a native matrix provider, or real keyboard input.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ACTIVITY = ROOT / 'tests/gecko/GeckoCaretCompatibilityIntegrationActivity.java'
PINNED_JAVA = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')


def actual_method(source, name='mapClientPoint'):
    """Copy the complete method, including its validation, from fixture source."""
    match = re.search(r'\b(?:static\s+)?(?:float\s*\[\s*\]|JSONObject)\s+' + re.escape(name)
                      + r'\s*\([^)]*\)\s*(?:throws\s+Exception\s*)?\{', source)
    if match is None:
        raise AssertionError('Actual fixture ' + name + ' method is absent')
    depth = 1
    cursor = match.end()
    quote = None
    while cursor < len(source):
        char = source[cursor]
        if quote:
            if char == '\\':
                cursor += 2
                continue
            if char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif source.startswith('//', cursor):
            end = source.find('\n', cursor)
            cursor = len(source) if end < 0 else end
            continue
        elif source.startswith('/*', cursor):
            end = source.find('*/', cursor + 2)
            if end < 0:
                raise AssertionError('Unterminated fixture method comment')
            cursor = end + 2
            continue
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return source[match.start():cursor + 1]
        cursor += 1
    raise AssertionError('Actual fixture mapClientPoint method is incomplete')


JAVA_CHECKS = r'''
  // Minimal JSON containers let the complete source tap method execute without
  // Android. A fresh native query fails, proving both taps use the owned pose.
  static class JSONObject {
    final java.util.Map<String,Object> values=new java.util.LinkedHashMap<>();
    Object get(String key){if(!values.containsKey(key))throw new AssertionError("Missing "+key);return values.get(key);}
    double getDouble(String key){return ((Number)get(key)).doubleValue();}
    int getInt(String key){return ((Number)get(key)).intValue();}
    JSONObject getJSONObject(String key){return (JSONObject)get(key);}
    JSONArray getJSONArray(String key){return (JSONArray)get(key);}
  }
  static class JSONArray extends java.util.ArrayList<Object> {
    JSONArray put(Object value){add(value);return this;}
    int length(){return size();}
    double getDouble(int index){return ((Number)get(index)).doubleValue();}
    JSONObject getJSONObject(int index){return (JSONObject)get(index);}
  }
  static class J {
    static JSONObject obj(Object... pairs){JSONObject value=new JSONObject();for(int i=0;i<pairs.length;i+=2)value.values.put((String)pairs[i],pairs[i+1]);return value;}
  }
  JSONObject nativeGeometry(JSONObject value){throw new AssertionError("Tap queried a new unpaired native pose");}
  interface Work { void run(); }
  static void close(float expected,float actual) {
    if(!Float.isFinite(actual)||Math.abs(expected-actual)>.001f)
      throw new AssertionError("Expected "+expected+", received "+actual);
  }
  static void rejected(Work call) {
    try { call.run(); } catch(IllegalArgumentException expected) { return; }
    throw new AssertionError("Invalid geometry was accepted");
  }
  static float[] identity() { return new float[]{1,0,0,0,1,0,0,0,1}; }
  public static void main(String[] args) throws Exception {
    switch(args[0]) {
      case "ime-regression": {
        float x=147.98405896777342f,y=91.99999829882812f;
        float ratio=1080f/414f;
        float[] matrix={ratio,0,0,0,ratio,0,0,0,1};
        // Recorded layout viewport heights differ; native transform and CSS
        // point are unchanged. Both observations must map to the same tap.
        for(int innerHeight:new int[]{667,989}) {
          float[] point=mapClientPoint(x,y,matrix,1,0,117);
          if(Math.round(point[0])!=386||Math.round(point[1])!=357)
            throw new AssertionError("IME viewport "+innerHeight+" moved native tap");
        }
        int oldBefore=117+Math.round(y*1740f/667f);
        int oldAfter=117+Math.round(y*1740f/989f);
        if(oldBefore!=357||oldAfter!=279)
          throw new AssertionError("Retained failure vector changed");
        break;
      }
      case "translation-layout-origin": {
        float[] matrix={2,0,-8,0,2,13,0,0,1};
        float[] point=mapClientPoint(10,20,matrix,.75f,31,47);
        close(40,point[0]);close(86.75f,point[1]);
        float[] simple=mapClientPoint(-4,-9,identity(),1,-10,12);
        close(-14,simple[0]);close(3,simple[1]);
        break;
      }
      case "matrix-length": {
        rejected(()->mapClientPoint(1,2,null,1,0,0));
        for(int size:new int[]{0,1,8,10}) {
          final float[] matrix=new float[size];
          rejected(()->mapClientPoint(1,2,matrix,1,0,0));
        }
        break;
      }
      case "matrix-finiteness": {
        for(int index=0;index<9;index++)for(float invalid:new float[]{Float.NaN,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY}) {
          float[] matrix=identity();matrix[index]=invalid;
          rejected(()->mapClientPoint(1,2,matrix,1,0,0));
        }
        break;
      }
      case "coordinate-layout-finiteness": {
        for(float invalid:new float[]{Float.NaN,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY}) {
          rejected(()->mapClientPoint(invalid,2,identity(),1,0,0));
          rejected(()->mapClientPoint(1,invalid,identity(),1,0,0));
          rejected(()->mapClientPoint(1,2,identity(),invalid,0,0));
        }
        for(float invalid:new float[]{0,-1,2})
          rejected(()->mapClientPoint(1,2,identity(),invalid,0,0));
        break;
      }
      case "nonuniform-skew-perspective": {
        for(float[] matrix:new float[][]{
          {0,0,0,0,0,0,0,0,1},{-1,0,0,0,-1,0,0,0,1},
          {.0005f,0,0,0,0,0,0,0,1},{.0005f,0,0,0,-.00025f,0,0,0,1},
          {2,0,0,0,3,0,0,0,1},{1,.25f,0,0,1,0,0,0,1},
          {1,0,0,.25f,1,0,0,0,1},{1,0,0,0,1,0,.25f,0,1},
          {1,0,0,0,1,0,0,.25f,1},{1,0,0,0,1,0,0,0,2}})
          rejected(()->mapClientPoint(1,2,matrix,1,0,0));
        break;
      }
      case "result-overflow": {
        float[] matrix={Float.MAX_VALUE,0,0,0,Float.MAX_VALUE,0,0,0,1};
        rejected(()->mapClientPoint(2,2,matrix,1,0,0));
        float[] translated={1,0,Float.MAX_VALUE,0,1,Float.MAX_VALUE,0,0,1};
        rejected(()->mapClientPoint(Float.MAX_VALUE,Float.MAX_VALUE,translated,.75f,0,0));
        break;
      }
      case "captured-rapid-taps": {
        CaretGeometryUnderTest fixture=new CaretGeometryUnderTest();
        JSONArray matrix=new JSONArray();for(float value:new float[]{2.5f,0,0,0,2.5f,0,0,0,1})matrix.put(value);
        JSONObject pose=J.obj("clientToSurfaceMatrix",matrix,"readingLayout",1,"originX",0,"originY",117);
        JSONObject viewport=J.obj("width",432,"height",667);
        JSONArray points=new JSONArray();for(int i=0;i<=10;i++)points.put(J.obj("x",(100+i)/2.5,"y",80));
        JSONObject observation=J.obj("nativeGeometry",pose,"viewport",viewport,"points",points);
        for(int caret:new int[]{2,9}) {
          JSONObject tap=fixture.tap(observation,caret);
          if(tap.getInt("expectedCaret")!=caret||tap.getInt("x")!=100+caret||tap.getInt("y")!=317
              ||tap.getJSONObject("clientPoint")!=points.getJSONObject(caret)
              ||tap.getJSONObject("nativeGeometry")!=pose||tap.getJSONObject("viewport")!=viewport)
            throw new AssertionError("Tap substituted the captured point, viewport or native pose");
        }
        break;
      }
      default: throw new AssertionError("Unknown host vector");
    }
    System.out.println("PASS "+args[0]+"; host Java arithmetic only");
  }
'''


class CaretGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = os.environ.get('PROFILE_JAVA') or (str(PINNED_JAVA) if PINNED_JAVA.exists() else shutil.which('java'))
        if not cls.java:
            raise RuntimeError('A host JDK is required to execute actual Java geometry')
        cls.temporary = tempfile.TemporaryDirectory(prefix='caret-geometry-host-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        fixture_source=ACTIVITY.read_text()
        methods='\n'.join(actual_method(fixture_source,name) for name in ['mapClientPoint','matrixValues','tap'])
        source = 'public final class CaretGeometryUnderTest {\n' + methods + '\n' + JAVA_CHECKS + '\n}\n'
        path = cls.directory / 'CaretGeometryUnderTest.java'
        path.write_text(source)
        compiled = subprocess.run([cls.java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8',str(path)],
                                  text=True,capture_output=True,timeout=30)
        if compiled.returncode:
            raise AssertionError('Actual Java fixture method did not compile:\n' + compiled.stdout + compiled.stderr)

    def vector(self, name):
        result = subprocess.run([self.java,'-cp',str(self.directory),'CaretGeometryUnderTest',name],
                                text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(),'PASS ' + name + '; host Java arithmetic only')

    def test_retained_ime_viewport_height_does_not_distort_native_tap(self):
        self.vector('ime-regression')

    def test_translation_layout_and_surface_origin_are_applied_in_order(self):
        self.vector('translation-layout-origin')

    def test_missing_and_wrong_length_matrix_is_rejected(self):
        self.vector('matrix-length')

    def test_every_nonfinite_matrix_component_is_rejected(self):
        self.vector('matrix-finiteness')

    def test_nonfinite_coordinates_and_nonpositive_layout_are_rejected(self):
        self.vector('coordinate-layout-finiteness')

    def test_skew_perspective_nonuniform_and_nonpositive_scale_are_rejected(self):
        self.vector('nonuniform-skew-perspective')

    def test_native_coordinate_overflow_is_rejected(self):
        self.vector('result-overflow')

    def test_both_rapid_taps_use_the_same_captured_pose_viewport_and_measured_points(self):
        self.vector('captured-rapid-taps')


if __name__ == '__main__':
    unittest.main()
