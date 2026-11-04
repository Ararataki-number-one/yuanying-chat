import com.sun.source.tree.*;
import com.sun.source.util.*;
import javax.tools.*;
import javax.lang.model.element.Modifier;
import java.nio.file.*;
import java.util.*;
import java.io.*;

/** Generates compilation-only app API boundaries; never supplies an SDK package. */
public class BoundaryGenerator {
  static String flags(ModifiersTree m, boolean field) {
    StringBuilder b=new StringBuilder();
    for(Modifier f:m.getFlags())if(!(field&&f==Modifier.FINAL))b.append(f.toString()).append(' ');
    return b.toString();
  }
  static boolean sdk(String s){return s.matches("(?s).*(org\\.mozilla|GeckoSession|GeckoRuntime|GeckoResult|GeckoProfile|WebExtension|ImageDecoder|ContentBlocking|StorageController|EventDispatcher|GeckoBundle|GeckoDisplay|PanZoomController|Autofill|WebResponse|\\bGeckoView\\b).*" );}
  static String def(Tree type){String t=type.toString();return t.equals("boolean")?"false":Set.of("byte","short","int","long","float","double","char").contains(t)?"0":"null";}
  static String cls(ClassTree c,String parent){
    if(c.getKind()==Tree.Kind.ENUM)return c.toString();
    String name=c.getSimpleName().toString();if(name.isEmpty())return "";
    String kind=c.getKind()==Tree.Kind.INTERFACE?"interface":c.getKind()==Tree.Kind.ANNOTATION_TYPE?"@interface":"class";
    StringBuilder b=new StringBuilder(flags(c.getModifiers(),false)+kind+" "+name);
    if(!c.getTypeParameters().isEmpty())b.append('<').append(join(c.getTypeParameters())).append('>');
    String ext=c.getExtendsClause()==null?"":c.getExtendsClause().toString();

    if(!ext.isEmpty()&&!sdk(ext))b.append(" extends ").append(ext);
    List<String> impl=new ArrayList<>();for(Tree t:c.getImplementsClause())if(!sdk(t.toString()))impl.add(t.toString());
    if(!impl.isEmpty())b.append(kind.equals("interface")?" extends ":" implements ").append(String.join(",",impl));
    b.append("{\n");
    for(Tree member:c.getMembers()){
      if(member instanceof ClassTree)b.append(cls((ClassTree)member,name));
      else if(member instanceof VariableTree){
        VariableTree v=(VariableTree)member;
        if(sdk(v.getType().toString())){
          // Existing app callers only compare the session token and use inherited
          // Android View input-fence methods. These are explicit app boundaries,
          // never replacement Mozilla classes or validation of Gecko APIs.
          if(name.equals("GeckoWebView")&&v.getName().contentEquals("surface"))b.append("android.view.View surface=null;\n");
          if(name.equals("GeckoWebView")&&v.getName().contentEquals("current"))b.append("java.lang.Object current=null;\n");
          continue;
        }
        String value=def(v.getType());
        if(v.getInitializer()!=null&&v.getInitializer() instanceof LiteralTree)value=v.getInitializer().toString();
        String modifiers=flags(v.getModifiers(),true);if(v.getModifiers().getFlags().contains(Modifier.FINAL)&&v.getInitializer() instanceof LiteralTree)modifiers+="final ";
        b.append(modifiers).append(v.getType()).append(' ').append(v.getName()).append('=').append(value).append(";\n");
      }else if(member instanceof MethodTree){
        MethodTree m=(MethodTree)member;String signature=(m.getReturnType()==null?"":m.getReturnType().toString())+join(m.getParameters())+join(m.getThrows());
        if(sdk(signature))continue;
        b.append(flags(m.getModifiers(),false));
        if(!m.getTypeParameters().isEmpty())b.append('<').append(join(m.getTypeParameters())).append("> ");
        boolean constructor=m.getReturnType()==null;
        b.append(constructor?name:m.getReturnType()+" "+m.getName()).append('(');
        List<String> parameters=new ArrayList<>();for(VariableTree v:m.getParameters())parameters.add(v.toString().replaceAll("@[A-Za-z0-9_.]+(?:\\([^)]*\\))?\\s*", ""));
        b.append(String.join(",",parameters)).append(')');
        if(!m.getThrows().isEmpty())b.append(" throws ").append(join(m.getThrows()));
        if(m.getBody()==null)b.append(';');
        else{
          b.append('{');
          if(constructor&&!ext.isEmpty()){
            List<? extends StatementTree> statements=m.getBody().getStatements();
            String first=statements.isEmpty()?"":statements.get(0).toString();
            if(first.startsWith("super(")||first.startsWith("this("))b.append(first);
            else if(name.equals("GeckoWebView"))b.append("super(context);");
          }
          b.append("throw new UnsupportedOperationException(\"Compilation-only app boundary\");}");
        }
        b.append('\n');
      }
    }
    return b.append("}\n").toString();
  }
  static String join(List<? extends Tree> ts){List<String> ss=new ArrayList<>();for(Tree t:ts)ss.add(t.toString());return String.join(",",ss);}
  public static void main(String[] args)throws Exception{
    Path src=Path.of(args[0]),out=Path.of(args[1]);Files.createDirectories(out);
    Set<String> actual=new HashSet<>(Arrays.asList(Arrays.copyOfRange(args,2,args.length)));
    JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();StandardJavaFileManager fm=compiler.getStandardFileManager(null,null,null);
    List<File> files=new ArrayList<>();try(var stream=Files.list(src)){stream.filter(p->p.toString().endsWith(".java")).forEach(p->files.add(p.toFile()));}
    JavacTask task=(JavacTask)compiler.getTask(null,fm,null,List.of("-proc:none"),null,fm.getJavaFileObjectsFromFiles(files));
    for(CompilationUnitTree unit:task.parse()){
      String filename=Path.of(unit.getSourceFile().toUri()).getFileName().toString();if(actual.contains(filename))continue;
      StringBuilder b=new StringBuilder("package "+unit.getPackageName()+";\n");
      for(ImportTree imp:unit.getImports())if(!imp.toString().contains("org.mozilla"))b.append(imp).append('\n');
      for(Tree type:unit.getTypeDecls())if(type instanceof ClassTree)b.append(cls((ClassTree)type,null));
      Files.writeString(out.resolve(filename),b.toString());
    }
  }
}
