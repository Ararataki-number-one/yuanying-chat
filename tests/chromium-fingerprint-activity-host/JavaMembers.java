import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TreeScanner;
import com.sun.source.util.Trees;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.List;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

/** Read real Java declarations without resolving Android/Gecko dependencies. */
public class JavaMembers {
  public static void main(String[] args) throws Exception {
    Path file = Path.of(args[0]);
    String source = Files.readString(file);
    JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
    DiagnosticCollector<JavaFileObject> errors = new DiagnosticCollector<>();
    try (StandardJavaFileManager files = compiler.getStandardFileManager(errors, null, StandardCharsets.UTF_8)) {
      JavacTask task = (JavacTask) compiler.getTask(null, files, errors, List.of("-proc:none"), null,
          files.getJavaFileObjects(file));
      CompilationUnitTree unit = task.parse().iterator().next();
      if (errors.getDiagnostics().stream().anyMatch(d -> d.getKind() == Diagnostic.Kind.ERROR))
        throw new IllegalArgumentException(errors.getDiagnostics().toString());
      SourcePositions positions = Trees.instance(task).getSourcePositions();
      String topName = file.getFileName().toString().replace(".java", "");
      for (Tree tree : unit.getTypeDecls()) {
        if (!(tree instanceof ClassTree) || !((ClassTree) tree).getSimpleName().contentEquals(topName)) continue;
        new TreeScanner<Void,Integer>() {
          void emit(String kind, String name, Tree node) {
            int start = Math.toIntExact(positions.getStartPosition(unit,node));
            int end = Math.toIntExact(positions.getEndPosition(unit,node));
            String body = source.substring(start,end);
            System.out.println(kind+"\t"+name+"\t"+Base64.getEncoder().encodeToString(body.getBytes(StandardCharsets.UTF_8)));
          }
          @Override public Void visitClass(ClassTree node,Integer depth) {
            if (depth == 1) emit("class",node.getSimpleName().toString(),node);
            return super.visitClass(node,depth+1);
          }
          @Override public Void visitMethod(MethodTree node,Integer depth) {
            String name=node.getName().toString();
            if (depth == 1) emit("method",name,node);
            else if (name.equals("onPageStarted") || name.equals("doUpdateVisitedHistory")) emit("callback",name,node);
            return super.visitMethod(node,depth);
          }
        }.scan(tree,0);
      }
    }
  }
}
